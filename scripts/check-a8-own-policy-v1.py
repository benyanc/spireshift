"""Check full-menu model control using saved menus and fresh natural games."""

from __future__ import annotations

import fcntl
import json
import os
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_boss_game import worker
from spireshift.native_a8_crash_resume import RECIPE, relocated_context
from spireshift.native_a8_ordinary_session import require_short, saved_check
from spireshift.native_a8_own_policy import CONTRACT, OwnPolicy
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_rescue_inputs import GAME_LIMITS
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_win4_game import episode, prepare, write
from spireshift.native_win4_plan import AnswerPolicy

WORKSPACE = "artifacts/native-a8-own-policy/control-v1"
PAIRED = "docs/evidence/native-a8-paired-finals-result-v1.json"
CASES: tuple[dict[str, Any], ...] = (
    {"key": "own-policy-p2", "player": 2, "seed": "SP1RESH1FTA8OWNC001"},
    {"key": "own-policy-p3", "player": 3, "seed": "SP1RESH1FTA8OWNC002"},
)


def bound_menus(directory: Path) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    raw = records(directory / "worker/public-observations.jsonl.gz")
    for (_, frame, delivered), row in zip(decisions(directory / TRACE), raw, strict=True):
        snapshot = row["snapshot"]
        if snapshot["snapshot_id"] != frame["observation"]["snapshot_id"]:
            raise ValueError("The shared menu must use its exact native observation")
        if delivered is None:
            continue
        native = snapshot["bound_actions"]
        actions = frame["actions"]
        if (
            native["status"] != "complete"
            or native["total_count"] != len(native["actions"])
            or sorted(a["raw_index"] for a in actions) != list(range(len(native["actions"])))
            or any(
                a["bound_action_id"] != native["actions"][a["raw_index"]]["bound_action_id"]
                for a in actions
            )
            or len(frame["public_input"]["candidates"]) != len(actions)
        ):
            raise ValueError("A current native action did not reach the shared menu")
        yield frame, delivered["choice"]


