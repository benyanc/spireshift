"""Verify the stopped Act 1 study and reproduce its decoder failure from saved evidence."""

from __future__ import annotations

import fcntl
import json
import subprocess
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_rescue_curriculum import ARMS, assess, first_change
from spireshift.native_a8_rescue_game import TRACE, Progress, decisions, public_state, verify
from spireshift.native_a8_rescue_inputs import AREA, declaration, freeze, load
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

ATTEMPT = 1794026671116975000
REGRESSION = "scripts/engine-generated-choice-belt-regression-v1.mjs"


def episode_summary(path: Path, episode: dict[str, Any]) -> dict[str, Any]:
    progress = Progress()
    interventions: Counter[str] = Counter()
    boss = None
    native = 0
    for _, frame, delivered in decisions(path / TRACE):
        outcome = progress.observe(frame)
        run, player, interaction = public_state(frame)
        context = interaction["content"].get("context", {})
        if interaction["kind"] == "combat_turn" and context.get("encounter_type") == "boss":
            if boss is None:
                boss = {"floor": run["floor"], "entry_hp": player["hp"]}
            boss["last_round"] = context["round"]
            boss["remaining_enemy_hp"] = [
                {"enemy": enemy["definition_id"], "hp": enemy["hp"]} for enemy in context["enemies"]
            ]
        if delivered is None:
            if outcome != episode["outcome"] or native != episode["verified_native_deliveries"]:
                raise ValueError("Sealed Act 1 outcome or delivery count differs")
            return {
                "outcome": outcome,
                "final_floor": run["floor"],
                "final_hp": player["hp"],
                "boss": boss,
                "native_deliveries": native,
                "interventions": dict(interventions),
            }
        choice, receipt = delivered["choice"], delivered["receipt"]
        index, domain = choice["action_index"], receipt["delivery_domain"]
        progress.delivered(frame, index, domain)
        if domain == "native":
            native += 1
            if "intervention" in choice:
                interventions[choice["intervention"]] += 1
    raise ValueError("Missing sealed Act 1 final frame")


def stopped_case(
    root: Path, ctx: dict[str, Any], path: Path, stop: dict[str, Any]
) -> dict[str, Any]:
    case = stop["case"]
    marker = json.loads((path / "active.json").read_text())
    if (
        marker["request"] != case
        or marker["config_id"] != ctx["config_id"]
        or (path / "done.json").exists()
        or (path / "teacher").exists()
    ):
        raise ValueError("Unexpected interrupted-world evidence")
    original = identified(path / "original/report.json")
    fitted = path / "fitted/worker"
    observed = deque(records(fitted / "public-observations.jsonl.gz"), maxlen=1).pop()
    receipts = list(records(fitted / "public-receipts.jsonl.gz"))
    offered = deque(records(path / "fitted" / TRACE), maxlen=1).pop()
    sent = deque(records(fitted / "private-transcript.jsonl.gz"), maxlen=1).pop()
    stopped = json.loads((fitted / "native-process-stop.json").read_text())
    identity = json.loads((fitted / "identity.json").read_text())
    before = offered["frame"]
    _, _, interaction = public_state(before)
    if (
        original["case"] != case
        or original["outcome"] != "act1_loss"
        or not original["shutdown"]["clean_exit"]
        or not (fitted / "active.json").is_file()
        or (fitted / "closed.json").exists()
        or stopped["process_id"] != identity["runtime_identity"]["process_id"]
        or len(receipts) != observed["index"]
        or any(row["delivery"] != "delivered" for row in receipts)
        or offered["kind"] != "policy_input"
        or receipts[-1]["successor_snapshot_id"] != observed["snapshot"]["snapshot_id"]
        or observed["snapshot"]["snapshot_id"] != before["observation"]["snapshot_id"]
        or interaction["kind"] != "combat_turn"
        or not any(
            row["label"] == "Use Attack Potion" for row in before["public_input"]["candidates"]
        )
        or sent["request"].get("action") != "use_potion"
        or sent["response"].get("decision") != "generated_card_choice"
    ):
        raise ValueError("Interrupted prefix or missing native receipt differs")
    projection = identity["shared_projection"]
    if (
        not Path(projection["directory"])
        .resolve()
        .is_relative_to(root / "artifacts/engine-runtime-code")
    ):
        raise ValueError("Unexpected projection cache")
    check = subprocess.run(
        [ctx["node"], str(root / REGRESSION)],
        input=json.dumps(
            {
                "projection": {
                    "shared_projection": projection,
                    "projection": ctx["native"]["projection"],
                },
                "state": sent["response"],
            }
        ),
        capture_output=True,
        check=True,
        text=True,
        timeout=20,
    )
    return {
        "case": case,
        "original_loss_report_id": original["report_id"],
        "fitted_acknowledged_prefix": len(receipts),
        "fitted_unacknowledged_action": "Use Attack Potion",
        "native_process_stopped": stopped,
        "teacher_started": False,
        "saved_projection_regression": json.loads(check.stdout),
        "source_sha256": {
            str(file.relative_to(root)): _sha_file(file)
            for file in (
                path / "active.json",
                path / "original/report.json",
                path / "fitted" / TRACE,
                fitted / "active.json",
                fitted / "identity.json",
                fitted / "native-process-stop.json",
                fitted / "public-observations.jsonl.gz",
                fitted / "public-receipts.jsonl.gz",
                fitted / "private-transcript.jsonl.gz",
            )
        },
    }


