"""Qualify archive replays with checked effects and the frozen game's boss map rules."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_batch_v2 as runner
from spireshift import native_a8_archive_batch_v4 as previous
from spireshift import native_a8_archive_effects_v5 as effects
from spireshift import native_a8_feedback_host as host
from spireshift import native_a8_replay_probe as replay
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_mix_session import Study, admit
from spireshift.native_a8_replay_source import Journal
from spireshift.native_compatibility_contract import local, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-qualification-v5.json"
SCHEMA = "native-a8-archive-batch-v5"
PROJECT = Path("mod/SpireShift.HeadlessBossMap")
ASSEMBLY = "SpireShift.HeadlessBossMap.dll"
ADAPTER = f"{batch.AREA}/boss-map-adapter-v2"
CONTROL = f"{batch.AREA}/boss-map-control-v1"
CONTROL_END = "Short boss map control verified combat entry"
REQUIRED = previous.REQUIRED | {
    "src/spireshift/native_a8_archive_batch_v5.py",
    "src/spireshift/native_a8_archive_effects_v5.py",
    "mod/SpireShift.HeadlessConfirmation/StartupHook.cs",
    f"{PROJECT}/BossMapTravel.cs",
    f"{PROJECT}/SpireShift.HeadlessConfirmation.csproj",
    "scripts/qualify-a8-archive-batch-v5.sh",
}


def adapter_study(base: Study, cfg: dict[str, Any]) -> Study:
    root = base.root
    path = root / ADAPTER / "report.json"
    if not path.exists():
        with patch.multiple(host, ADAPTER=ADAPTER, PROJECT=PROJECT, ASSEMBLY=ASSEMBLY):
            host.build_adapter(root)
    adapter = host.load_adapter(
        root, base.ctx, {"path": str(path.relative_to(root)), "sha256": _sha_file(path)}
    )
    replay.equal("boss map adapter bytes", cfg["boss_map_adapter_sha256"], adapter["sha256"])
    return replace(base, ctx={**base.ctx, "confirmation_adapter": adapter})


def check_saved_boss_map(prior: previous.Predecessor, visit: dict[str, Any]) -> dict[str, Any]:
    final = prior.final["public_input"]["context"]["interaction"]
    replay.equal("saved boss map owner", "map_navigation", final["kind"])
    surface = final["content"]["surface"]
    replay.equal(
        "saved travel gap",
        (True, False, []),
        (
            surface["travel_enabled"],
            surface["traveling"],
            surface["next_options"],
        ),
    )
    saved_map = None
    transcript = prior.trace.parent / "worker/private-transcript.jsonl.gz"
    for row in records(transcript):
        if row["request"] == {"cmd": "get_map"}:
            saved_map = row["response"]
    if saved_map is None:
        raise ValueError("Saved boss map read is missing")
    boss = saved_map["boss"]
    destination = {axis: boss[axis] for axis in ("col", "row")}
    (current,) = (node for node in saved_map["rows"][-1] if node["current"])
    replay.equal(
        "saved last-row boss route",
        (
            visit["act"],
            visit["floor"] - 1,
            visit["id"],
            visit["coord"],
            saved_map["current_coord"],
            [destination],
        ),
        (
            saved_map["context"]["act"],
            saved_map["context"]["total_floor"],
            boss["id"],
            f"{boss['col']},{boss['row']}",
            {axis: current[axis] for axis in ("col", "row")},
            current["children"],
        ),
    )
    return {"act": visit["act"], "floor": visit["floor"], "boss": boss["id"], **destination}


def replay_prefix(prior: previous.Predecessor, journal: Journal) -> int:
    cursor = count = 0
    for row in records(prior.trace):
        index, cursor, domain = replay.next_choice(
            row["frame"], journal, cursor, len(journal.intents)
        )
        replay.equal(
            "saved prefix choice and domain",
            (
                row["choice"]["action_index"],
                row["receipt"]["delivery_domain"],
            ),
            (index, domain),
        )
        count += 1
    replay.equal("saved prefix deliveries", prior.deliveries, count)
    return cursor


def map_control(
    base: Study,
    cfg: dict[str, Any],
    case: dict[str, Any],
    journal: Journal,
    prior: previous.Predecessor,
    cursor: int,
    destination: dict[str, Any],
    *,
    run: bool,
) -> dict[str, Any]:
    """Prove the changed route once from Neow, ending the diagnostic at the boss."""
    root, key = base.root, case["run_id"]
    directory = root / CONTROL / key / "archive-qualification-v1"
    evidence = root / CONTROL / "proof.json"
    if evidence.is_file():
        proof = identified(evidence)
        check_sources(root, proof["native_evidence"])
        replay.equal(
            "exact prior boss map control",
            (
                prior.report_id,
                cfg["boss_map_adapter_sha256"],
                destination,
            ),
            (proof["prior_report_id"], proof["adapter_sha256"], proof["destination"]),
        )
        return proof
    if not run:
        raise ValueError("Require the short boss map control before archive qualification")
    if directory.exists():
        raise ValueError("Preserve the incomplete boss map control for inspection")
    end = cursor + 1
    visit, encounter = journal.intents[cursor : end + 1]
    replay.equal(
        "boss entrance intent order", ("visit", "combat_start"), (visit.kind, encounter.kind)
    )

    def stop_at_boss(
        frame: dict[str, Any], declared: Journal, index: int, limit: int
    ) -> tuple[int | None, int, str]:
        if index == end:
            replay.match(frame, encounter, declared)
            raise ValueError(CONTROL_END)
        return effects.next_choice(frame, declared, index, limit)

    native = adapter_study(base, cfg)
    source = verified(root, case["source"])
    with (
        patch.multiple(
            replay,
            AREA=CONTROL,
            SAMPLE=key,
            SOURCE_SHA=case["source"]["sha256"],
            FULL_SECONDS=cfg["case_wall_seconds"],
            admit=lambda _: native,
            next_choice=stop_at_boss,
        ),
        previous.continuation(root, {key: prior}),
    ):
        report = replay.probe(root, journal, source, control=False, attempt=1)
    final = identified(directory / "last-frame.json")
    identity = json.loads((directory / "worker/identity.json").read_text())
    replay.equal(
        "native boss control evidence",
        (
            CONTROL_END,
            False,
            True,
            prior.deliveries + 1,
            0,
            cfg["boss_map_adapter_sha256"],
        ),
        (
            report["stop"]["error"],
            report["stop"]["delivery_uncertain"],
            report["clean_shutdown"],
            report["verified_native_deliveries"],
            report["optimizer_updates"],
            identity["initial_identity"]["confirmation_adapter_sha256"],
        ),
    )
    if not all(report["frozen_checks"].values()):
        raise ValueError("Boss map control failed the frozen-state checks")
    actions = iter(records(directory / replay.TRACE))
    for _ in range(prior.deliveries):
        next(actions)
    delivery = next(actions)
    public = delivery["frame"]["public_input"]
    (route,) = public["context"]["interaction"]["content"]["surface"]["next_options"]
    label = public["candidates"][delivery["choice"]["action_index"]]["label"]
    replay.equal(
        "public boss route",
        (destination["col"], destination["row"], "boss", "native"),
        (route["col"], route["row"], route["point_type"], delivery["receipt"]["delivery_domain"]),
    )
    replay.equal(
        "boss route delivery successor",
        final["observation"]["snapshot_id"],
        delivery["receipt"]["successor_snapshot_id"],
    )
    paths = [
        directory / name
        for name in (
            "report.json",
            "last-frame.json",
            replay.TRACE,
            "worker/identity.json",
            "worker/public-observations.jsonl.gz",
            "worker/public-receipts.jsonl.gz",
            "worker/answer-plan-deliveries.jsonl.gz",
            "worker/closed.json",
        )
    ]
    return write(
        evidence,
        {
            "status": "boss_map_route_verified",
            "prior_report_id": prior.report_id,
            "adapter_sha256": cfg["boss_map_adapter_sha256"],
            "destination": destination,
            "action": label,
            "native_report_id": report["report_id"],
            "verified_native_deliveries": report["verified_native_deliveries"],
            "native_evidence": {str(path.relative_to(root)): _sha_file(path) for path in paths},
            "frozen_checks": report["frozen_checks"],
            "optimizer_updates": 0,
        },
    )


def preflight(
    base: Study,
    cfg: dict[str, Any],
    screened: dict[str, tuple[Journal | None, dict[str, Any]]],
    *,
    control: bool,
) -> tuple[dict[str, previous.Predecessor], dict[str, Any]]:
    root = base.root
    cases = {case["run_id"]: case for case in cfg["cases"] if not case.get("saved")}
    replay.equal("sealed predecessor worlds", cases.keys(), cfg["clean_stops"].keys())
    replay.equal("frozen replay environment", base.ctx["environment_id"], cfg["environment_id"])
    locale = base.ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): value
        for kind in ("potion", "relic", "card")
        for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    priors, result = {}, {}
    for key, case in cases.items():
        journal = screened[key][0]
        if journal is None:
            raise ValueError(f"Archive {key} failed source screening")
        journal = replace(journal, reward_names=names)
        prior = previous.load_predecessor(root, cfg["clean_stops"][key], case)
        cursor = replay_prefix(prior, journal)
        facts = {"verified_prefix": prior.deliveries, "prior_report_id": prior.report_id}
        if key == cfg["boss_map_case"]:
            destination = check_saved_boss_map(prior, journal.intents[cursor].record)
            proof = map_control(base, cfg, case, journal, prior, cursor, destination, run=control)
            facts.update(next_choice=proof["action"], boss_map_proof_id=proof["report_id"])
        else:
            index, _, domain = replay.next_choice(
                prior.final, journal, cursor, len(journal.intents)
            )
            if index is None:
                raise ValueError(f"Archive {key} has no verified next choice")
            facts.update(
                next_choice=prior.final["public_input"]["candidates"][index]["label"],
                delivery_domain=domain,
            )
        priors[key], result[key] = prior, facts
    return priors, result


@contextmanager
def continuation(
    base: Study, cfg: dict[str, Any], priors: dict[str, previous.Predecessor]
) -> Iterator[None]:
    execution = base.root / batch.AREA / "execution"
    native = adapter_study(base, cfg)

    class ContinuationJournal(ChunkJournal):
        def begin(self, key: str, request: dict[str, Any]) -> Path:
            prior = priors.get(request.get("run_id", ""))
            if self.workspace == execution and key.startswith("seed-") and prior is not None:
                if not self.path(f"v4-{key}").exists():
                    raise ValueError("The archive seed has no preserved v4 attempt")
                return super().begin(
                    f"v5-{key}", {**request, "preceding_native_report": prior.report_id}
                )
            return super().begin(key, request)

    with (
        previous.continuation(base.root, priors),
        patch.object(batch, "ChunkJournal", ContinuationJournal),
        patch.object(replay, "admit", lambda _: native),
    ):
        yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", nargs="?", default=RECIPE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true", help="Run the declared archive worlds")
    mode.add_argument(
        "--check-boss-map", action="store_true", help="Run one short native route control"
    )
    args = parser.parse_args()
    root = Path.cwd()
    try:
        recipe = local(root, args.recipe)
        with patch.multiple(runner, SCHEMA=SCHEMA, MATCHER=effects.MATCHER, REQUIRED=REQUIRED):
            cfg = runner.load(root, recipe)
        base = admit(root)
        screened = {case["run_id"]: effects.screen(root, case) for case in cfg["cases"]}
        with effects.installed():
            priors, report = preflight(base, cfg, screened, control=args.check_boss_map)
            if args.run:
                with continuation(base, cfg, priors):
                    result = batch.execute(root, recipe, cfg, screened)
            else:
                result = {
                    "status": "archive_qualification_ready",
                    "preceding_choices": report,
                    "optimizer_updates": 0,
                    "training_admission_granted": False,
                }
        check_sources(root, cfg["replay_implementation"])
    except (*batch.FAILURES, subprocess.SubprocessError) as exc:
        result = {
            "status": "stopped_preserving_evidence",
            "error": str(exc),
            "optimizer_updates": 0,
            "training_admission_granted": False,
        }
    print(json.dumps(result))
    return 2 if result["status"] == "stopped_preserving_evidence" else 0


if __name__ == "__main__":
    raise SystemExit(main())
