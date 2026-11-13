"""Matched world-balanced imitation with full warm-Adam restoration and a final barrier."""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_conditional_control import teaching_gradient
from spireshift.native_curriculum_config import ARMS
from spireshift.native_curriculum_store import (
    Pause,
    admit_result,
    final,
    finish,
    journal,
    reserve,
    snapshot,
)
from spireshift.native_learner_guard import recorded, require_copy
from spireshift.native_natural_learning import metrics
from spireshift.native_structured_model import encode
from spireshift.native_structured_state import load, save


def examples(
    model: Any,
    lessons: list[dict[str, Any]],
    arm: str,
    score: Any,
    count: int,
    batch: int,
    salt: str,
) -> tuple[list[Sample], list[int], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for lesson in lessons:
        if lesson["partition"] not in {"fit", "control"}:
            raise ValueError("Withheld labels never enter the optimizer")
        grouped.setdefault(lesson["world"], []).append(lesson)
    worlds = sorted(grouped)
    if not worlds or count < len(worlds):
        raise ValueError("Require a bounded batch covering every admitted fitting world")
    samples, labels, draws = [], [], {w: 0 for w in worlds}
    for i in range(count):
        world = worlds[(batch * count + i) % len(worlds)]
        entries = sorted(grouped[world], key=lambda r: r["root_id"])
        # Separate per-example streams keep world/entry work identical even when
        # teacher and reference trajectories have different lengths.
        lesson = random.Random(f"{salt}-{i}-entry").choice(entries)
        step = random.Random(f"{salt}-{i}-position").choice(lesson["plans"][arm]["steps"])
        public, label = step["public_input"], step["action_index"]
        if step["public_input_id"] != manifest_identifier(public):
            raise ValueError("A fitting label changed its exact public legal menu")
        rows, value = encode(public, model, score)
        if type(label) is not int or not 0 <= label < len(rows):
            raise ValueError("A teacher label is outside its complete current menu")
        logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
        samples.append(Sample(rows, value, label, logs[label], 0.0, 0.0))
        labels.append(label)
        draws[world] += 1
    return samples, labels, draws


def epoch(
    context: dict[str, Any],
    model: Any,
    adam: Adam,
    curriculum: dict[str, Any],
    arm: str,
    player: int,
    number: int,
    target: Path,
) -> tuple[Any, Adam, dict[str, Any]]:
    settings = context["config"]["plan"]["learning"]
    roots = [r["plans"][arm] for r in curriculum["lessons"]]
    before, value_weights = adam.steps, model.value_weights
    initial = metrics(model, roots, context["score"])
    draws: dict[str, int] = {}
    for update in range(settings["steps_per_epoch"]):
        batch = (number - 1) * settings["steps_per_epoch"] + update
        samples, labels, work = examples(
            model,
            curriculum["lessons"],
            arm,
            context["score"],
            settings["batch_choices"],
            batch,
            f"varied-{player}-{number}-{update}",
        )
        for world, count in work.items():
            draws[world] = draws.get(world, 0) + count
        config = {
            "temperature": settings["temperature"],
            "clip": 0.2,
            "entropy_coefficient": 0.0,
            "value_coefficient": 0.0,
        }
        _, gradient, _ = teaching_gradient(cast(Any, model), samples, labels, config)
        model, adam, _ = adam.update(
            cast(Any, model),
            gradient,
            actor_rate=settings["actor_learning_rate"],
            value_rate=0.0,
            maximum_norm=settings["gradient_clip"],
        )
        if model.value_weights != value_weights:
            raise ValueError("Diagnostic imitation changed critic weights")
    result = {
        "epoch": number,
        "arm": arm,
        "optimizer_updates": adam.steps - before,
        "example_draws": sum(draws.values()),
        "draws_by_world": draws,
        "initial": initial,
        "final": metrics(model, roots, context["score"]),
        "loss": "public_legal_action_categorical_imitation",
        "ordinary_PPO": False,
        "critic_unchanged": True,
        "heldout_used": False,
    }
    atomic_json(target / "work.json", result)
    return model, adam, result


def schedule(epochs: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = [
        {"key": f"initial-p{p}", "kind": "import", "player": p} for p in (2, 3)
    ]
    states = {(p, a): f"initial-p{p}" for p in (2, 3) for a in ARMS}
    for e in range(1, epochs + 1):
        for p in (2, 3):
            for arm in ARMS:
                key = f"fit-p{p}-{arm}-e{e:02d}"
                tasks.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "player": p,
                        "arm": arm,
                        "epoch": e,
                        "state": states[p, arm],
                    }
                )
                states[p, arm] = key
    finals = {
        f"p{p}-{a}": f"initial-p{p}" if a == "original" else states[p, a]
        for p in (2, 3)
        for a in ("original", *ARMS)
    }
    tasks.append({"key": "frozen-finals", "kind": "freeze", "states": finals})
    return tasks