def saved_menus(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = identified(root / PAIRED)
    source = identified(verified(root, evidence["saved_recovery"]))
    workspace = root / "artifacts/native-a8-paired/study-v1"
    store = ChunkJournal(root, json.loads((workspace / "config-at-launch.json").read_text()))
    if source["config_id"] != store.config_id:
        raise ValueError("The saved paired menu evidence differs")
    families: Counter[str] = Counter()
    forced = omitted = restored = 0
    with (workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        for key, seal_id in source["seals"].items():
            directory = store.path(key)
            request = json.loads((directory / "active.json").read_text())["request"]
            seal = store.completed(key, request)
            if seal is None or seal["report_id"] != seal_id:
                raise ValueError("Require the exact sealed paired loss")
            case = seal["result"]
            legacy = ShopNavigation()
            for frame, choice in bound_menus(directory):
                public = frame["public_input"]
                _, indices, is_forced = legacy.view(public)
                families[public["context"]["interaction"]["kind"]] += 1
                missing = len(frame["actions"]) - len(indices)
                if (
                    choice["navigation_only"] is not is_forced
                    or choice["action_index"] not in indices
                ):
                    raise ValueError("The saved shop routing did not reconstruct")
                if missing:
                    policy = OwnPolicy(
                        ctx["models"][case["player"], case["arm"]], ctx["score"], case["world"]
                    )
                    policy.choose(frame)
                    restored += 1
                omitted += missing
                forced += is_forced
                legacy.advance(public, choice["action_index"])
    return {
        "source_report_id": source["report_id"],
        "sealed_games": len(source["seals"]),
        "exact_menus": sum(families.values()),
        "families": dict(families),
        "legacy_forced_choices": forced,
        "legacy_omitted_options": omitted,
        "affected_menus_scored_in_full": restored,
    }


def own_policy(
    context: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
) -> AnswerPolicy:
    if variant != "own" or start["kind"] != "natural_training":
        raise ValueError("This control requires model-only play from a fresh normal start")
    return AnswerPolicy(OwnPolicy(model, context["score"], start["seed"]))


def main() -> None:
    root, started = Path.cwd(), time.monotonic()
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise ValueError("Use the pinned single-thread numerical runtime")
    crash = json.loads((root / RECIPE).read_text())
    check_sources(root, crash["implementation"])
    previous = json.loads(verified(root, crash["continuation_recipe"]).read_text())
    original = json.loads(verified(root, previous["previous_recipe"]).read_text())
    ctx, runtime = relocated_context(root, original, crash["node"])
    require_short(root, ctx, saved_check(root, ctx))
    audit = saved_menus(root, ctx)
    print(json.dumps(audit), flush=True)
    if _running_games():
        raise ValueError("Close STS2 and wait for any other native worker")
    before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    store = ChunkJournal(
        root,
        {
            "workspace": WORKSPACE,
            "cases": list(CASES),
            "node": crash["node"],
            "source_report_id": audit["source_report_id"],
            "implementation": {
                "scripts/check-a8-own-policy-v1.py": _sha_file(Path(__file__)),
                "src/spireshift/native_a8_own_policy.py": _sha_file(
                    root / "src/spireshift/native_a8_own_policy.py"
                ),
            },
        },
    )
    context = {**ctx, "config": {"plan": GAME_LIMITS}}
    outcomes = {}
    with store.lock():
        for case in CASES:
            key = case["key"]
            target = store.begin(key, case)
            deadline = started + 265
            start = prepare(
                context,
                {
                    **case,
                    "entry": "natural",
                    "partition": "own_policy_diagnostic",
                    "seed_pool": [case["seed"]],
                },
                target,
                deadline,
            )
            with (
                patch("spireshift.native_win4_game.worker", worker),
                patch("spireshift.native_win4_game.policy", own_policy),
            ):
                result = episode(
                    context,
                    start,
                    "own",
                    target,
                    deadline,
                    model=ctx["models"][case["player"], "original"],
                )
            count = 0
            for _, choice in bound_menus(target):
                if (
                    choice["policy_contract"] != CONTRACT
                    or choice["behavior"] != "sampled_softmax"
                    or choice["effective_input_id"] != choice["public_input_id"]
                    or choice["navigation_only"]
                    or choice.get("intervention") is not None
                    or choice["optimizer_updates"] != 0
                ):
                    raise ValueError("The trajectory contains a non-model or filtered choice")
                count += 1
            if (
                count
                != result["actual_deliveries_independently_verified"]
                + result["local_answer_factors"]
            ):
                raise ValueError("The full-menu and native answer counts disagree")
            if result["status"] == "complete" and (
                not result["native_terminal"]
                or result["native_ending"]["native_ending_evidence_agrees"] is not True
            ):
                raise ValueError(
                    "Natural own-policy play requires genuine native terminal evidence"
                )
            boundary(root, ctx, before, profile)
            seal = store.commit(key, case, result)
            outcomes[key] = {
                "seal_id": seal["report_id"],
                "status": result["status"],
                "win": result["full_run_win"],
                "terminal": result["native_terminal"],
                "verified_native_decisions": result["actual_deliveries_independently_verified"],
                "local_answer_factors": result["local_answer_factors"],
                "full_menus": count,
            }
            print(key, outcomes[key], flush=True)
        if execution_runtime(ctx["node"]) != runtime:
            raise ValueError("The numerical runtime changed")
        checked = write(
            store.workspace / "report.json",
            {
                "status": "own_policy_short_verified"
                if all(outcome["status"] == "complete" for outcome in outcomes.values())
                else "own_policy_short_incomplete",
                "policy_contract": CONTRACT,
                "saved_menus": audit,
                "new_games": outcomes,
                "config_id": store.config_id,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                **NO_UPDATES,
            },
        )
    print(json.dumps(checked))


if __name__ == "__main__":
    main()
