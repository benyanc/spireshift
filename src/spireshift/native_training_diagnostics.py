"""Read-only behavior, credit and update diagnostics on sealed completed TRAIN games.

No worker, policy optimizer or running workspace is opened. Observed behavior and
in-sample credit alignment do not establish action quality or causal mistakes.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Sample, log_softmax
from spireshift.native_compact_training import prepare_compact
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_optimizer_probe import (
    SOURCES as PROBE_SOURCES,
)
from spireshift.native_optimizer_probe import actor_gradient, load_probe, logits, normalized
from spireshift.neural_combat import _numpy
from spireshift.training_objective import load_training_score_spec

SOURCES = (*PROBE_SOURCES, "native_compact_training.py", "native_training_diagnostics.py")


def bucket(action: dict[str, Any]) -> str:
    """Structural action classes, never inferred effects from card descriptions."""
    subject = action.get("subject") or {}
    role, verb = subject.get("role", "none"), action["verb"]
    properties = subject.get("properties", {})
    detail = properties.get("option_id") if role == "rest_option" else None
    return f"{verb}:{role}" + (f":{detail}" if detail else "")


def decision_meta(public: dict[str, Any], chosen: int) -> dict[str, Any]:
    context = public["context"]
    interaction, player = context["interaction"], context["persistent"]["player"]
    family, actions = interaction["kind"], public["candidates"]
    if type(chosen) is not int or not 0 <= chosen < len(actions):
        raise ValueError("Diagnostic choice is outside its observed menu")
    kinds = [bucket(a) for a in actions]
    opportunities: dict[str, list[int]] = {}

    def offer(name: str, indices: list[int]) -> None:
        if indices:
            opportunities[name] = indices

    plays = [i for i, a in enumerate(actions) if a["verb"] == "play"]
    if family == "combat_turn" and plays:
        offer(
            "end_turn_with_play_available",
            [i for i, a in enumerate(actions) if a["verb"] == "end_turn"],
        )
    if family == "card_reward_selection":
        offer("card_reward_skip", [i for i, a in enumerate(actions) if a["verb"] == "skip"])
        offer(
            "card_reward_take",
            [
                i
                for i, a in enumerate(actions)
                if a["verb"] == "select" and (a.get("subject") or {}).get("role") == "card"
            ],
        )
    for verb, name in (("use", "potion_use"), ("activate", "potion_discard")):
        offer(
            name,
            [
                i
                for i, a in enumerate(actions)
                if a["verb"] == verb
                and (a.get("subject") or {}).get("role") == "potion"
                and (verb == "use" or a["subject"]["properties"].get("can_discard") is True)
            ],
        )
    if family == "shop_inventory":
        purchases = [
            i
            for i, a in enumerate(actions)
            if a["verb"] == "activate"
            and (a.get("subject") or {}).get("role", "").startswith("shop_")
        ]
        offer("shop_purchase_or_service_control", purchases)
        leaves = [
            i for i, a in enumerate(actions) if a["verb"] == "close" and a.get("subject") is None
        ]
        if purchases:
            offer("shop_leave_with_purchase_available", leaves)
        offer(
            "shop_leave_without_prior_inspection",
            [i for i in leaves if actions[i].get("history", {}).get("shop_inspected") is False],
        )
    if family == "rest_site":
        for i, action in enumerate(actions):
            subject = action.get("subject") or {}
            if subject.get("role") == "rest_option":
                option = subject["properties"]["option_id"]
                offer(f"rest_option_{option}", [j for j, k in enumerate(kinds) if k == kinds[i]])
    if family == "reward_claim" and any(
        (a.get("subject") or {}).get("role") == "reward" for a in actions
    ):
        offer(
            "reward_exit_with_unclaimed_rewards",
            [
                i
                for i, a in enumerate(actions)
                if a.get("subject") is None and a["verb"] in {"activate", "skip"}
            ],
        )
    hp, maximum = player["hp"], player["max_hp"]
    if maximum <= 0 or not all(math.isfinite(v) for v in (hp, maximum)):
        raise ValueError("Invalid public health observation")
    content = interaction.get("content", {}).get("context", {})
    return {
        "family": family,
        "action": chosen,
        "kinds": kinds,
        "opportunities": opportunities,
        "hp_fraction": hp / maximum,
        "hp_band": "low" if hp / maximum < 0.25 else "high" if hp / maximum >= 0.75 else "middle",
        "floor": context["persistent"]["run"]["floor"],
        "act": context["persistent"]["run"]["act"],
        "energy": content.get("player", {}).get("energy") if family == "combat_turn" else None,
        "enemies": [e["definition_id"] for e in content.get("enemies", [])],
        "encounter_type": content.get("encounter_type"),
    }


def weighting(samples: list[Sample], metadata: list[dict[str, Any]]) -> dict[str, Any]:
    np = _numpy()
    raw = np.asarray([s.advantage for s in samples])
    mask = np.asarray([len(s.rows) > 1 for s in samples])
    if not len(raw) or not mask.any() or len(metadata) != len(samples):
        raise ValueError("Diagnostic weighting requires matched genuine choices")
    z = (raw - raw.mean()) / max(float(raw.std()), 1e-8)
    choice_z = (raw[mask] - raw[mask].mean()) / max(float(raw[mask].std()), 1e-8)
    games: dict[int, dict[str, Any]] = {}
    for i, (s, meta) in enumerate(zip(samples, metadata, strict=True)):
        g = games.setdefault(
            meta["seed_id"],
            {
                "seed_id": meta["seed_id"],
                "decisions": 0,
                "choices": 0,
                "combat_choices": 0,
                "absolute_credit_mass": 0.0,
            },
        )
        g["decisions"] += 1
        if len(s.rows) > 1:
            g["choices"] += 1
            g["combat_choices"] += int(meta["family"] == "combat_turn")
            g["absolute_credit_mass"] += abs(float(z[i]))
    choices, mass = int(mask.sum()), sum(g["absolute_credit_mass"] for g in games.values())
    for g in games.values():
        g["nominal_actor_choice_weight"] = g["choices"] / len(samples)
        g["share_of_choice_opportunities"] = g["choices"] / choices
        g["share_of_absolute_credit_mass"] = g["absolute_credit_mass"] / mass if mass else None
    shares = [g["share_of_choice_opportunities"] for g in games.values()]
    top = max(1, math.ceil(len(shares) / 4))
    return {
        "decisions": len(samples),
        "choice_decisions": choices,
        "forced_decisions": int((~mask).sum()),
        "forced_fraction": float((~mask).mean()),
        "raw_advantage_mean": float(raw.mean()),
        "raw_advantage_std": float(raw.std()),
        "choice_only_raw_mean": float(raw[mask].mean()),
        "choice_only_raw_std": float(raw[mask].std()),
        "choice_sign_changes_if_normalized_without_forced": int(
            np.count_nonzero(np.sign(z[mask]) != np.sign(choice_z))
        ),
        "choice_only_normalization_is_diagnostic_not_an_update": True,
        "normalization_is_over_all_decisions": True,
        "effective_games_from_choice_counts": 1 / sum(v * v for v in shares),
        "top_quarter_games_share_of_choices": sum(sorted(shares, reverse=True)[:top]),
        "nominal_weights_and_credit_mass_are_not_net_gradient_influence": True,
        "games": sorted(games.values(), key=lambda g: g["seed_id"]),
    }


def measure(
    before: CachedContextModel,
    after: CachedContextModel,
    samples: list[Sample],
    metadata: list[dict[str, Any]],
    settings: dict[str, Any],
    deadline: float = math.inf,
) -> dict[str, Any]:
    if len(samples) != len(metadata) or not samples:
        raise ValueError("Diagnostic decision denominator changed")
    np = _numpy()
    prepared = normalized(samples)
    rows: list[dict[str, Any]] = []
    offers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    selected: Counter[str] = Counter()
    for start in range(0, len(samples), 64):
        if time.monotonic() >= deadline:
            raise TimeoutError("Completed-record diagnostic reached its short wall cap")
        batch = prepared[start : start + 64]
        a, b = logits(before, batch), logits(after, batch)
        offset = 0
        for j, s in enumerate(batch):
            meta = metadata[start + j]
            n = len(s.rows)
            la = np.asarray(log_softmax(a[offset : offset + n], settings["temperature"]))
            lb = np.asarray(log_softmax(b[offset : offset + n], settings["temperature"]))
            pa, pb = np.exp(la), np.exp(lb)
            if (
                n != len(meta["kinds"])
                or s.action != meta["action"]
                or not math.isclose(
                    float(la[s.action]), s.old_log_probability, abs_tol=1e-10, rel_tol=0
                )
            ):
                raise ValueError("Diagnostic inputs no longer reconstruct the behavior menu")
            delta = float(lb[s.action] - la[s.action])
            ratio = math.exp(delta)
            bounded = max(1 - settings["clip"], min(1 + settings["clip"], ratio))
            rows.append(
                {
                    "family": meta["family"],
                    "seed_id": meta["seed_id"],
                    "choice": n > 1,
                    "kl": float(pa @ (la - lb)),
                    "tv": float(abs(pa - pb).sum()) / 2,
                    "greedy_changed": int(int(pa.argmax()) != int(pb.argmax())),
                    "surrogate_gain": min(ratio * s.advantage, bounded * s.advantage) - s.advantage,
                    "log_alignment": s.advantage * delta,
                    "signed_probability_movement": float(pb[s.action] - pa[s.action])
                    * (1 if s.advantage > 0 else -1 if s.advantage < 0 else 0),
                    "advantage": s.advantage,
                }
            )
            selected[f"{meta['family']}|{meta['kinds'][s.action]}"] += 1
            for name, indices in meta["opportunities"].items():
                offers[name].append(
                    {
                        "seed_id": meta["seed_id"],
                        "hp_band": meta["hp_band"],
                        "chosen": int(s.action in indices),
                        "before": float(pa[indices].sum()),
                        "after": float(pb[indices].sum()),
                        "energy": meta["energy"],
                    }
                )
            offset += n
    families = []
    vectors = {}
    total = np.zeros(before.actor.parameter_count)
    for family in sorted({m["family"] for m in metadata}):
        if time.monotonic() >= deadline:
            raise TimeoutError("Completed-record diagnostic reached its short wall cap")
        indices = [i for i, m in enumerate(metadata) if m["family"] == family]
        g = actor_gradient(before, [prepared[i] for i in indices], settings, 0)
        vectors[family] = g * len(indices) / len(samples)
        total += vectors[family]
        group = [rows[i] for i in indices]
        choices = [r for r in group if r["choice"]]
        families.append(
            {
                "family": family,
                "decisions": len(group),
                "choices": len(choices),
                "forced": len(group) - len(choices),
                "complete_runs": len({r["seed_id"] for r in group}),
                "mean_choice_kl": sum(r["kl"] for r in choices) / len(choices) if choices else None,
                "mean_choice_tv": sum(r["tv"] for r in choices) / len(choices) if choices else None,
                "greedy_change_fraction": sum(r["greedy_changed"] for r in choices) / len(choices)
                if choices
                else None,
                "mean_signed_chosen_probability_change": sum(
                    r["signed_probability_movement"] for r in choices
                )
                / len(choices)
                if choices
                else None,
                "clipped_surrogate_gain_per_source_decision": sum(
                    r["surrogate_gain"] for r in group
                )
                / len(group),
                "weighted_initial_data_gradient_norm": float(np.linalg.norm(vectors[family])),
            }
        )
    total_norm = float(np.linalg.norm(total))
    for f in families:
        g = vectors[f["family"]]
        norm = float(np.linalg.norm(g))
        f["data_gradient_cosine_with_total"] = (
            float(g @ total) / norm / total_norm if norm and total_norm else None
        )
    forced = [s for s in prepared if len(s.rows) == 1]
    forced_norm = (
        float(np.linalg.norm(actor_gradient(before, forced, settings, 0))) if forced else 0.0
    )
    opportunities = []
    for name, values in sorted(offers.items()):
        by_health = {}
        for band in ("low", "middle", "high"):
            v = [x for x in values if x["hp_band"] == band]
            by_health[band] = {
                "opportunities": len(v),
                "selected": sum(x["chosen"] for x in v),
                "mean_probability_before": sum(x["before"] for x in v) / len(v) if v else None,
                "mean_probability_after": sum(x["after"] for x in v) / len(v) if v else None,
            }
        opportunities.append(
            {
                "name": name,
                "opportunities": len(values),
                "selected": sum(v["chosen"] for v in values),
                "complete_runs": len({v["seed_id"] for v in values}),
                "mean_probability_before": sum(v["before"] for v in values) / len(values),
                "mean_probability_after": sum(v["after"] for v in values) / len(values),
                "health_bands": by_health,
            }
        )
    end_turns = sum(v for k, v in selected.items() if k == "combat_turn|end_turn:none")
    early = sum(v["selected"] for v in opportunities if v["name"] == "end_turn_with_play_available")
    return {
        "families": families,
        "selected_action_classes": dict(sorted(selected.items())),
        "observed_opportunities": opportunities,
        "end_turns": end_turns,
        "end_turns_with_play_available": early,
        "fraction_of_end_turns_with_play_available": early / end_turns if end_turns else None,
        "global_clipped_surrogate_gain": sum(r["surrogate_gain"] for r in rows) / len(rows),
        "global_advantage_weighted_log_movement": sum(r["log_alignment"] for r in rows) / len(rows),
        "initial_data_gradient_norm": total_norm,
        "forced_menu_initial_actor_gradient_norm": forced_norm,
        "gradient_scope": "before_update_data_term_only_not_entropy_Adam_or_causal_influence",
        "normalization_and_game_weighting": weighting(samples, metadata),
        "behavior_counts_are_decisions_not_unique_room_visits": True,
        "probability_changes_use_identical_saved_inputs_not_after_policy_rollouts": True,
        "action_quality_or_causal_mistakes_established": False,
    }


def model_at(root: Path, ref: dict[str, Any]) -> CachedContextModel:
    if ref["kind"] not in {"state", "model"}:
        raise ValueError("Unknown diagnostic checkpoint format")
    model = (
        load_state(root / ref["path"])[0]
        if ref["kind"] == "state"
        else CachedContextModel.from_mapping(json.loads((root / ref["path"]).read_text()))
    )
    if model.model_id != ref["id"]:
        raise ValueError("Diagnostic checkpoint identity changed")
    return model


def checked_case(
    root: Path,
    cohort: dict[str, Any],
    entry: dict[str, Any],
    before: CachedContextModel,
    score_id: str,
) -> dict[str, Any]:
    header = json.loads((root / entry["path"]).read_text())
    b = header["binding"]
    if (
        b["partition"] != "train"
        or b["panel_purpose"] != "training"
        or b["model_id"] != before.model_id
        or b["seed_id"] != entry["seed_id"]
        or b["config_id"] != cohort["source_config"]["id"]
        or b["seed_manifest_id"] != cohort["seed_manifest"]["id"]
        or b["environment_id"] != before.actor.environment_id
        or b["training_spec_id"] != score_id
        or b["native_seed"] != entry["native_seed"]
    ):
        raise ValueError("Only own-behavior completed TRAIN records may enter diagnostics")
    case = read_native_episode(root / entry["path"], b)
    if (
        case["seed"] != entry["native_seed"]
        or case["status"] != "terminal"
        or case.get("recovered") is not False
        or case.get("privileged_fixture") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or not case["decisions"]
    ):
        raise ValueError(
            "Incomplete, recovered or privileged records are not clean diagnostic games"
        )
    return case


def load(root: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = json.loads(path.read_text())
    q = load_engine_qualification_config(root / cfg["qualification"])
    probe_cfg, parent = load_probe(q, root / cfg["probe_config"]["path"])
    report = identified(root / cfg["probe_report"]["path"])
    if (
        cfg.get("schema_version") != "native-completed-training-diagnostics-config-v1"
        or cfg["probe_config"]["id"] != manifest_identifier(probe_cfg)
        or cfg["probe_report"]["id"] != report["report_id"]
        or report["config_id"] != manifest_identifier(probe_cfg)
        or report["status"] != "train_only_optimizer_probe_complete"
        or cfg["implementation_sha256"]
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg["resource_limits"]
        != {
            "wall_seconds": 240,
            "cpu_seconds": 240,
            "resident_memory_bytes": 1000000000,
            "storage_bytes": 100000000,
        }
        or cfg["maximum_games"] != 64
        or not 1 <= len(cfg["cohorts"]) <= 2
        or sum(len(c["cases"]) for c in cfg["cohorts"]) > cfg["maximum_games"]
    ):
        raise ValueError(
            "Freeze completed TRAIN-only scope, exact sources and finite diagnostic budget"
        )
    check_sources(root, report["sources"])
    check_sources(root, cfg["protected_files_sha256"])
    seen = set()
    for c in cfg["cohorts"]:
        match = next(
            (
                r
                for r in report["results"]
                if r["cohort"] == c["number"] and r["variant"] == "standard"
            ),
            None,
        )
        if (
            match is None
            or c["before"]["id"] != match["before_model_id"]
            or c["after"]["id"] != match["after_model_id"]
            or len(c["cases"]) != match["source_games"]
        ):
            raise ValueError("Diagnostic cohort must match its completed standard update")
        for ref in (c["source_config"], c["seed_manifest"]):
            d = json.loads((root / ref["path"]).read_text())
            actual = (
                identified(root / ref["path"], "manifest_id")["manifest_id"]
                if ref == c["seed_manifest"]
                else manifest_identifier(d)
            )
            if actual != ref["id"]:
                raise ValueError("Diagnostic source ownership manifest changed")
        seeds = json.loads((root / c["seed_manifest"]["path"]).read_text())["seeds"]
        for e in c["cases"]:
            if e["seed_id"] in seen or not any(
                s["id"] == e["seed_id"]
                and s["partition"] == "train"
                and s["seed"] == e["native_seed"]
                for s in seeds
            ):
                raise ValueError("Diagnostic games repeat or cross whole-run TRAIN ownership")
            seen.add(e["seed_id"])
        for name in [
            c["before"]["path"],
            c["after"]["path"],
            *[
                n
                for e in c["cases"]
                for n in (e["path"], str(Path(e["path"]).with_suffix(".jsonl.gz")))
            ],
        ]:
            if name not in report["sources"]:
                raise ValueError("Diagnostic file is not sealed by the completed source report")
    return cfg, parent, report


def diagnose(
    root: Path, cfg: dict[str, Any], parent: dict[str, Any], c: dict[str, Any], deadline: float
) -> dict[str, Any]:
    score = load_training_score_spec(root / parent["training_spec"]["path"])
    before, after = model_at(root, c["before"]), model_at(root, c["after"])
    if (
        before.mode != after.mode
        or before.feature_spec_id != after.feature_spec_id
        or before.actor.dimension != after.actor.dimension
        or before.actor.environment_id != after.actor.environment_id
    ):
        raise ValueError("Diagnostic policy changes cannot silently change input encoding")
    metadata, outcomes = [], []
    for e in c["cases"]:
        if time.monotonic() >= deadline:
            raise TimeoutError("Completed-record diagnostic reached its short wall cap")
        case = checked_case(root, c, e, before, score.spec_id)
        for i, d in enumerate(case["decisions"]):
            meta = decision_meta(d["public_input"], d["choice"]["action_index"])
            metadata.append({**meta, "seed_id": e["seed_id"], "decision": i})
        last = metadata[-1]
        outcomes.append(
            {
                "seed_id": e["seed_id"],
                "victory": case["victory"],
                "maximum_floor": case["maximum_floor"],
                "completed_acts": case["completed_acts"],
                "decisions": len(case["decisions"]),
                "last_public_family": last["family"],
                "last_public_hp_fraction": last["hp_fraction"],
                "last_public_encounter_type": last["encounter_type"],
                "last_public_enemies": last["enemies"],
                "last_action_class": last["kinds"][last["action"]],
                "causal_death_reason_available": False,
            }
        )
        del case
    settings = parent["learning"]["ppo"]
    samples, credit = prepare_compact(
        [root / e["path"] for e in c["cases"]],
        before,
        score,
        settings,
        parent["learning"]["credit_assignment"],
        1,
    )
    if len(metadata) != c["expected_decisions"] or len(samples) != len(metadata):
        raise ValueError("Diagnostic complete decision denominator changed")
    result = measure(before, after, samples, metadata, settings, deadline)
    observed = Counter(o["last_public_family"] for o in outcomes if not o["victory"])
    return {
        "cohort": c["number"],
        "games": len(outcomes),
        "decisions": len(samples),
        "before_model_id": before.model_id,
        "after_model_id": after.model_id,
        "wins": sum(o["victory"] for o in outcomes),
        "outcomes": outcomes,
        "losses_preceded_by_public_family": dict(observed),
        "credit_reconstruction": credit,
        **result,
    }


def summary_text(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Completed training diagnostics",
        "",
        "Only completed historical TRAIN games are inspected. No games, policy updates, "
        "running results or checkpoint promotions occur.",
        "",
        "These are behavior frequencies and agreement with assigned credit, not optimal-action "
        "labels or evidence of stronger play. Health bands compare different observed states.",
        "Credit compares the whole-run outcome with a state baseline. Its sign does not isolate "
        "one action's effect on the ending.",
    ]
    for r in results:
        w = r["normalization_and_game_weighting"]
        lines.extend(
            [
                "",
                f"## Cohort {r['cohort']}",
                "",
                f"{r['games']} clean training games, {r['decisions']} decisions, "
                f"{r['wins']} full wins.",
                f"Mandatory menus: {w['forced_decisions']}/{w['decisions']} "
                f"({w['forced_fraction']:.1%}). Their direct actor gradient norm is "
                f"{r['forced_menu_initial_actor_gradient_norm']:.3g}; "
                "they still enter normalization.",
                f"Removing them from normalization alone would change the credit sign for "
                f"{w['choice_sign_changes_if_normalized_without_forced']}/{w['choice_decisions']} "
                "real choices. This counterfactual is diagnostic; no update is applied.",
                "The quarter of games with most real choices supplies "
                f"{w['top_quarter_games_share_of_choices']:.1%} of choice opportunities. "
                "Counts and credit mass do not measure net causal influence.",
                f"End turns with a play still available: {r['end_turns_with_play_available']}/"
                f"{r['end_turns']} end turns. Availability does not mean playing is preferable.",
                "",
                "| Observed control | Selected | Opportunities | Before probability | "
                "After probability |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        lines.extend(
            f"| {v['name']} | {v['selected']} | {v['opportunities']} | "
            f"{v['mean_probability_before']:.3f} | {v['mean_probability_after']:.3f} |"
            for v in r["observed_opportunities"]
        )
        lines.extend(
            [
                "",
                "Purchase/service controls can open a further choice; "
                "they are not confirmed purchases. "
                "Counts are decisions, so repeated menus and multiple rest options remain counted.",
                "",
                "| Decision family | Choices | Mandatory | Mean probability movement | "
                "Changed greedy choice |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for f in r["families"]:
            tv = f"{f['mean_choice_tv']:.4f}" if f["choices"] else "n/a"
            flips = f"{f['greedy_change_fraction']:.1%}" if f["choices"] else "n/a"
            lines.append(f"| {f['family']} | {f['choices']} | {f['forced']} | {tv} | {flips} |")
        lines.extend(
            [
                "",
                "Probability movement is total variation on the same old inputs. "
                "It is not measured "
                "performance of the updated player. Rare or absent families have limited evidence.",
                "",
                f"Losses preceded by public family: {r['losses_preceded_by_public_family']}. "
                "The last public state is not a causal explanation of death.",
            ]
        )
    return "\n".join(lines) + "\n"


def run(root: Path, path: Path) -> dict[str, Any]:
    cfg, parent, probe = load(root, path)
    store = ChunkJournal(root, cfg)
    started = time.monotonic()
    deadline = started + cfg["resource_limits"]["wall_seconds"] - 10
    sources = {
        str(path.relative_to(root)): _sha_file(path),
        **cfg["protected_files_sha256"],
        **{f"src/spireshift/{n}": h for n, h in cfg["implementation_sha256"].items()},
        cfg["probe_report"]["path"]: _sha_file(root / cfg["probe_report"]["path"]),
        **probe["sources"],
    }
    results = []
    with store.lock():
        final = store.workspace / "report.json"
        if final.exists():
            saved = identified(final)
            if saved["config_id"] != store.config_id:
                raise ValueError("Saved diagnostic recipe changed")
            check_sources(root, saved["sources"])
            return saved
        for c in cfg["cohorts"]:
            key = f"cohort-{c['number']}"
            request = {"cohort": c, "source_report_id": probe["report_id"]}
            cached = store.completed(key, request)
            if cached is None:
                target = store.begin(key, request)
                result = diagnose(root, cfg, parent, c, deadline)
                expected = next(
                    r
                    for r in probe["results"]
                    if r["cohort"] == c["number"] and r["variant"] == "standard"
                )
                norm = result["normalization_and_game_weighting"]
                if not all(
                    math.isclose(norm[k], expected["work"][k], abs_tol=1e-12, rel_tol=0)
                    for k in ("raw_advantage_mean", "raw_advantage_std")
                ) or not math.isclose(
                    result["global_clipped_surrogate_gain"],
                    expected["movement"]["clipped_training_surrogate_gain"],
                    abs_tol=1e-10,
                    rel_tol=0,
                ):
                    raise ValueError(
                        "Diagnostic credit/movement does not reconstruct saved training"
                    )
                atomic_json(target / "diagnostics.json", result)
                cached = store.commit(key, request, result, sources)
                print(
                    f"Cohort {c['number']}: {result['games']} completed training games, "
                    f"{result['decisions']} decisions checked; no games or optimizer updates.",
                    flush=True,
                )
            results.append(cached["result"])
            sources.update(cached["sources"])
            p = store.path(key) / "done.json"
            sources[str(p.relative_to(root))] = _sha_file(p)
        check_sources(root, sources)
        summary = store.workspace / "summary.md"
        # Publish the derived prose once, like other evidence. Preserve an interrupted write.
        with summary.open("x") as handle:
            handle.write(summary_text(results))
        sources[str(summary.relative_to(root))] = _sha_file(summary)
        body = {
            "schema_version": "native-completed-training-diagnostics-v1",
            "config_id": store.config_id,
            "status": "completed_training_diagnostics_complete",
            "environment_manifest": parent.get("environment_manifest"),
            "training_spec": parent["training_spec"],
            "source_probe_report_id": probe["report_id"],
            "cohorts": results,
            "source_games": sum(r["games"] for r in results),
            "source_decisions": sum(r["decisions"] for r in results),
            "summary_path": str(summary.relative_to(root)),
            "sources": sources,
            "protected_files_unchanged": True,
            "maximum_raw_episodes_retained": 1,
            "policy_optimizer_steps": 0,
            "games_launched": 0,
            "worker_processes_started": 0,
            "worker_profiles_modified": 0,
            "running_experiment_records_read": 0,
            "checkpoint_promoted": False,
            "action_quality_established": False,
            "claim_scope": (
                "completed_TRAIN_behavior_and_in_sample_credit_alignment_not_causal_action_quality"
            ),
            "wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        atomic_json(final, result)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    r = run(root, root / a.config)
    print(json.dumps({k: v for k, v in r.items() if k not in {"sources", "cohorts"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
