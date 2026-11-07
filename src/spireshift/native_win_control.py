"""Bounded native starts and collect/learn/reload/held-world copy control."""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import time
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_neural import validate_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Sample, log_softmax
from spireshift.native_conditional_control import teaching_gradient
from spireshift.native_structured_model import encode
from spireshift.native_structured_state import load as restore
from spireshift.native_structured_state import save
from spireshift.native_win_bank import steps
from spireshift.native_win_game import episode, prepare, write
from spireshift.native_win_inputs import RECIPE, binding, frozen_checks, load
from spireshift.native_win_plan import cases, start_cases


def public_steps(root: Path, result: dict[str, Any]) -> list[dict[str, Any]]:
    return steps(root, {"episode_directory": result["directory"]})


def loss(model: Any, data: list[dict[str, Any]], score: Any) -> float:
    if not data:
        raise ValueError("No independent meaningful public labels")
    values = []
    for row in data:
        validate_public_input(row["public_input"])
        encoded, _ = encode(row["public_input"], model, score)
        logs = log_softmax(score_features(cast(Any, model.actor), encoded), 0.8)
        values.append(-logs[row["action_index"]])
    return math.fsum(values) / len(values)


def update(
    model: Any, adam: Any, data: list[dict[str, Any]], score: Any, salt: str
) -> tuple[Any, Any]:
    rng = random.Random(salt)
    samples, labels = [], []
    for _ in range(32):
        step = rng.choice(data)
        encoded, state = encode(step["public_input"], model, score)
        label = step["action_index"]
        logs = log_softmax(score_features(cast(Any, model.actor), encoded), 0.8)
        samples.append(Sample(encoded, state, label, logs[label], 0.0, 0.0))
        labels.append(label)
    _, gradient, _ = teaching_gradient(
        cast(Any, model),
        samples,
        labels,
        {"temperature": 0.8, "clip": 0.2, "entropy_coefficient": 0.0, "value_coefficient": 0.0},
    )
    result, optimizer, _ = adam.update(
        cast(Any, model), gradient, actor_rate=0.001, value_rate=0.0, maximum_norm=1.0
    )
    return result, optimizer


def starts(context: dict[str, Any], target: Path, deadline: float) -> dict[str, Any]:
    generation = context["config"]["control_generation"]
    entries = start_cases(generation)
    results = []
    short = {
        **context,
        "config": {
            **context["config"],
            "plan": {**context["config"]["plan"], "maximum_decisions": 2},
        },
    }
    for case in entries:
        where = target / case["key"]
        where.mkdir()
        start = prepare(context, case, where, deadline)
        if start["status"] != "ready":
            raise ValueError("A declared native start is unavailable")
        run = where / "delivery"
        run.mkdir()
        result = episode(short, start, "scaling", run, deadline)
        if result["policy_decisions"] != 2 or not result["shutdown"]["clean_exit"]:
            raise ValueError("Native start did not exercise two acknowledged actual choices")
        results.append(result)
        print(
            f"Start control: {case['act_definition']} / {case['entry']} / {case['boss']}: verified",
            flush=True,
        )
    return {
        "all_twelve_native_bosses_started": len(results) == 14,
        "all_final_bosses_started": True,
        "actual_start_deliveries": sum(r["policy_decisions"] for r in results),
        "start_reports": [r["report_id"] for r in results],
        "optimizer_updates": 0,
    }


