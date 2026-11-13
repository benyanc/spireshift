"""Finite shared-contract/native/official checkpoint delivery checks, never learning."""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_flow_worker_v7 import RelicWorker
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import difference_paths, local
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v9 import load, prepare
from spireshift.native_flow_session_v9 import official_prefix
from spireshift.native_launch_limits import load_launch
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines


def completion_status(delivered: bool, inputs_equal: bool) -> str:
    if not delivered:
        return "live_checkpoint_delivery_blocked"
    if not inputs_equal:
        return "live_checkpoint_inputs_blocked"
    return "live_checkpoint_delivery_control_pass"


def append(path: Path, value: dict[str, Any]) -> None:
    with gzip.open(path, "at") as file:
        file.write(json.dumps(value, allow_nan=False) + "\n")


def native_prefix(
    context: dict[str, Any],
    case: dict[str, Any],
    attempt: Path,
    policy: LivePolicy,
    deadline: float,
) -> dict[str, Any]:
    root, cfg = context["qualification"].root, context["config"]
    attempt.mkdir(parents=True, exist_ok=False)
    worker = RelicWorker(
        context["qualification"],
        context["native"],
        attempt / "worker",
        Path(cfg["node"]),
        context["native_helpers"],
    )
    converter = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/engine-shared-input-v14.mjs")],
        attempt / "projection-stderr.log",
    )
    started_cpu = time.thread_time()
    ending = None
    try:
        current = worker.request(
            "mount", seed=case["seed"], timeout=min(25, deadline - time.monotonic())
        )
        for _ in range(cfg["maximum_decisions"]):
            if (
                time.monotonic() > deadline - 5
                or worker.cpu_seconds() + time.thread_time() - started_cpu > 128
            ):
                raise TimeoutError("Native checkpoint prefix cap")
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if (
                policy.decisions == 0
                and case.get("expected_first_public_input_id")
                and frame["input_digest"] != case["expected_first_public_input_id"]
            ):
                raise ValueError("The observed target scenario changed before any action")
            append(attempt / "shared-public.jsonl.gz", {"kind": "policy_input", "frame": frame})
            if frame["terminal"]:
                ending = frame["ending"]
                break
            choice = policy.choose(frame)
            binding = frame["actions"][choice["action_index"]]
            successor = worker.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=min(20, deadline - time.monotonic()),
            )
            receipt = {
                "binding_id": frame["binding_id"],
                "delivery": "delivered",
                "bound_action_id": binding["bound_action_id"],
                "runtime_instance_id": frame["observation"]["runtime_instance_id"],
                "before_snapshot_id": frame["observation"]["snapshot_id"],
                "successor_snapshot_id": successor["snapshot"]["snapshot_id"],
            }
            policy.acknowledge(receipt)
            converter.commit(choice, receipt, deadline)
            append(
                attempt / "shared-public.jsonl.gz",
                {"kind": "policy_choice", "choice": choice, "receipt": receipt},
            )
            current = successor
        shutdown = worker.close()
        converter.close()
        body = {
            "status": "native_prefix_pass",
            "policy_decisions": policy.decisions,
            "shutdown": shutdown,
            "ending": ending,
            "optimizer_updates": 0,
            "full_game_evaluation": False,
        }
        body["report_id"] = manifest_identifier(body)
        atomic_json(attempt / "report.json", body)
        return body
    finally:
        converter.stop()
        worker.stop()


def frames(path: Path) -> list[dict[str, Any]]:
    # Prefix is explicitly bounded at 128 decisions; return compact hashes/facts only.
    result = []
    with gzip.open(path, "rt") as file:
        for line in file:
            row = json.loads(line)
            if row.get("kind") == "policy_input":
                f = row["frame"]
                result.append(
                    {"input": f["public_input"], "keys": [a["key"] for a in f["actions"]]}
                )
    return result


