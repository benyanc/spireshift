"""Replay two sealed Act 1 losses to exact public menus and test local alternatives."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_worker import _EpisodeLiveness
from spireshift.native_a8_boss2_inputs import declaration, freeze, load, short_check
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_combat_branch_policy import (
    EEL_ATTACKS,
    eel_choice,
    giant_choice,
    intent_damage,
)
from spireshift.native_a8_rescue_game import (
    TRACE,
    Progress,
    bridge,
    decisions,
    public_state,
    receipt,
)
from spireshift.native_a8_rescue_inputs import CONTROL_LIMITS, GAME_LIMITS, ORDERED_PROOF
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write
from spireshift.native_win_teacher import validate_student_input

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-combat-branches-v1.json"
MODULE = "spireshift.native_a8_combat_branches"
SCOPE = "known_world_local_combat_diagnostic_only"


def require_exact_menu(frame: dict[str, Any], original: dict[str, Any], line: int) -> None:
    # Canonical public inputs and action keys are comparable across processes.
    # Snapshot and bound-action IDs belong to the fresh worker only.
    if (
        frame["input_digest"] != original["input_digest"]
        or frame["source_family"] != original["source_family"]
        or frame["terminal"] != original["terminal"]
        or [a["key"] for a in frame["actions"]] != [a["key"] for a in original["actions"]]
        or difference_paths(frame["public_input"], original["public_input"])
    ):
        paths = difference_paths(frame["public_input"], original["public_input"])
        raise ValueError(f"Saved public menu differs at line {line}: {paths[:8]}")


class Branch:
    def __init__(self, case: dict[str, Any], trace: Path) -> None:
        self.case = case
        self.history = decisions(trace)
        self.progress = Progress()
        self.liveness = _EpisodeLiveness()
        self.anchor: dict[str, Any] | None = None
        self.steps: list[dict[str, Any]] = []
        self.prefix = self.native_deliveries = self.local_factors = 0
        self.outcome: str | None = None
        self.final_hp: int | None = None
        self.death_blow: dict[str, Any] | None = None

    def choose(self, frame: dict[str, Any]) -> dict[str, Any] | None:
        public = frame["public_input"]
        validate_student_input(public)
        natural = self.progress.observe(frame)
        if natural is None:
            self.liveness.observe(frame["input_digest"])
        run, player, interaction = public_state(frame)
        kind = interaction["kind"]
        combat = interaction["content"].get("context", {})
        if (
            self.native_deliveries >= GAME_LIMITS["maximum_decisions"]
            or combat.get("round", 0) > GAME_LIMITS["maximum_rounds_per_fight"]
        ):
            raise ValueError("Native decision or combat round limit reached")
        if self.anchor is None:
            line, original, saved = next(self.history, (0, {}, None))
            if saved is None or natural is not None:
                raise ValueError("The replay ended before the declared combat menu")
            require_exact_menu(frame, original, line)
            index = saved["choice"]["action_index"]
            if line < self.case["line"]:
                return self.action(
                    frame, index, saved["receipt"]["delivery_domain"], "saved_prefix"
                )
            if line != self.case["line"] or frame["input_digest"] != self.case["input_digest"]:
                raise ValueError("The exact declared combat branch root is missing")
            self.anchor = {
                "line": line,
                "input_digest": frame["input_digest"],
                "saved_action": public["candidates"][index]["label"],
                "saved_key": frame["actions"][index]["key"],
            }
            self.history.close()
        if run["act"] != 1 or run["floor"] != self.case["floor"]:
            raise ValueError("A combat branch cannot continue beyond its declared room")
        if natural == "act1_loss":
            self.outcome, self.final_hp = "fight_loss", 0
            return None
        if (
            kind == "reward_claim"
            and combat.get("reward_kind") == "room_rewards"
            and combat.get("completed_boss_combat") is not False
            and self.steps
            and player["hp"] > 0
        ):
            if self.case["enemy"] == "TERROR_EEL" and [s["label"] for s in self.steps] != list(
                EEL_ATTACKS
            ):
                raise ValueError("Eel rewards require the complete three-attack sequence")
            if self.case["encounter"] == "boss" and (
                self.death_blow is None or self.steps[-1]["label"] != "End turn"
            ):
                raise ValueError("Giant rewards require a delivered Death Blow turn")
            self.outcome, self.final_hp = "fight_win", player["hp"]
            return None
        if (
            kind not in {"combat_turn", "card_selection"}
            or combat.get("encounter_type") != self.case["encounter"]
            or [e["definition_id"] for e in combat.get("enemies", [])] != [self.case["enemy"]]
        ):
            raise ValueError("The native combat owner differs from the declared branch")
        index = (
            eel_choice(public, combat, len(self.steps))
            if self.case["enemy"] == "TERROR_EEL"
            else giant_choice(public, combat, self.steps[-1]["label"] if self.steps else None)
        )
        action = self.action(frame, index, "native", "combat_branch")
        if not self.steps and action["action_key"] == self.anchor["saved_key"]:
            raise ValueError("The branch must make a different choice at the declared root")
        return action

    def action(self, frame: dict[str, Any], index: int, domain: str, stage: str) -> dict[str, Any]:
        candidate = frame["public_input"]["candidates"][index]
        return {
            "action_index": index,
            "action_key": frame["actions"][index]["key"],
            "binding_id": frame["binding_id"],
            "label": candidate["label"],
            "stage": stage,
            "expected_domain": domain,
        }

    def acknowledge(self, frame: dict[str, Any], choice: dict[str, Any], domain: str) -> None:
        if domain not in {"native", "local_answer_factor"} or domain != choice["expected_domain"]:
            raise ValueError("The delivered action domain differs from the exact branch plan")
        self.native_deliveries += domain == "native"
        self.local_factors += domain == "local_answer_factor"
        if choice["stage"] == "saved_prefix":
            self.prefix += 1
            return
        _, player, interaction = public_state(frame)
        combat = interaction["content"]["context"]
        enemy = combat["enemies"][0]
        step = {
            "label": choice["label"],
            "action_key": choice["action_key"],
            "input_digest": frame["input_digest"],
            "round": combat["round"],
            "hp": player["hp"],
            "block": combat["player"].get("block"),
            "enemy_hp": enemy["hp"],
            "steam_eruption": next(
                (
                    s["amount"]
                    for s in enemy["statuses"]
                    if s["definition_id"] == "STEAM_ERUPTION_POWER"
                ),
                None,
            ),
        }
        blow = intent_damage(enemy, "DeathBlow")
        if (
            blow
            and frame["public_input"]["candidates"][choice["action_index"]]["verb"] == "end_turn"
        ):
            self.death_blow = {
                "damage": blow,
                "hp_before": step["hp"],
                "block_before": step["block"],
            }
        self.steps.append(step)

    def result(self) -> dict[str, Any]:
        if self.anchor is None or self.outcome is None or not self.steps:
            raise ValueError("A partial diagnostic cannot be sealed as a combat result")
        return {
            "root": self.anchor,
            "exact_prefix_choices": self.prefix,
            "verified_native_deliveries": self.native_deliveries,
            "local_answer_factors": self.local_factors,
            "outcome": self.outcome,
            "final_hp": self.final_hp,
            "death_blow": self.death_blow,
            "survived_death_blow": self.death_blow is not None and self.outcome == "fight_win",
            "branch_steps": self.steps,
        }


def reconstruct(
    ctx: dict[str, Any], case: dict[str, Any], trace: Path, target: Path, out: Path, deadline: float
) -> dict[str, Any]:
    out.mkdir()
    plan = Branch(case, trace)
    converter = bridge(ctx, out / "converter.log")
    observations = iter(records(target / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(target / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(target / "worker/answer-plan-deliveries.jsonl.gz"))
    try:
        current = next(observations)
        for _, recorded, saved in decisions(target / TRACE):
            frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            if difference_paths(frame, recorded):
                raise ValueError("Live branch frame failed independent raw reconstruction")
            choice = plan.choose(frame)
            if saved is None:
                if choice is not None:
                    raise ValueError("The raw branch ended before a native fight outcome")
                break
            if choice is None or not same(choice, saved["choice"]):
                raise ValueError("Live branch choice differs from the reconstructed decision")
            current, actual, domain = next(observations), next(receipts), next(domains)
            accepted = receipt(
                frame, choice, domain["delivery_domain"], current["snapshot"]["snapshot_id"]
            )
            if (
                not same(accepted, saved["receipt"])
                or actual["delivery"] != "delivered"
                or actual["snapshot_id"] != accepted["before_snapshot_id"]
                or actual["action"]["bound_action_id"] != accepted["bound_action_id"]
                or actual["successor_snapshot_id"] != accepted["successor_snapshot_id"]
                or domain["before_snapshot_id"] != accepted["before_snapshot_id"]
                or domain["action_id"] != accepted["bound_action_id"]
                or domain["successor_snapshot_id"] != accepted["successor_snapshot_id"]
            ):
                raise ValueError("Independent native delivery or successor proof differs")
            plan.acknowledge(frame, choice, accepted["delivery_domain"])
            converter.commit(choice, accepted, deadline)
        if any(next(stream, None) is not None for stream in (observations, receipts, domains)):
            raise ValueError("Unexpected raw combat branch evidence")
        converter.close()
    except StopIteration as exc:
        raise ValueError("Missing a native branch observation or receipt") from exc
    finally:
        plan.history.close()
        converter.stop()
    worker_path = target / "worker"
    if (worker_path / "selection-cursor.jsonl.gz").exists():
        proof = subprocess.run(
            [
                ctx["node"],
                str(ctx["qualification"].root / "scripts" / ORDERED_PROOF),
                str(worker_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=max(1, min(20, deadline - time.monotonic())),
        )
        checked = json.loads(proof.stdout)
        if (
            checked["native_deliveries"] != plan.native_deliveries
            or checked["local_factors"] != plan.local_factors
        ):
            raise ValueError("Ordered selection delivery counts differ")
        write(out / "ordered-answer-raw-verification.json", checked)
    return plan.result()


def play(
    ctx: dict[str, Any], case: dict[str, Any], trace: Path, target: Path, deadline: float
) -> dict[str, Any]:
    plan = Branch(case, trace)
    boundary = min(deadline - 20, time.monotonic() + GAME_LIMITS["episode_wall_seconds"])
    native = worker(ctx, target / "worker")
    converter = None
    ending = None
    try:
        converter = bridge(ctx, target / "converter.log")
        current = native.request("mount", seed=case["seed"], timeout=25)
        identity = current["private_start_identity"]
        if (
            current["episode"] != 1
            or current["reset"] is not False
            or identity["seed"] != case["seed"]
            or identity["started_with_neow"] is not True
        ):
            raise ValueError("Branch worker did not mount the declared isolated normal start")
        write(
            target / "native-start.json",
            {"identity": identity, "process_id": current["native_process_id"]},
        )
        while True:
            if (
                time.monotonic() > boundary - 3
                or current["usage"]["native_cpu_seconds"] > GAME_LIMITS["episode_cpu_seconds"]
            ):
                raise ValueError("Combat branch hit a wall or native CPU limit")
            frame = converter.project(current["snapshot"], current["reads"], None, boundary)
            choice = plan.choose(frame)
            if choice is None:
                append(target / TRACE, {"kind": "final_observation", "frame": frame})
                if plan.outcome == "fight_loss":
                    ending = native.request("ending", timeout=15)
                    final = ending["private_final_identity"]
                    if (
                        ending["native_ending_evidence_agrees"] is not True
                        or final["seed"] != case["seed"]
                        or final["act"] != 1
                        or final["native_player_dead"] is not True
                        or final["native_game_over"] is not True
                    ):
                        raise ValueError("Native loss evidence disagrees")
                break
            append(target / TRACE, {"kind": "policy_input", "frame": frame})
            current = native.request(
                "step",
                snapshot_id=frame["observation"]["snapshot_id"],
                action_index=frame["actions"][choice["action_index"]]["raw_index"],
                timeout=min(20, max(1, boundary - time.monotonic())),
            )
            domain = current["delivery_domain"]
            accepted = receipt(frame, choice, domain, current["snapshot"]["snapshot_id"])
            plan.acknowledge(frame, choice, domain)
            converter.commit(choice, accepted, boundary)
            append(target / TRACE, {"kind": "policy_choice", "choice": choice, "receipt": accepted})
        shutdown = native.close()
        converter.close()
    finally:
        plan.history.close()
        if converter is not None:
            converter.stop()
        native.stop()
    if (
        shutdown["clean_exit"] is not True
        or shutdown["runtime_errors"]
        or shutdown["episodes"] != 1
    ):
        raise ValueError("Combat branch worker shutdown was incomplete")
    result = reconstruct(ctx, case, trace, target, target / "verification", deadline)
    if not same(result, plan.result()):
        raise ValueError("Independent branch outcome differs from the live result")
    return {**result, "usage": current["usage"], "shutdown": shutdown, "native_ending": ending}


def check_inputs(root: Path, cfg: dict[str, Any], ctx: dict[str, Any]) -> dict[str, bool]:
    if json.loads((root / RECIPE).read_text()) != cfg:
        raise ValueError("The combat branch declaration changed")
    check_sources(root, cfg["implementation"])
    return freeze(root, ctx)


def branches(root: Path, cfg: dict[str, Any], mode: str, started: float) -> dict[str, Any]:
    parent = declaration(root)
    ctx = load(root, parent)
    checks = short_check(root, ctx)
    if (
        checks is None
        or cfg["objective"] != parent["objective"]
        or cfg["game_limits"] != GAME_LIMITS
    ):
        raise ValueError("Require the sealed qualification inputs and original objective")
    ctx["reward_short_receipts"] = checks
    saved = identified(verified(root, cfg["saved_result"]))
    audit = identified(verified(root, saved["saved_audit"]))
    if (
        audit["execution_id"] != ctx["execution_id"]
        or audit["config_id"] != ctx["reward_config_id"]
        or audit["status"] != "complete_boss_qualification_losses_verified"
    ):
        raise ValueError("Require the exact v2 qualification loss audit")
    previous, store = ChunkJournal(root, parent), ChunkJournal(root, cfg)
    shared = Path.home() / SHARED_PROFILE
    deadline = started + CONTROL_LIMITS["wall_seconds"] - 10
    with (previous.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        before = check_inputs(root, cfg, ctx)
        sources = {}
        for case in cfg["cases"]:
            key = case["world"]
            world = next((w for w in parent["worlds"] if w["key"] == key), None)
            if world is None or world["seed"] != case["seed"]:
                raise ValueError("Branch seed is not the declared sealed world")
            seal = previous.completed(key, world)
            if (
                seal is None
                or seal["report_id"] != audit["seals"][key]
                or seal["result"]["outcomes"]["boss"] != "act1_loss"
            ):
                raise ValueError("Branch requires a completed, verified native loss")
            trace = previous.path(key) / "boss" / TRACE
            name = trace.relative_to(root).as_posix()
            sources[case["key"]] = (trace, {name: seal["sources"][name]})
            with closing(decisions(trace)) as rows:
                anchor = next(
                    (
                        frame
                        for line, frame, choice in rows
                        if line == case["line"] and choice is not None
                    ),
                    None,
                )
            if anchor is None or anchor["input_digest"] != case["input_digest"]:
                raise ValueError("Declared branch root differs from the sealed public trace")
        if mode == "preflight":
            return {
                "status": "saved_branch_roots_verified",
                "frozen_checks": before,
                "cases": cfg["cases"],
            }
        if mode == "verify":
            report = identified(store.workspace / "report.json")
            with tempfile.TemporaryDirectory(
                prefix="spireshift-combat-branch-verify-"
            ) as temporary:
                for case in cfg["cases"]:
                    key = case["key"]
                    seal = store.completed(key, case)
                    if seal is None or report["seals"][key] != seal["report_id"]:
                        raise ValueError("Saved branch seal is missing or differs")
                    raw = reconstruct(
                        ctx, case, sources[key][0], store.path(key), Path(temporary) / key, deadline
                    )
                    if any(not same(value, seal["result"][field]) for field, value in raw.items()):
                        raise ValueError(
                            "Saved branch result differs from the reconstructed evidence"
                        )
            if check_inputs(root, cfg, ctx) != before:
                raise ValueError("Frozen inputs differ after saved verification")
            return report
        with store.lock():
            if _running_games():
                raise ValueError("Close STS2 and wait for any other native worker to finish")
            if (store.workspace / "report.json").exists():
                raise ValueError("Use --verify for the completed combat branches")
            profile = _shared_snapshot(shared)
            results, seals = {}, {}
            for case in cfg["cases"]:
                key = case["key"]
                trace, pinned = sources[key]
                seal = store.completed(key, case)
                if seal is None:
                    target = store.begin(key, case)
                    result = play(ctx, case, trace, target, deadline)
                    if (
                        check_inputs(root, cfg, ctx) != before
                        or _shared_snapshot(shared) != profile
                        or _running_games()
                    ):
                        raise ValueError("Frozen inputs, shared profile or worker shutdown differs")
                    seal = store.commit(key, case, result, pinned)
                results[key], seals[key] = seal["result"], seal["report_id"]
                print(
                    f"{key} {results[key]['outcome']} with {results[key]['final_hp']} HP",
                    flush=True,
                )
            return write(
                store.workspace / "report.json",
                {
                    "schema_version": "native-a8-act1-combat-branch-result-v1",
                    "status": "combat_branches_verified",
                    "config_id": store.config_id,
                    "execution_id": ctx["execution_id"],
                    "saved_audit_id": audit["report_id"],
                    "objective": cfg["objective"],
                    "scope": SCOPE,
                    "results": results,
                    "seals": seals,
                    "frozen_checks": before,
                    "shared_profile_unchanged": True,
                    "optimizer_updates": 0,
                    "lessons_admitted": 0,
                },
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight", action="store_const", dest="mode", const="preflight")
    modes.add_argument("--verify", action="store_const", dest="mode", const="verify")
    modes.add_argument("--run", action="store_const", dest="mode", const="run")
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    cfg = json.loads((root / RECIPE).read_text())
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread launcher")
        if args.mode is None:
            if _running_games():
                raise ValueError("Close STS2 and wait for any other native worker to finish")
            if (root / cfg["workspace"] / "report.json").exists():
                raise ValueError("Use --verify for the completed combat branches")
            command = [
                "uv",
                "run",
                "--no-sync",
                "spireshift",
                "resources",
                "run",
                "--kind",
                "other",
                "--report",
                cfg["resource_report"],
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "1",
            ]
            for flag, key in (
                ("--max-wall-seconds", "wall_seconds"),
                ("--max-cpu-seconds", "cpu_seconds"),
                ("--max-memory-bytes", "resident_memory_bytes"),
                ("--max-storage-bytes", "storage_bytes"),
            ):
                command.extend([flag, str(CONTROL_LIMITS[key])])
            return subprocess.call(
                [*command, "--", "uv", "run", "--no-sync", "python", "-m", MODULE, "--run"],
                cwd=root,
            )
        result = branches(root, cfg, args.mode, started)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps(
                {"status": "stopped_preserving_evidence", "error": str(exc), "optimizer_updates": 0}
            )
        )
        return 2
    print(
        json.dumps(
            {key: result[key] for key in ("status", "frozen_checks", "report_id") if key in result}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