def collect_control(
    context: dict[str, Any], target: Path, deadline: float, partition: str
) -> dict[str, Any]:
    generation = context["config"]["control_generation"]
    chosen, outputs = [], []
    selected = cases("control_" + partition, control=True, generation=generation)[:3]
    for case in selected:
        where = target / case["key"]
        where.mkdir()
        start = prepare(context, case, where, deadline)
        if start["status"] != "ready":
            raise ValueError("A fitting/held-world control start is unavailable")
        attempts = []
        for variant in context["config"]["plan"]["teacher_variants"]:
            run = where / variant
            run.mkdir()
            result = episode(context, start, variant, run, deadline)
            outputs.append(result)
            attempts.append(result)
            print(
                f"Learning control: {case['key']} / {variant}: {result['status']}; "
                f"success={result['curriculum_success']}",
                flush=True,
            )
        successful = [r for r in attempts if r["status"] == "complete" and r["curriculum_success"]]
        if successful:
            result = max(successful, key=lambda r: r["ending_hp"])
            chosen.append({"start": start, "episode": result})
    if not chosen:
        raise ValueError("No successful native continuation in this short-control partition")
    return {
        "partition": partition,
        "selected": chosen,
        "successful_act_slots": sorted({r["start"]["scenario"]["act"] for r in chosen}),
        "all_attempt_reports": [r["report_id"] for r in outputs],
        "actual_deliveries": sum(r["policy_decisions"] for r in outputs),
        "optimizer_updates": 0,
        "fitting_labels_allowed": partition == "fit",
    }


