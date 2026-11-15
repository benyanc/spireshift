"""Compare mixed rest-site choices on the two frozen execution hosts."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host, native_systematic_live_v1
from spireshift.engine_connector import _verify_toolchain, load_connector_qualification_config
from spireshift.engine_profile import load_profile_policy, verify_benchmark_progress
from spireshift.engine_qualification import _sha_file
from spireshift.engine_working_app import load_working_app_policy, preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_rescue_game import receipt
from spireshift.native_compatibility_contract import verified
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_flow_verification_v12 import records
from spireshift.native_mixed_rest import REST, Case, control, verify
from spireshift.native_shared_transport import JsonLines
from spireshift.native_systematic_live_v1 import ScriptedPolicy, append, compare_frames
from spireshift.native_systematic_selectors_v2 import CONVERTER, PROJECTION
from spireshift.native_systematic_session_v1 import official_prefix
from spireshift.native_win4_game import write

SCRIPT = "engine-mixed-rest-worker-v1.mjs"
CONNECTOR = "configs/engine-qualification/sts2-v0.111.0-connector-rest-site-readiness-v32.json"
BOOTSTRAP = "configs/native-compatibility/sts2-v0.111.0-a8-live-control-v1.json"


class RestWorker(FeedbackWorker):
    def __init__(self, ctx: dict[str, Any], directory: Path) -> None:
        with patch.multiple(native_a8_feedback_host, SCRIPT=SCRIPT, PROJECTION=PROJECTION):
            super().__init__(ctx, directory)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "selector_fixture": True}
        return super().request(command, timeout=timeout, **values)


def conversion(ctx: dict[str, Any], log: Path) -> JsonLines:
    root = ctx["qualification"].root
    return JsonLines(root, [ctx["node"], str(root / "scripts" / CONVERTER)], log)


def official_context(ctx: dict[str, Any]) -> dict[str, Any]:
    qualification = ctx["qualification"]
    root = qualification.root
    connector = load_connector_qualification_config(root / CONNECTOR, qualification)
    _verify_toolchain(connector)
    inputs = json.loads((root / BOOTSTRAP).read_text())["inputs"]
    progress = verified(root, inputs["benchmark_progress"])
    verify_benchmark_progress(
        progress, load_profile_policy(verified(root, inputs["profile_policy"]), qualification)
    )
    return {
        **ctx,
        "connector": connector,
        "working_app": load_working_app_policy(
            verified(root, inputs["working_app"]), qualification
        ),
        "config": {**ctx["config"], "node": ctx["node"]},
        "progress": progress,
    }


def prepare(ctx: dict[str, Any], case: Case, directory: Path) -> Path:
    directory.mkdir()
    worker = RestWorker(ctx, directory / "setup")
    try:
        result = worker.request(
            "prepare",
            seed=case.seed,
            relics=list(case.relics),
            deck=list(case.deck),
            belt=list(case.belt),
            timeout=25,
        )
        close = worker.close()
        if not close["clean_exit"] or close["runtime_errors"]:
            raise ValueError("Rest fixture preparation did not exit cleanly")
    finally:
        worker.stop()
    save = result["save"]
    if save["rng"]["seed"] != case.seed:
        raise ValueError(f"{case.name}: diagnostic save seed differs from the declared seed")
    (player,) = save["players"]
    if case.girya:
        (girya,) = [r for r in player["relics"] if r["id"] == "RELIC.GIRYA"]
        (counter,) = [p for p in girya["props"]["ints"] if p["name"] == "TimesLifted"]
        if counter["value"] != 0:
            raise ValueError(
                "Require the exact unused native Girya before setting its diagnostic counter"
            )
        counter["value"] = case.girya
    if case.clone:
        # Serialize one already acquired Ancient relic and the card enchanted
        # by its acquisition so the test starts at its later rest-site effect.
        player["relics"].append({"id": "RELIC.PAELS_GROWTH", "floor_added_to_deck": 1})
        card = player["deck"][0]
        if card["id"] != "CARD.STRIKE_IRONCLAD" or card.get("enchantment"):
            raise ValueError("Require the declared plain physical card to receive Clone")
        card["enchantment"] = {"id": "ENCHANTMENT.CLONE", "amount": 4}
    path = directory / "fixture.save"
    atomic_json(path, save)
    write(
        directory / "fixture-provenance.json",
        {
            "case": asdict(case),
            "source_sha256": result["source_sha256"],
            "save_sha256": _sha_file(path),
            "privileged_fixture": True,
            "training_allowed": False,
            "shutdown": close,
        },
    )
    return path


def select(frame: dict[str, Any], step: str) -> int:
    public = frame["public_input"]
    kind = public["context"]["interaction"]["kind"]
    matched = [i for i, c in enumerate(public["candidates"]) if control(c, kind) == step]
    if len(matched) != 1:
        raise ValueError(f"{kind} did not offer one exact {step} control: {matched}")
    return matched[0]


def native_prefix(
    ctx: dict[str, Any],
    case: Case,
    fixture: Path,
    directory: Path,
    deadline: float,
) -> list[dict[str, Any]]:
    directory.mkdir()
    worker = RestWorker(ctx, directory / "worker")
    bridge = conversion(ctx, directory / "converter.log")
    try:
        current = worker.request("load", seed=case.seed, save_json=fixture.read_text(), timeout=25)
        frames = []
        for step in (*case.steps, None):
            frame = bridge.project(current["snapshot"], current["reads"], None, deadline)
            frames.append(frame)
            append(directory / "frames.jsonl.gz", frame)
            if step is None:
                break
            i = select(frame, step)
            binding = frame["actions"][i]
            choice = {"binding_id": frame["binding_id"], "action_index": i}
            current = worker.request(
                "step",
                snapshot_id=frame["observation"]["snapshot_id"],
                action_index=binding["raw_index"],
                timeout=min(20, max(0.1, deadline - time.monotonic())),
            )
            if current["delivery_domain"] != "native":
                raise ValueError("The declared rest action did not reach the native game")
            ack = receipt(frame, choice, "native", current["snapshot"]["snapshot_id"])
            bridge.commit(choice, ack, deadline)
            append(directory / "deliveries.jsonl.gz", {"choice": choice, "receipt": ack})
        native_receipts = records(directory / "worker/public-receipts.jsonl.gz")
        expected = zip(frames[:-1], frames[1:], case.steps, strict=True)
        for (before, after, step), raw in zip(expected, native_receipts, strict=True):
            binding = before["actions"][select(before, step)]
            if (
                raw["delivery"] != "delivered"
                or raw["action"]["bound_action_id"] != binding["bound_action_id"]
                or raw["snapshot_id"] != before["observation"]["snapshot_id"]
                or raw["successor_snapshot_id"] != after["observation"]["snapshot_id"]
            ):
                raise ValueError("The native delivery journal differs from the compared frames")
        stopped = worker.close()
        if not stopped["clean_exit"] or stopped["runtime_errors"]:
            raise ValueError("The native rest worker did not shut down cleanly")
        bridge.close()
        return frames
    finally:
        bridge.stop()
        worker.stop()


def official_frames(
    ctx: dict[str, Any],
    source: Path,
    case: Case,
    policy: ScriptedPolicy,
    deadline: float,
) -> list[dict[str, Any]]:
    """Replay raw Connector inputs through the very same converter as the learner."""
    observations = []
    receipts: dict[str, list[dict[str, Any]]] = {}
    for row in records(source / "live-public.jsonl.gz"):
        if row["kind"] in {"policy_input", "diagnostic_successor"}:
            observations.append(row)
        if row["kind"] == "receipt":
            receipts.setdefault(row["before_snapshot_id"], []).append(row)
    frames = []
    if len(policy.frames) != len(case.steps) + 1 or len(observations) != len(policy.frames):
        raise ValueError("The Connector lacks its complete observation and delivery chain")
    bridge = conversion(ctx, source / "learner-converter.log")
    try:
        binding_from_previous = None
        for i, (obs, live) in enumerate(zip(observations, policy.frames, strict=True)):
            snapshot, reads = obs["snapshot"], obs["reads"]
            snapshot_id = snapshot["snapshot_id"]
            if live["observation"]["snapshot_id"] != snapshot_id:
                raise ValueError("The Connector journal used a different policy snapshot")
            if binding_from_previous is not None:
                before, choice = binding_from_previous
                bridge.commit(choice, receipt(before, choice, "native", snapshot_id), deadline)
            frame = bridge.project(snapshot, reads, None, deadline)
            frames.append(frame)
            if i == len(case.steps):
                break
            step = case.steps[i]
            index = select(frame, step)
            live_id = live["actions"][select(live, step)]["bound_action_id"]
            actions = frame["actions"]
            (raw,) = receipts[snapshot_id]
            if (
                raw["receipt"]["delivery"] != "delivered"
                or raw["action"]["bound_action_id"] != live_id
                or actions[index]["bound_action_id"] != live_id
            ):
                raise ValueError(
                    "The Connector receipt did not deliver the same current legal choice"
                )
            binding_from_previous = (
                frame,
                {"binding_id": frame["binding_id"], "action_index": index},
            )
        bridge.close()
    finally:
        bridge.stop()
    return frames


def run_cases(
    ctx: dict[str, Any],
    checks: Iterable[Case],
    directory: Path,
    deadline: float,
    *,
    paired: bool,
) -> Iterator[dict[str, Any]]:
    selected = tuple(checks)
    earlier = None
    if paired:
        for case in selected:
            try:
                canonical_seed(case.seed)
            except ValueError as exc:
                raise ValueError(f"{case.name}: {exc}") from exc
        earlier = official_context(ctx)
        preflight_working_app(earlier["working_app"])
    directory.mkdir()
    root = ctx["qualification"].root
    fixtures: dict[str, Path] = {}
    for case in selected:
        if time.monotonic() + (55 if paired else 4) >= deadline:
            raise TimeoutError("Insufficient time for another complete rest control")
        target = directory / case.name
        target.mkdir()
        if case.seed not in fixtures:
            fixtures[case.seed] = prepare(ctx, case, target / "preparation")
        fixture = fixtures[case.seed]
        local_limit = min(deadline, time.monotonic() + (145 if paired else 40))
        native = native_prefix(ctx, case, fixture, target / "native", local_limit)
        effects = verify(case, native)
        result: dict[str, Any] = {"case": asdict(case), "native_effects": effects}
        if earlier is not None:
            policy = ScriptedPolicy(list(case.steps))
            checkpoint = {
                **earlier,
                "config": {**earlier["config"], "maximum_decisions": len(case.steps)},
            }
            with patch.object(native_systematic_live_v1, "select_action", select):
                official = official_prefix(
                    checkpoint,
                    {
                        "seed": case.seed,
                        "family": REST,
                        "fixture_save": {
                            "path": str(fixture.relative_to(root)),
                            "sha256": _sha_file(fixture),
                        },
                    },
                    target / "official",
                    policy,
                    local_limit,
                )
            result["official"] = official
            if official["status"] != "official_prefix_pass":
                write(target / "report.json", {**result, "status": "blocked"})
                detail = official["probe"].get("error") or official["error"]
                raise ValueError(f"{case.name}: {detail}")
            projected = official_frames(ctx, target / "official", case, policy, deadline)
            for frame in projected:
                append(target / "official/learner-frames.jsonl.gz", frame)
            result["official_effects"] = verify(case, projected)
            result["paired_inputs"] = compare_frames(native, projected)
            if result["official_effects"] != effects or not result["paired_inputs"]["equal"]:
                write(target / "report.json", {**result, "status": "blocked"})
                difference = result["paired_inputs"]["first_difference"]
                raise ValueError(f"{case.name}: native and official differ: {difference}")
        checked = write(target / "report.json", {**result, "status": "verified"})
        print(f"{'Paired' if paired else 'Native'} rest check {case.name} verified", flush=True)
        yield checked
