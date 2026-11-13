"""One sealed experience unit; no mutations of parent checkpoints or historical recipes."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_experience_game import batch
from spireshift.native_experience_training import prepare
from spireshift.native_policy_updates import qualify, update
from spireshift.native_structured_state import load, save


def execute(
    root: Path,
    context: dict[str, Any],
    journal: ChunkJournal,
    task: dict[str, Any],
    request: dict[str, Any],
    done: dict[str, dict[str, Any]],
    deadline: float,
    native: Any,
) -> None:
    cfg, score = context["config"], context["score"]
    target = journal.begin(task["key"], request)
    if task["kind"] == "qualify":
        checks = [qualify(context["models"][p], context["adams"][p]) for p in (2, 3)]
        result = {
            "kind": "qualify",
            "passed": all(r["passed"] for r in checks),
            "checks": checks,
            "games_recorded": 0,
        }
        atomic_json(target / "policy-checks.json", result)
    else:
        if task["kind"] == "import":
            model = context["models"][task["player"]]
            adam = Adam.from_mapping(
                context["adams"][task["player"]].as_dict(), model.parameter_count
            )
        else:
            parent = done[task["state"]]
            model, adam, sid = load(root / parent["state_path"])
            if sid != request["predecessor_state_id"] or adam.steps != parent["optimizer_steps"]:
                raise ValueError("Do not substitute weights or reset any saved Adam state")
        result = {
            "kind": task["kind"],
            "player": task["player"],
            "arm": task["arm"],
            "games_recorded": 0,
        }
        if task["kind"] in {"import", "fit"}:
            if task["kind"] == "fit":
                paths = [root / n for k in task["collections"] for n in done[k]["paths"]]
                outcomes = [r for k in task["collections"] for r in done[k]["outcomes"]]
                samples, credit = prepare(
                    paths, model, score, cfg, task["seeds"], task["round"], outcomes
                )
                steps = adam.steps
                model, adam, work = update(model, adam, samples, task["round"])
                result.update(round=task["round"], new_optimizer_steps=adam.steps - steps)
                atomic_json(target / "credit.json", credit)
                atomic_json(target / "work.json", work)
                result["experience"] = credit["experience"]
                clean = [r for r in outcomes if r["status"] == "terminal"]
                print(
                    f"Round {task['round']} / player {task['player']} / {task['arm']}: "
                    f"wins {sum(r['victory'] for r in clean)}/{len(outcomes)}; "
                    f"average floor {sum(r['maximum_floor'] for r in clean) / len(outcomes):.2f}; "
                    f"best floor {max((r['maximum_floor'] for r in clean), default=0)}; "
                    f"failures {len(outcomes) - len(clean)}; {adam.steps - steps} updates.",
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
            checks_immutable = immutable_checks(q, inputs)
            checks_immutable["account_profile_unchanged"] = before == _shared_snapshot(account)
            if not all(checks_immutable.values()):
                raise ValueError("A frozen input or real account profile changed")
            if training:
                result.update(
                    **report, round=task["round"], collection_id=manifest_identifier(report)
                )
            else:
                result.update(**report["outcomes"][0], games_recorded=1)
            result["checks"] = checks_immutable
    if time.monotonic() >= deadline:
        raise TimeoutError("Experience unit reached its finite cap; preserve unfinished evidence")
    journal.commit(task["key"], request, result)