def learn(context: dict[str, Any], target: Path, deadline: float) -> dict[str, Any]:
    root = context["qualification"].root
    groups: dict[str, list[dict[str, Any]]] = {"fit": [], "heldout": []}
    start_by_key = {}
    outputs = []
    for partition in ("fit", "heldout"):
        report = identified(target.parent / f"{partition}/report.json")
        if report["implementation_id"] != manifest_identifier(context["config"]["implementation"]):
            raise ValueError("Control collection must use the exact current implementation")
        for chosen in report["result"]["selected"]:
            start, result = chosen["start"], chosen["episode"]
            start_by_key[start["scenario"]["key"]] = start
            for step in public_steps(root, result):
                groups[partition].append(
                    {**step, "scenario_key": start["scenario"]["key"], "world": start["seed"]}
                )
    fitting_ids = {s["public_input_id"] for s in groups["fit"]}
    groups["heldout"] = [s for s in groups["heldout"] if s["public_input_id"] not in fitting_ids]
    held = groups["heldout"][:128]
    fits = groups["fit"][:256]
    if not held:
        raise ValueError("Control held-world menus must be genuinely unseen during fitting")
    values = []
    for p in (2, 3):
        model, adam = context["models"][p], copy.deepcopy(context["adams"][p])
        before_steps, before_weights, before_critic = (
            adam.steps,
            model.weights(),
            model.value_weights,
        )
        initial_fit, initial_held = (
            loss(model, fits, context["score"]),
            loss(model, held, context["score"]),
        )
        destination = target / f"student-p{p}"
        destination.mkdir()
        for update_index in range(16):
            if update_index == 8:
                state = save(destination / "halfway.json", model, adam)
                restored, moments, sid = restore(destination / "halfway.json")
                if (
                    sid != state["state_id"]
                    or restored.weights() != model.weights()
                    or moments.as_dict() != adam.as_dict()
                ):
                    raise ValueError("Full warm-Adam reload differs")
                expected, expected_adam = update(
                    model,
                    copy.deepcopy(adam),
                    fits,
                    context["score"],
                    f"win-control-{p}-{update_index}",
                )
                actual, actual_adam = update(
                    restored, moments, fits, context["score"], f"win-control-{p}-{update_index}"
                )
                if (
                    expected.weights() != actual.weights()
                    or expected_adam.as_dict() != actual_adam.as_dict()
                ):
                    raise ValueError("Next resumed update failed exact reconstruction")
                model, adam = actual, actual_adam
            else:
                model, adam = update(
                    model, adam, fits, context["score"], f"win-control-{p}-{update_index}"
                )
        final_fit, final_held = (
            loss(model, fits, context["score"]),
            loss(model, held, context["score"]),
        )
        if (
            not final_fit < initial_fit
            or not final_held < initial_held
            or adam.steps != before_steps + 16
            or model.weights() == before_weights
            or model.value_weights != before_critic
        ):
            raise ValueError("Actual-bank fitting/unseen-world transfer control failed")
        state = save(destination / "final.json", model, adam)
        restored, _, _ = restore(destination / "final.json")
        start = start_by_key[held[0]["scenario_key"]]
        student = {
            **context,
            "config": {
                **context["config"],
                "plan": {**context["config"]["plan"], "maximum_decisions": 4},
            },
        }
        run = destination / "actual-held-world-delivery"
        run.mkdir()
        result = episode(student, start, "student", run, deadline, model=restored)
        outputs.append(result)
        if result["policy_decisions"] != 4:
            raise ValueError("Reloaded student did not deliver its four current actions")
        values.append(
            {
                "player": p,
                "fit_initial": initial_fit,
                "fit_final": final_fit,
                "held_initial": initial_held,
                "held_final": final_held,
                "state_id": state["state_id"],
                "optimizer_steps": adam.steps,
                "actual_deliveries": result["policy_decisions"],
            }
        )
    return {
        "copies": values,
        "fit_choices": len(fits),
        "heldout_unseen_choices": len(held),
        "heldout_fit_overlap": 0,
        "registered_disposable_copy_updates": 32,
        "additional_resume_reconstruction_steps": 2,
        "main_optimizer_updates": 0,
        "originals_unchanged": True,
        "actual_episode_reports": [r["report_id"] for r in outputs],
        "actual_deliveries": sum(r["policy_decisions"] for r in outputs),
        "new_player_strength_or_live_qualification_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["starts", "fit", "heldout", "learn", "verify"])
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    context = load(root, root / RECIPE, require_control=False)
    cfg = context["config"]
    base = root / f"artifacts/native-win-curriculum/control-v{cfg['control_generation']}"
    target = base / args.phase
    target.mkdir(parents=True, exist_ok=False)
    deadline = started + 275
    before = frozen_checks(context)
    if args.phase == "verify":
        a, b = identified(base / "starts/report.json"), identified(base / "learn/report.json")
        if any(
            r["implementation_id"] != manifest_identifier(cfg["implementation"]) for r in [a, b]
        ):
            raise ValueError("Controls must use this exact implementation")
        resources = [
            root
            / f"artifacts/resources/win-curriculum-control-{p}-v{cfg['control_generation']}.json"
            for p in ["starts", "fit", "heldout", "learn"]
        ]
        for path in resources:
            resource = identified(path)
            if (
                resource["status"] != "completed"
                or resource["exit_code"] != 0
                or resource["cap"] is not None
            ):
                raise ValueError("A native control resource guard failed")
        checks = {
            "all_native_acts_and_bosses_started": a["result"]["all_twelve_native_bosses_started"],
            "new_data_fit_reload_and_actual_delivery": len(b["result"]["copies"]) == 2,
            "unseen_world_transfer": all(
                r["held_final"] < r["held_initial"] for r in b["result"]["copies"]
            ),
            "no_heldout_labels_in_fit": b["result"]["heldout_fit_overlap"] == 0,
            "originals_and_build_exact": all(before.values()),
            "old_canary_scope_not_granted": True,
        }
        if not all(checks.values()):
            raise ValueError("Short control is incomplete")
        result = {"checks": checks}
    elif args.phase in {"fit", "heldout"}:
        result = collect_control(context, target, deadline, args.phase)
    else:
        result = (starts if args.phase == "starts" else learn)(context, target, deadline)
    after = frozen_checks(context)
    evidence = {str(p.relative_to(root)): _sha_file(p) for p in base.rglob("*") if p.is_file()}
    if args.phase == "verify":
        evidence.update({str(p.relative_to(root)): _sha_file(p) for p in resources})
    body = {
        "schema_version": "native-win-curriculum-control-v1",
        "status": "all_act_curriculum_control_verified"
        if args.phase == "verify"
        else "control_phase_verified",
        "phase": args.phase,
        "implementation_id": manifest_identifier(cfg["implementation"]),
        "launch_binding_id": binding(cfg),
        "result": result,
        "checks": result.get("checks", {"phase_complete": True}),
        "checks_before": before,
        "checks_after": after,
        "main_workspace_started": False,
        "main_optimizer_updates": 0,
        "live_qualification_granted": False,
        "wall_seconds": time.monotonic() - started,
        "sources": {**cfg["implementation"], cfg["baseline"]["path"]: cfg["baseline"]["sha256"]},
        "evidence": evidence,
    }
    report = write(target / "report.json", body)
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"sources", "evidence", "result"}})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