def fit(
    context: dict[str, Any], *, max_units: int | None = None, deadline: float | None = None
) -> dict[str, Any]:
    saved = final(context, "fitting")
    if saved is not None:
        return saved
    root, cfg = context["qualification"].root, context["config"]
    collection = final(context, "collection")
    if collection is None or collection["status"] != "curriculum_qualified":
        raise ValueError(
            "Complete and assess the prospectively fixed fitting-only teacher quality gate first"
        )
    curriculum = identified(root / collection["bank_path"], "bank_id")
    if curriculum["bank_id"] != collection["bank_id"] or curriculum["control_only"] is not (
        cfg["stage"] == "short_control"
    ):
        raise ValueError("Wrong bank or a short-control quality bypass in the main study")
    store = journal(context, "fitting")
    started = time.monotonic()
    deadline = deadline or started + cfg["session_limits"]["wall_seconds"] - 15
    done: dict[str, Any] = {}
    tasks, sources, new = (
        schedule(cfg["plan"]["learning"]["epochs"]),
        dict(context["sources"]),
        0,
    )
    sources.update(collection["sources"])
    sources.update(collection["evidence"])
    with store.lock():
        sources.update(snapshot(context, store))
        try:
            for task in tasks:
                request = {
                    "bank_id": curriculum["bank_id"],
                    "guard_id": context["guard_receipt"]["report_id"],
                    "task": task,
                }
                if "state" in task:
                    request["predecessor_state_id"] = done[task["state"]]["state_id"]
                    request["predecessor_optimizer_id"] = done[task["state"]]["optimizer_id"]
                if task["kind"] == "freeze":
                    request["final_state_ids"] = {
                        k: done[v]["state_id"] for k, v in task["states"].items()
                    }
                receipt = store.completed(task["key"], request)
                if receipt is None:
                    reserve(deadline, 20, new, max_units)
                    check_sources(root, cfg["implementation"])
                    target = store.begin(task["key"], request)
                    if task["kind"] == "freeze":
                        finals = {k: done[v] for k, v in task["states"].items()}
                        expected = (
                            cfg["plan"]["learning"]["epochs"]
                            * cfg["plan"]["learning"]["steps_per_epoch"]
                        )
                        for p in (2, 3):
                            initial = finals[f"p{p}-original"]["optimizer_steps"]
                            for arm in ARMS:
                                if finals[f"p{p}-{arm}"]["optimizer_steps"] != initial + expected:
                                    raise ValueError("Teacher and reference optimizer work differ")
                            for e in range(1, cfg["plan"]["learning"]["epochs"] + 1):
                                reference_work = done[f"fit-p{p}-reference-e{e:02d}"]["work"]
                                teacher_work = done[f"fit-p{p}-teacher-e{e:02d}"]["work"]
                                if any(
                                    reference_work[k] != teacher_work[k]
                                    for k in [
                                        "optimizer_updates",
                                        "example_draws",
                                        "draws_by_world",
                                    ]
                                ):
                                    raise ValueError(
                                        "Matched optimizer work or world contributions differ"
                                    )
                        result = {
                            "kind": "freeze",
                            "finals": finals,
                            "bank_id": curriculum["bank_id"],
                            "no_evaluation_used_for_selection": True,
                            "fixed_final_epoch": cfg["plan"]["learning"]["epochs"],
                        }
                        result["frozen_finals_id"] = manifest_identifier(result)
                        atomic_json(target / "finals.json", result)
                    else:
                        p = task["player"]
                        work = None
                        if task["kind"] == "import":
                            model = context["models"][p]
                            adam = Adam.from_mapping(
                                context["adams"][p].as_dict(), model.parameter_count
                            )
                        else:
                            parent = done[task["state"]]
                            model, adam, sid = load(root / parent["state_path"])
                            if sid != parent["state_id"]:
                                raise ValueError("Fitting resume changed its full predecessor")
                            regression = identified(root / parent["recorded_path"])
                            require_copy(context, model, adam, regression)
                            model, adam, work = epoch(
                                context,
                                model,
                                adam,
                                curriculum,
                                task["arm"],
                                p,
                                task["epoch"],
                                target,
                            )
                        value = save(target / "state.json", model, adam)
                        if (
                            task["kind"] == "import"
                            and value["state_id"]
                            != context["guard_binding"]["players"][str(p)]["imported_state_id"]
                        ):
                            raise ValueError(
                                "Initial copied state differs from its "
                                "live-qualified numerical/Adam import"
                            )
                        regression = recorded(
                            context, model, value["state_id"], manifest_identifier(adam.as_dict())
                        )
                        require_copy(context, model, adam, regression)
                        atomic_json(target / "recorded.json", regression)
                        result = {
                            "kind": task["kind"],
                            "player": p,
                            "arm": task.get("arm", "original"),
                            "epoch": task.get("epoch", 0),
                            "state_path": str((target / "state.json").relative_to(root)),
                            "state_id": value["state_id"],
                            "model_id": model.model_id,
                            "optimizer_steps": adam.steps,
                            "optimizer_id": manifest_identifier(adam.as_dict()),
                            "recorded_path": str((target / "recorded.json").relative_to(root)),
                            "recorded_id": regression["report_id"],
                            "work": work,
                        }
                    store.commit(task["key"], request, result, context["sources"])
                    receipt = store.completed(task["key"], request)
                    assert receipt is not None
                    new += 1
                    print(f"Fitting: {task['key']} sealed", flush=True)
                done[task["key"]] = receipt["result"]
                admit_result(root, sources, store, task["key"], receipt)
            barrier = done["frozen-finals"]
            return finish(
                context,
                store,
                {
                    "schema_version": "native-varied-fitting-result-v1",
                    "status": "diagnostic_finals_frozen",
                    "bank_id": curriculum["bank_id"],
                    "finals": barrier["finals"],
                    "frozen_finals_id": barrier["frozen_finals_id"],
                    "optimizer_updates": sum(
                        r["work"]["optimizer_updates"] for r in done.values() if r["kind"] == "fit"
                    ),
                    "matched_optimizer_work": True,
                    "teacher_routing_uses_same_teacher_weights_and_optimizer": True,
                    "new_checkpoint_live_canaries_required": True,
                    "new_checkpoint_live_delivery_qualified": False,
                    "wall_seconds": time.monotonic() - started,
                },
                sources,
            )
        except Pause:
            progress = {
                "status": "clean_session_boundary",
                "phase": "fit",
                "new_units": new,
                "units_restored": len(done) - new,
                "automatic_follow_up": False,
            }
            atomic_json(store.workspace / "progress.json", progress)
            return progress