def audit(root: Path, cfg: dict[str, Any], out: Path, deadline: float) -> dict[str, Any]:
    ctx = load(root, cfg, control=False)
    store = ChunkJournal(root, cfg)
    attempt = identified(store.workspace / f"attempt-{ATTEMPT}.json")
    launch = identified(store.workspace / f"launch-{ATTEMPT}.json")
    resource = identified(root / f"artifacts/resources/a8-act1-rescue-v1-{ATTEMPT}.json")
    checks = freeze(root, ctx)
    if (
        attempt["launch_id"] != launch["report_id"]
        or attempt["config_id"] != launch["config_id"]
        or launch["config_id"] != ctx["config_id"]
        or attempt["status"] != "stopped_preserving_evidence"
        or resource["status"] != "failed"
        or resource["exit_code"] != 2
        or resource["cap"] is not None
        or attempt["bank_id"] is not None
        or attempt["optimizer_updates"] != 0
        or checks != launch["frozen_checks"]
        or checks != attempt["frozen_checks"]
        or not attempt["shared_profile_unchanged"]
    ):
        raise ValueError("Saved owner attempt or its frozen inputs differ")

    broken = attempt["stop"]["case"]
    missing, seals, rows, games, replayed = [], {}, {}, {}, {}
    for phase, planned in cfg["worlds"].items():
        rows[phase] = []
        for case in planned:
            key = case["key"]
            if case == broken:
                continue
            sealed = store.completed(key, case)
            if sealed is None:
                missing.append(key)
                continue
            seals[key] = sealed["report_id"]
            row = sealed["result"]
            rows[phase].append(row)
            path = store.path(key)
            games[key] = {
                arm: episode_summary(path / arm, episode)
                for arm, episode in row["episodes"].items()
            }
            if not row["strict_rescue_confirmed"]:
                continue
            change = first_change(path / "fitted" / TRACE, path / "teacher" / TRACE)
            if change != row["first_change_from_fitted"] or set(row["episodes"]) != {
                *ARMS,
                "confirmation",
            }:
                raise ValueError("Strict rescue is missing matching inputs or a confirmation")
            replayed[key] = {}
            for arm, episode in row["episodes"].items():
                target = out / "replay" / key / arm
                target.mkdir(parents=True)
                (target / TRACE).symlink_to(path / arm / TRACE)
                (target / "worker").symlink_to(path / arm / "worker", target_is_directory=True)
                raw = verify(ctx, case, arm, target, deadline)
                if any(episode[name] != value for name, value in raw.items()):
                    raise ValueError("Strict rescue raw replay differs from its seal")
                replayed[key][arm] = raw
            if (
                replayed[key]["teacher"]["semantic_trajectory_sha256"]
                != replayed[key]["confirmation"]["semantic_trajectory_sha256"]
            ):
                raise ValueError("Strict rescue confirmation does not reproduce")

    assessments = {
        "qualification": assess("qualify", cfg["worlds"]["qualify"], rows["qualify"]),
        "collection": assess("collect", cfg["worlds"]["collect"], rows["collect"]),
    }
    if (
        any(value != attempt[phase] for phase, value in assessments.items())
        or {p.name for p in (store.workspace / "chunks").iterdir()} != {*seals, broken["key"]}
        or (store.workspace / "bank.json").exists()
    ):
        raise ValueError("The stopped-run denominator or bank differs")
    failure = stopped_case(root, ctx, store.path(broken["key"]), attempt["stop"])
    if freeze(root, ctx) != checks:
        raise ValueError("Frozen inputs changed during the saved audit")
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-act1-rescue-stopped-audit-v1",
            "status": "stopped_act1_rescue_study_verified",
            "owner_attempt_id": attempt["report_id"],
            "owner_resource_id": resource["report_id"],
            "config_id": ctx["config_id"],
            "environment_id": ctx["environment_id"],
            "frozen_checks": checks,
            "seals": seals,
            **assessments,
            "sealed_episodes": sum(map(len, games.values())),
            "sealed_deliveries": sum(
                g["native_deliveries"] for arms in games.values() for g in arms.values()
            ),
            "episodes": games,
            "raw_replayed_rescues": replayed,
            "unstarted_worlds": missing,
            "failure": failure,
            "bank_id": None,
            "qualification_worlds_trainable": False,
            "new_games": 0,
            "optimizer_updates": 0,
            "automatic_follow_up": False,
        },
    )


if __name__ == "__main__":
    root = Path.cwd()
    cfg = declaration(root)
    out = root / AREA / "stopped-audit-v2"
    with (root / cfg["workspace"] / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        out.mkdir(parents=True, exist_ok=False)
        report = audit(root, cfg, out, time.monotonic() + 230)
    print(
        json.dumps(
            {k: report[k] for k in ("status", "sealed_episodes", "sealed_deliveries", "report_id")}
        )
    )
