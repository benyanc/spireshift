"""Execute and seal one bounded representation-comparison unit."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_policy_updates import update
from spireshift.native_structured_checks import check
from spireshift.native_structured_game import batch
from spireshift.native_structured_model import extend
from spireshift.native_structured_state import load, save
from spireshift.native_structured_training import prepare


def execute(
    root: Path,
    context: dict[str, Any],
    store: ChunkJournal,
    task: dict[str, Any],
    request: dict[str, Any],
    done: dict[str, dict[str, Any]],
    deadline: float,
    native: Any,
) -> None:
    cfg, score = context["config"], context["score"]
    target = store.begin(task["key"], request)
    if task["kind"] == "qualify":
        result = {"kind": "qualify", **check(root, context), "games_recorded": 0}
        atomic_json(target / "input-checks.json", result)
    else:
        if task["kind"] == "import":
            model, adam = extend(
                context["models"][task["player"]],
                context["adams"][task["player"]],
                tuple(context["layout"]["columns"]),
                task["arm"],
            )
        else:
            parent = done[task["state"]]
            model, adam, sid = load(root / parent["state_path"])
            if sid != request["predecessor_state_id"] or adam.steps != parent["optimizer_steps"]:
                raise ValueError("Do not reset or substitute a saved model/Adam state")
        result = {
            "kind": task["kind"],
            "player": task["player"],
            "arm": task["arm"],
            "games_recorded": 0,
        }
        if task["kind"] in {"import", "fit"}:
            if task["kind"] == "fit":
                paths = [root / name for key in task["collections"] for name in done[key]["paths"]]
                samples, credit = prepare(paths, model, score, cfg, task["seeds"], task["round"])
                prior_steps = adam.steps
                model, adam, work = update(model, adam, samples, task["round"])
                result.update(round=task["round"], new_optimizer_steps=adam.steps - prior_steps)
                atomic_json(target / "credit.json", credit)
                atomic_json(target / "work.json", work)
                print(
                    f"Player {task['player']} / {task['arm']}, round {task['round']}: "
                    f"{credit['clean_complete_training_games']}/{credit['scheduled_games']} "
                    "clean games, "
                    f"{credit['decisions']} decisions, {adam.steps - prior_steps} updates.",
                    flush=True,
                )
                del samples
            saved = save(target / "state.json", model, adam)
            result.update(
                state_path=str((target / "state.json").relative_to(root)),
                state_id=saved["state_id"],
                model_id=model.model_id,
                optimizer_steps=adam.steps,
            )
        else:
            q, inputs = native
            account = Path.home() / "Library/Application Support/SlayTheSpire2"
            before = _shared_snapshot(account)
            training = task["kind"] == "collect"
            report = batch(
                q,
                cfg,
                inputs,
                target / "games",
                task["seeds"] if training else [task["seed"]],
                model,
                score,
                training,
                deadline,
            )
            checks = immutable_checks(q, inputs)
            checks["account_profile_unchanged"] = before == _shared_snapshot(account)
            if not all(checks.values()):
                raise ValueError("A frozen input or real account profile changed")
            if training:
                result.update(
                    **report, round=task["round"], collection_id=manifest_identifier(report)
                )
            else:
                result.update(**report["outcomes"][0], games_recorded=1)
            result["checks"] = checks
    if time.monotonic() >= deadline:
        raise TimeoutError("Unit exceeded its finite session; preserve unfinished evidence")
    store.commit(task["key"], request, result)