def compare_prefixes(native: Path, official: Path) -> dict[str, Any]:
    left = frames(native)
    right = frames(official)
    matched = 0
    witness = None
    for index, (a, b) in enumerate(zip(left, right, strict=False)):
        if a != b:
            witness = {
                "decision": index,
                "difference_paths": difference_paths(a["input"], b["input"]),
                "complete_menu_keys_equal": a["keys"] == b["keys"],
                "native_input_id": manifest_identifier(a["input"]),
                "official_input_id": manifest_identifier(b["input"]),
            }
            break
        matched += 1
    return {
        "native_decisions": len(left),
        "official_decisions": len(right),
        "equal_input_prefix": matched,
        "first_difference": witness,
        "complete_prefix_input_equivalence": bool(left) and len(left) == len(right) == matched,
        "later_divergent_states_realignable": False,
    }


def run(root: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg = context["config"]
    if cfg["stage"] == "saved_only_checks":
        raise ValueError("The saved-only stage cannot launch a game")
    workspace = local(root, cfg["workspace"])
    final = workspace / "report.json"
    if final.exists():
        saved = identified(final)
        if saved["config_id"] != manifest_identifier(cfg) or (workspace / "active.json").exists():
            raise ValueError("A saved live result belongs to different settings")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    # No active marker or attempt is created when the owner's game is open.
    if _running_games():
        raise ValueError("Close the game before the short live checkpoint check")
    preflight_working_app(context["working_app"])
    imported = prepare(root, context)
    workspace.mkdir(parents=True, exist_ok=True)
    marker = workspace / "active.json"
    if marker.exists():
        raise ValueError(
            "Preserve the interrupted live checkpoint plan; do not replay uncertain seeds"
        )
    source_copy = workspace / "source-at-launch"
    if not source_copy.exists():
        source_copy.mkdir()
        for name in (*cfg["implementation_sha256"], *cfg["helpers_sha256"], *cfg["entry_sha256"]):
            target = source_copy / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / name).read_bytes())
        atomic_json(source_copy / "recipe.json", cfg)
    atomic_json(marker, {"config_id": manifest_identifier(cfg), "optimizer_updates": 0})
    launches = workspace / "launches"
    launches.mkdir(exist_ok=True)
    atomic_json(
        launches / f"launch-{len(list(launches.glob('*.json'))) + 1}.json",
        {
            "experiment_id": manifest_identifier(cfg),
            "limits": context["launch_limits"].as_dict(),
            "launch_file": context["launch_file"],
            "launch_sha256": context["launch_sha256"],
        },
    )
    started = time.monotonic()
    deadline = started + context["launch_limits"].wall_seconds - 15
    cases = []
    for case in cfg["cases"]:
        directory = workspace / case["key"]
        if directory.exists():
            unit = identified(directory / "unit.json")
            if unit["config_id"] != manifest_identifier(cfg) or unit["case"] != case:
                raise ValueError("Completed live unit belongs to different settings")
            check_sources(root, unit["evidence"])
            cases.append(unit["result"])
            continue
        if deadline - time.monotonic() < cfg["maximum_case_wall_seconds"] + 10:
            index = len(list(workspace.glob("clean-pause-*.json"))) + 1
            marker.rename(workspace / f"clean-pause-{index}.json")
            return {
                "status": "clean_pause",
                "completed_pairs": len(cases),
                "planned_pairs": len(cfg["cases"]),
                "checkpoint_delivery_exercised": False,
                "optimizer_updates": 0,
                "repeat_same_command_to_resume": True,
            }
        directory.mkdir()
        model, _, state_receipt = imported[case["player"]]
        pair_started = time.monotonic()
        case_deadline = min(deadline, time.monotonic() + cfg["maximum_case_wall_seconds"])
        native = native_prefix(
            context,
            case,
            directory / "native",
            LivePolicy(model, context["score"], case["seed"]),
            case_deadline,
        )
        official = official_prefix(
            context,
            case,
            directory / "official",
            LivePolicy(model, context["score"], case["seed"]),
            case_deadline,
        )
        comparison = compare_prefixes(
            directory / "native/shared-public.jsonl.gz", directory / "official/live-public.jsonl.gz"
        )
        cases.append(
            {
                "key": case["key"],
                "seed": case["seed"],
                "player": case["player"],
                "native": native,
                "official": official,
                "comparison": comparison,
                "import_id": state_receipt["report_id"],
                "pair_wall_seconds": time.monotonic() - pair_started,
            }
        )
        atomic_json(directory / "result.json", cases[-1])
        unit = {
            "config_id": manifest_identifier(cfg),
            "case": case,
            "result": cases[-1],
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in directory.rglob("*") if p.is_file()
            },
        }
        unit["report_id"] = manifest_identifier(unit)
        atomic_json(directory / "unit.json", unit)
        match_status = (
            "INPUTS MATCH" if comparison["complete_prefix_input_equivalence"] else "INPUT MISMATCH"
        )
        print(
            f"Live checkpoint {len(cases)}/{len(cfg['cases'])}: "
            f"{match_status}; "
            f"game delivery {official['status']}; "
            f"{comparison['equal_input_prefix']} equal input decisions; zero optimizer updates.",
            flush=True,
        )
    check_sources(root, context["sources"])
    evidence = {
        str(p.relative_to(root)): _sha_file(p)
        for p in workspace.rglob("*")
        if p.is_file() and p != marker
    }
    delivery = all(
        c["native"]["status"] == "native_prefix_pass"
        and c["official"]["status"] == "official_prefix_pass"
        for c in cases
    )
    inputs_equal = all(c["comparison"]["complete_prefix_input_equivalence"] for c in cases)
    body = {
        "schema_version": "native-live-checkpoint-adapter-result-v1",
        "config_id": manifest_identifier(cfg),
        "environment_id": context["environment"]["manifest_id"],
        "implementation_id": manifest_identifier(cfg["implementation_sha256"]),
        "helpers_id": manifest_identifier(cfg["helpers_sha256"]),
        "control_kind": cfg.get("control_kind"),
        "status": completion_status(delivery, inputs_equal),
        "cases": cases,
        "sources": context["sources"],
        "evidence": evidence,
        "seeds": sorted({c["seed"] for c in cfg["cases"]}),
        "checkpoint_delivery_exercised": delivery,
        "completed_regression_replay": bool(cfg.get("completed_regression_replay")),
        "observation_only_start_replay": bool(cfg.get("observed_start_replay")),
        "fresh_strength_evidence": False,
        "full_prefix_input_equivalence": inputs_equal,
        "input_equivalence_required_for_success": True,
        "full_game_performance_evaluated": False,
        "game_starts": 2 * len(cases),
        "original_weights_and_all_Adam_unchanged": True,
        "optimizer_updates": 0,
        "training_allowed": False,
        "checkpoint_promoted": False,
        "adaptive_controller_allowed": False,
        "live_gate_qualification_granted": False,
        "wall_seconds": time.monotonic() - started,
        "wall_seconds_scope": "current_launch_only",
        "completed_pairs_wall_seconds": sum(c["pair_wall_seconds"] for c in cases),
        "claim_scope": "current_checkpoint_delivery_prefixes_not_complete_host_parity"
        "_or_playing_strength",
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(final, body)
    marker.rename(workspace / "complete.json")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--launch", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        context = load(root, args.recipe.resolve())
        context["launch_limits"] = load_launch(
            root, args.launch.resolve(), args.recipe.resolve(), context["config"]
        )
        context["launch_file"] = str(args.launch.resolve().relative_to(root))
        context["launch_sha256"] = _sha_file(args.launch)
        if args.preflight:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "environment_id": context["environment"]["manifest_id"],
                        "games_launched": 0,
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        report = run(root, context)
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in {"sources", "evidence", "cases"}},
                indent=2,
            )
        )
        return (
            0 if report["status"] in {"live_checkpoint_delivery_control_pass", "clean_pause"} else 2
        )
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "blocked_preserving_evidence", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
