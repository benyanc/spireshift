"""Four bounded diagnostic native replays; preserve old actions, rules and all players."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_relic_worker import SCRIPT, RelicWorker
from spireshift.engine_run import _run_inputs
from spireshift.engine_selection_audit import audit_selection_worker
from spireshift.engine_worker import worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_relic_observation import CONTRACT, legacy_view, verify

SOURCES = ("engine_relic_worker.py", "native_relic_observation.py", "native_relic_qualification.py")


class Replay:
    def __init__(self, source: dict[str, Any]) -> None:
        self.rows = source["decisions"]
        self.index = 0

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        if (
            self.index >= len(self.rows)
            or legacy_view(public) != self.rows[self.index]["public_input"]
        ):
            raise ValueError("Repaired native run changed the legacy public trace or menu")
        action = self.rows[self.index]["choice"]["action_index"]
        self.index += 1
        return {
            "action_index": action,
            "public_input_id": manifest_identifier(public),
            "behavior": "diagnostic_saved_action_replay",
            "ordinary_PPO_eligible": False,
        }


def run(root: Path, path: Path) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + 210
    cfg = json.loads(path.read_text())
    if (
        cfg["schema_version"] != "native-relic-observation-qualification-config-v1"
        or cfg["helpers_sha256"] != worker_helpers(root, SCRIPT)
        or cfg["implementation_sha256"]
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
    ):
        raise ValueError("Freeze the repaired worker, public counter contract and finite plan")
    source = identified(root / cfg["source_report"]["path"])
    audit = identified(root / cfg["input_audit"]["path"])
    if (
        source["report_id"] != cfg["source_report"]["id"]
        or audit["report_id"] != cfg["input_audit"]["id"]
        or not audit["actor_encoding_distinctions_passed"]
    ):
        raise ValueError("Require the sealed source experiment and actor distinction audit")
    episodes = [c["source_episode"] for c in cfg["cases"]]
    if (
        len(episodes) != 4
        or len({c["key"] for c in cfg["cases"]}) != 4
        or sorted(Counter(episodes).values()) != [2, 2]
        or any(n not in source["sources"] for n in episodes)
    ):
        raise ValueError("Use two sealed TRAIN traces, each replayed exactly twice")
    sources = {**source["sources"], **audit["sources"]}
    for ref in (cfg["source_report"], cfg["input_audit"]):
        sources[ref["path"]] = _sha_file(root / ref["path"])
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": v for n, v in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": v for n, v in cfg["helpers_sha256"].items()})
    check_sources(root, sources)
    journal = ChunkJournal(root, cfg)
    with journal.lock():
        final = journal.workspace / "report.json"
        if final.exists():
            cached = identified(final)
            if cached["config_id"] != journal.config_id:
                raise ValueError("Saved counter qualification belongs to another plan")
            check_sources(root, cached["sources"])
            return cached
        if _running_games():
            raise ValueError("Close STS2 before the isolated counter checks")
        old_cfg = json.loads((root / source["recipe_path"]).read_text())
        q = load_engine_qualification_config(root / old_cfg["qualification"])
        inputs = _run_inputs(q, root / old_cfg["native_inputs"]["path"])
        account = Path.home() / "Library/Application Support/SlayTheSpire2"
        before = _shared_snapshot(account)
        outcomes = []
        for case in cfg["cases"]:
            request = {"case": case, "contract": CONTRACT}
            sealed = journal.completed(case["key"], request)
            if sealed is not None:
                outcomes.append(sealed["result"])
                sources.update(sealed["sources"])
                continue
            target = journal.begin(case["key"], request)
            header = json.loads((root / case["source_episode"]).read_text())
            old = read_native_episode(root / case["source_episode"], header["binding"])
            if (
                header["binding"]["partition"] != "train"
                or old["status"] != "terminal"
                or not old["ordinary_PPO_eligible"]
            ):
                raise ValueError("Replay only a planned verified TRAIN trace as a diagnostic")
            chooser = Replay(old)
            worker = RelicWorker(
                q, inputs, target / "worker", Path(old_cfg["node"]), cfg["helpers_sha256"]
            )
            try:
                atomic_json(worker.workspace / "selection-verifier.json", {"node": old_cfg["node"]})
                actual = worker.episode(
                    old["seed"],
                    maximum_decisions=4096,
                    wall_seconds=min(45, deadline - time.monotonic() - 20),
                    cpu_seconds=128,
                    chooser=chooser,
                )
                actual.update(
                    worker_workspace="worker",
                    ordinary_PPO_eligible=False,
                    privileged_fixed_world_teacher=False,
                    policy_contract="native_inventory_diagnostic_replay_v1",
                )
                save_native_episode(
                    target / "episode.json",
                    actual,
                    {
                        "config_id": journal.config_id,
                        "partition": "diagnostic",
                        "source_episode": case["source_episode"],
                        "counter_contract": CONTRACT,
                    },
                )
                if actual["status"] != "terminal":
                    worker.retire(actual.get("error", "Counter diagnostic failed"))
                    raise ValueError(f"Counter diagnostic failed: {actual.get('error')}")
                worker.close()
                if chooser.index != len(old["decisions"]) or any(
                    actual[k] != old[k] for k in ("victory", "maximum_floor", "completed_acts")
                ):
                    raise ValueError("Same saved native actions produced a different ending")
                delivery = audit_selection_worker(
                    worker.workspace, [target / "episode.json"], deadline=deadline
                )
                counters = verify(worker.workspace, deadline)
                if not delivery["valid"]:
                    raise ValueError("Repaired worker delivery did not verify")
                atomic_json(target / "native-audit.json", delivery)
                result = {
                    "key": case["key"],
                    "seed": old["seed"],
                    "source_episode": case["source_episode"],
                    "decisions": chooser.index,
                    "old_public_trace_and_actions_unchanged": True,
                    "ending_unchanged": True,
                    "native_delivery_verified": True,
                    **counters,
                }
                atomic_json(target / "result.json", result)
                journal.commit(case["key"], request, result)
                saved = journal.completed(case["key"], request)
                assert saved is not None
                sources.update(saved["sources"])
                outcomes.append(result)
            finally:
                worker.stop()
        checks = immutable_checks(q, inputs)
        checks["account_profile_unchanged"] = before == _shared_snapshot(account)
        if (
            not all(checks.values())
            or len(outcomes) != 4
            or not any(r["numeric_counter_observations"] for r in outcomes)
        ):
            raise ValueError(
                "Counter qualification lacks clean cases, a numeric witness or immutable checks"
            )
        check_sources(root, sources)
        body = {
            "schema_version": "native-relic-observation-qualification-v1",
            "config_id": journal.config_id,
            "status": "native_relic_observation_qualification_complete",
            "cases": outcomes,
            "completed_games": len(outcomes),
            "failed_games": 0,
            "independent_seeds": 2,
            "inventory_observation_contract": CONTRACT,
            "checks": checks,
            "sources": sources,
            "all_original_model_weights_and_Adam_unchanged": True,
            "optimizer_steps": 0,
            "ordinary_PPO_eligible": False,
            "game_apps_created": 0,
            "training_allowed": False,
            "claim_scope": (
                "four_native_diagnostic_replays_public_counter_projection_"
                "and_unchanged_legacy_trace_only"
            ),
            "wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(final, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe)
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_relic_qualification", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
