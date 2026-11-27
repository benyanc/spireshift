"""Current mixture-aware learning diagnostics on one sealed whole-game TRAIN batch."""

from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import load_state
from spireshift.native_exploration_training import prepare_compact
from spireshift.native_feedback_checks import input_checks, teaching_check
from spireshift.native_optimizer_probe import logits, normalized
from spireshift.native_rest_exploration import Sample, mixed_logs
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_training_diagnostics import decision_meta, weighting
from spireshift.training_objective import TrainingScoreSpec


def moment(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def movement(
    before: CachedContextModel,
    after: CachedContextModel,
    samples: list[Sample],
    metadata: list[dict[str, Any]],
    temperature: float,
    deadline: float,
) -> dict[str, Any]:
    """Use actual mixture likelihoods for feedback, and report base policy separately."""
    if len(samples) != len(metadata):
        raise ValueError("Feedback metadata and exact learner rows disagree")
    # dataclasses.replace in the frozen helper preserves the mixture subclass.
    prepared = cast(list[Sample], normalized(cast(list[Any], samples)))
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rest: dict[str, list[dict[str, Any]]] = defaultdict(list)
    offers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for start in range(0, len(samples), 64):
        if time.monotonic() >= deadline:
            raise TimeoutError("Saved feedback check reached its finite cap")
        batch = prepared[start : start + 64]
        a, b = logits(before, cast(list[Any], batch)), logits(after, cast(list[Any], batch))
        offset = 0
        for j, s in enumerate(batch):
            meta = metadata[start + j]
            n = len(s.rows)
            la = log_softmax(a[offset : offset + n], temperature)
            lb = log_softmax(b[offset : offset + n], temperature)
            qa, qb = mixed_logs(la, s.epsilon), mixed_logs(lb, s.epsilon)
            if not math.isclose(qa[s.action], s.old_log_probability, abs_tol=1e-10, rel_tol=0):
                raise ValueError("Behavior probability no longer matches exact learner rows")
            selected, following = math.exp(qa[s.action]), math.exp(qb[s.action])
            row = {
                "seed_id": meta["seed_id"],
                "choice": n > 1,
                "advantage": s.advantage,
                "positive_credit": s.advantage > 0,
                "base_probability_before": math.exp(la[s.action]),
                "base_probability_after": math.exp(lb[s.action]),
                "actual_probability_before": selected,
                "actual_probability_after": following,
                "credit_aligned_probability_change": (following - selected)
                * (1 if s.advantage > 0 else -1 if s.advantage < 0 else 0),
                "responsibility_at_behavior": (1 - s.epsilon)
                * math.exp(la[s.action] - qa[s.action]),
                "hp_fraction": meta["hp_fraction"],
            }
            families[meta["family"]].append(row)
            if meta["family"] == "rest_site":
                rest[meta["chosen_label"]].append(row)
            for name, indices in meta["opportunities"].items():
                offers[name].append(
                    {
                        "seed_id": meta["seed_id"],
                        "hp_band": meta["hp_band"],
                        "chosen": s.action in indices,
                        "before": math.fsum(math.exp(la[i]) for i in indices),
                        "after": math.fsum(math.exp(lb[i]) for i in indices),
                    }
                )
            offset += n

    def describe(rows: list[dict[str, Any]]) -> dict[str, Any]:
        choices = [r for r in rows if r["choice"]]
        return {
            "decisions": len(rows),
            "choices": len(choices),
            "complete_runs": len({r["seed_id"] for r in rows}),
            **{
                key: moment([r[key] for r in choices])
                for key in (
                    "advantage",
                    "base_probability_before",
                    "base_probability_after",
                    "credit_aligned_probability_change",
                    "responsibility_at_behavior",
                    "hp_fraction",
                )
            },
            "positive_credit_choices": sum(r["positive_credit"] for r in choices),
            "positive_credit_probability_increased": sum(
                r["positive_credit"]
                and r["actual_probability_after"] > r["actual_probability_before"]
                for r in choices
            ),
            "interpretation": "observed_credit_alignment_not_action_quality_or_net_Adam_influence",
        }

    return {
        "families": {k: describe(v) for k, v in sorted(families.items())},
        "rest_choices": {k: describe(v) for k, v in sorted(rest.items())},
        "observed_opportunities": {
            name: {
                "opportunities": len(rows),
                "complete_runs": len({r["seed_id"] for r in rows}),
                "selected": sum(r["chosen"] for r in rows),
                "base_probability_before": moment([r["before"] for r in rows]),
                "base_probability_after": moment([r["after"] for r in rows]),
                "health_bands": {
                    band: {
                        "opportunities": sum(r["hp_band"] == band for r in rows),
                        "selected": sum(r["hp_band"] == band and r["chosen"] for r in rows),
                    }
                    for band in ("low", "middle", "high")
                },
            }
            for name, rows in sorted(offers.items())
        },
        "opportunities_are_menu_presentations_not_unique_visits_or_quality_labels": True,
        "normalization_and_game_weighting": weighting(cast(list[Any], samples), metadata),
        "all_learner_likelihoods_reconstructed": True,
        "same_saved_inputs_before_and_after_not_new_game_evaluation": True,
    }


def value_quality(
    samples: list[Sample], metadata: list[dict[str, Any]], folds: list[dict[str, Any]]
) -> dict[str, Any]:
    """Equal-game choice weighting, same-fold constant and current-floor references."""
    by_seed: dict[int, list[int]] = defaultdict(list)
    for i, (s, meta) in enumerate(zip(samples, metadata, strict=True)):
        if len(s.rows) > 1:
            by_seed[meta["seed_id"]].append(i)
    targets = {seed: samples[indices[0]].target for seed, indices in by_seed.items()}
    constants = {}
    for fold in folds:
        fitting, predicted = set(fold["fitting_runs"]), set(fold["predicted_runs"])
        if fitting & predicted or not fitting or fitting | predicted != set(by_seed):
            raise ValueError("Prediction reference leaked a game's own outcome")
        constants.update(
            {seed: statistics.fmean(targets[s] for s in fitting) for seed in predicted}
        )
    if set(constants) != set(by_seed):
        raise ValueError("Prediction reference lost a whole game")
    errors = {
        k: 0.0
        for k in ("credit_baseline", "recorded_critic", "other_fold_constant", "current_progress")
    }
    for seed, indices in by_seed.items():
        for i in indices:
            s, meta = samples[i], metadata[i]
            predictions = {
                "credit_baseline": s.target - s.advantage,
                "recorded_critic": meta["behavior_value"],
                "other_fold_constant": constants[seed],
                "current_progress": meta["progress_potential"],
            }
            for name, value in predictions.items():
                errors[name] += (s.target - value) ** 2 / len(indices) / len(by_seed)
    return {
        "mse": errors,
        "credit_baseline_beats_other_fold_constant": errors["credit_baseline"]
        < errors["other_fold_constant"],
        "credit_baseline_beats_current_progress": errors["credit_baseline"]
        < errors["current_progress"],
        "independent_games": len(by_seed),
        "weighting": "equal_complete_run_then_equal_choice_bearing_decision",
        "current_progress_is_an_unfitted_reference_not_a_learned_forecast": True,
        "recorded_critic_is_not_the_cross_fitted_predictor_used_for_actor_credit": True,
        "target_is_bootstrap_return_not_victory_probability": True,
    }


def diagnose(
    root: Path,
    cohort: dict[str, Any],
    score: TrainingScoreSpec,
    parent: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    from spireshift.native_value_credit import public_value_features

    before, optimizer, before_id = load_state(root / cohort["before"]["state_path"])
    after, after_optimizer, after_id = load_state(root / cohort["after"]["state_path"])
    if before_id != cohort["before"]["state_id"] or after_id != cohort["after"]["state_id"]:
        raise ValueError("Feedback source model or complete Adam state changed")
    settings = parent["learning"]["ppo"]
    samples, credit = prepare_compact(
        [root / p for p in cohort["paths"]],
        before,
        score,
        settings,
        parent["learning"]["credit_assignment"],
        cohort["round"],
        cohort["uniform_weight"],
    )
    saved_credit = identified(root / cohort["credit_path"])
    if credit != saved_credit:
        raise ValueError("Reconstructed credit differs from the actual training batch")
    metadata, losses, probes = [], [], []
    witness = None
    for path in cohort["paths"]:
        if time.monotonic() >= deadline:
            raise TimeoutError("Feedback reconstruction reached its finite cap")
        header = json.loads((root / path).read_text())
        binding = header["binding"]
        case = read_native_episode(root / path, binding)
        navigation = ShopNavigation()
        last_combat_entry, combat_location, last = None, None, None
        for row in case["decisions"]:
            public, saved = row["public_input"], row["choice"]
            effective, _, forced = navigation.view(public)
            navigation.advance(public, saved["action_index"])
            if forced:
                continue
            selected = saved["effective_action_index"]
            meta = decision_meta(effective, selected)
            _, potential = public_value_features(effective, score)
            metadata.append(
                {
                    **meta,
                    "seed_id": binding["seed_id"],
                    "chosen_label": effective["candidates"][selected]["label"],
                    "behavior_value": saved["value"],
                    "progress_potential": potential,
                }
            )
            last = meta
            if meta["family"] == "combat_turn":
                location = (meta["act"], meta["floor"])
                if location != combat_location:
                    last_combat_entry = meta
                    combat_location = location
                if witness is None and len(effective["candidates"]) > 1:
                    witness = effective
                    probes.append(input_checks(effective, before, score))
        if last is None:
            raise ValueError("No strategic public decisions in the completed training game")
        losses.append(
            {
                "seed_id": binding["seed_id"],
                "victory": case["victory"],
                "maximum_floor": case["maximum_floor"],
                "completed_acts": case["completed_acts"],
                "last_public_family": last["family"],
                "last_public_encounter": last["encounter_type"],
                "last_public_enemies": last["enemies"],
                "last_observed_combat_entry_hp_fraction": last_combat_entry["hp_fraction"]
                if last_combat_entry
                else None,
                "combat_grouping": "observed_act_and_floor_not_unique_engine_encounter_id",
                "causal_death_reason_established": False,
            }
        )
        del case
    if len(metadata) != len(samples) or witness is None:
        raise ValueError("Feedback lost strategic decisions or its input witness")
    result = movement(before, after, samples, metadata, settings["temperature"], deadline)
    sanity = teaching_check(witness, before, optimizer, score, settings)
    return {
        "key": cohort["key"],
        "round": cohort["round"],
        "numerical_seed": cohort["numerical_seed"],
        "arm": cohort["arm"],
        "games": len(cohort["paths"]),
        "decisions": len(samples),
        "before_model_id": before.model_id,
        "after_model_id": after.model_id,
        "before_optimizer_steps": optimizer.steps,
        "after_optimizer_steps": after_optimizer.steps,
        "actual_credit_report_exactly_reconstructed": True,
        "value_quality": value_quality(samples, metadata, credit["cross_fit"]),
        "input_checks": probes,
        "synthetic_teaching_check": sanity,
        "outcomes": losses,
        "last_observed_loss_encounters": dict(
            Counter(str(v["last_public_encounter"]) for v in losses if not v["victory"])
        ),
        "action_labels_created_from_native_losses": 0,
        "discount": credit["discount"],
        "trace_lambda": credit["trace_lambda"],
        **result,
    }
