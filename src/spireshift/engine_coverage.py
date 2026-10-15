"""Private native mechanics inventory and isolated, generated interface diagnostics.

Inventory is not execution coverage; a legal card blocked by a prerequisite is not
an exercised effect. Fixtures, source signals and failures never become PPO data.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _private_path, _require_native_launch_support, _running_games
from spireshift.engine_qualification import EngineQualificationConfig, _inventory, _sha_file
from spireshift.engine_run import _assert_saved_public, _run_inputs
from spireshift.engine_worker import EngineWorker, worker_helpers
from spireshift.full_run_experience import atomic_json

SCRIPT = "engine-mechanics-worker-v1.mjs"
IMPLEMENTATION = ("engine_coverage.py", "engine_worker.py", "engine_run.py", "engine_cli_probe.py")


def coverage_implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / "src/spireshift" / name) for name in IMPLEMENTATION}


TARGETS = {
    "None": "automatic",
    "Self": "automatic",
    "AnyEnemy": "bound_enemy",
    "AllEnemies": "automatic",
    "RandomEnemy": "automatic",
    "AnyPlayer": "automatic_single_player",
    "AnyAlly": "disabled_single_player",
    "AllAllies": "automatic",
    "Osty": "automatic_companion",
    "TargetedNoCreature": "requires_non_creature_binding",
}
# Broader requirements remain visible even when this sweep cannot yet exercise them.
REQUIREMENTS = {
    "all_pool_current_card_facts": "generated_cards",
    "current_energy_and_star_costs": "generated_cards",
    "foreign_orbs": "cold-snap",
    "foreign_stars": "solar-strike",
    "foreign_companion": "summon-osty",
    "nested_replayed_card_selection": "headbutt-replay",
    "dynamic_cost_interactions": "enlightenment",
    "reward_to_nested_bundle": "reward-scroll-boxes",
    "multiple_rest_actions_and_exit": "rest-multiple-options",
    "shop_restock_remove_leave": "shop-restock-remove",
    "out_of_combat_potion_use": "unverified",
    "non_creature_potion_target": "unsupported",
    "optional_reward_skip": "skip-card-reward",
    "act_and_terminal_transitions": "unverified",
    "random_legal_action_sequences": "unverified",
}


def _sealed(body: dict[str, Any], key: str = "report_id") -> dict[str, Any]:
    return {**body, key: manifest_identifier(body)}


def _read_sealed(path: Path, key: str = "report_id") -> dict[str, Any]:
    body = json.loads(path.read_text())
    if body.get(key) != manifest_identifier({k: v for k, v in body.items() if k != key}):
        raise ValueError(f"Coverage evidence identity changed: {path}")
    return dict(body)


def generate_plan(catalog: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Join exact native classes, never infer that name hints mean unobtainable."""
    models = catalog["models"]
    if len({row["class"] for row in models}) != len(models):
        raise ValueError("Duplicate live native model class")
    live = {row["class"]: row for row in models}
    registered = {row["type"] for row in registry["models"]}
    gaps = sorted(registered - set(live))
    rows, cases = [], []
    for item in registry["models"]:
        row = live.get(item["type"])
        status = "runtime_missing" if row is None else "inventoried_only"
        if row is not None and row.get("is_mock") is True:
            status = "native_mock_excluded"
        if row is not None and not row.get("metadata_complete"):
            status = "metadata_incomplete"
        if row and item["family"] == "Cards" and status == "inventoried_only":
            if row.get("pool_is_mock") is True:
                status = "native_mock_pool_excluded"
            else:
                # Token/event/foreign cards are included, even if not in the reward pool.
                card_id = row["id"].split(".")[-1]
                maximum = row.get("maximum_upgrade")
                if type(maximum) is not int or maximum < 0:
                    raise ValueError("Unknown native upgrade limit")
                for upgrade, funded in [(0, False), (0, True)] + ([(1, True)] if maximum else []):
                    case = {
                        "case_id": f"{card_id}-u{upgrade}-{'funded' if funded else 'normal'}",
                        "fixture": {"card_id": card_id, "upgrade": upgrade, "funded": funded},
                        "kind": "generated_card",
                        "model_class": item["type"],
                        "required_effect": False,
                    }
                    cases.append(case)
                status = "planned_base_and_first_upgrade" if maximum else "planned_base"
        if row and item["family"] == "Potions" and status == "inventoried_only":
            potion_id = row["id"].split(".")[-1]
            cases.append(
                {
                    "case_id": f"{potion_id}-combat",
                    "fixture": {
                        "card_id": "STRIKE_IRONCLAD",
                        "upgrade": 0,
                        "funded": True,
                        "potion_id": potion_id,
                    },
                    "kind": "generated_potion",
                    "model_class": item["type"],
                    "required_effect": False,
                }
            )
            status = "planned_combat_potion"
        rows.append(
            {
                "class": item["type"],
                "family": item["family"],
                "status": status,
                "native_id": row.get("id") if row else None,
            }
        )
    unknown_targets = sorted(set(catalog["target_types"]) - set(TARGETS))
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Generated coverage case identities collide")
    named_cases: list[tuple[str, str, dict[str, Any]]] = [
        ("cold-snap", "COLD_SNAP", {}),
        ("meteor-strike", "METEOR_STRIKE", {}),
        ("solar-strike", "SOLAR_STRIKE", {}),
        ("summon-osty", "BODYGUARD", {"summon_osty": True}),
        ("headbutt-replay", "HEADBUTT", {"enchantment": "GLAM", "discard_filler": True}),
        ("enlightenment", "ENLIGHTENMENT", {"hand_extra": "METEOR_STRIKE"}),
        ("reward-scroll-boxes", "STRIKE_IRONCLAD", {"reward_relic": "SCROLL_BOXES"}),
        (
            "rest-multiple-options",
            "STRIKE_IRONCLAD",
            {"room": "rest", "relics": ["MINIATURE_TENT", "SHOVEL", "GIRYA"]},
        ),
        ("shop-restock-remove", "STRIKE_IRONCLAD", {"room": "shop", "relics": ["THE_COURIER"]}),
        ("skip-card-reward", "STRIKE_IRONCLAD", {"reward_cards": True}),
    ]
    for name, card, extra in named_cases:
        cases.append(
            {
                "case_id": name,
                "fixture": {
                    "card_id": card,
                    "upgrade": 0,
                    "funded": name != "solar-strike",
                    **extra,
                },
                "kind": "named_regression",
                "required_effect": True,
            }
        )
    body = {
        "schema_version": "native-mechanics-plan-v1",
        "registry_id": registry["registry_id"],
        "catalog_id": catalog["report_id"],
        "models": rows,
        "cases": cases,
        "runtime_missing_classes": gaps,
        "unregistered_runtime_classes": sorted(set(live) - registered),
        "target_types": {
            target: TARGETS.get(target, "unsupported_unknown") for target in catalog["target_types"]
        },
        "unknown_target_types": unknown_targets,
        "requirements": REQUIREMENTS,
        "maximum_upgrade_exercised": 1,
        "unbounded_upgrade_combinations_exhausted": False,
        "all_interactions_proven": False,
        "training_allowed": False,
        "privileged_fixture": True,
    }
    return _sealed(body, "plan_id")


def _saved_case(path: Path, spec: dict[str, Any], plan_id: str) -> dict[str, Any]:
    case = _read_sealed(path)
    if case["spec"] != spec or case["plan_id"] != plan_id:
        raise ValueError("Saved coverage case belongs to another plan")
    for ref in case["evidence_files"]:
        if _sha_file(path.parent / ref["path"]) != ref["sha256"]:
            raise ValueError("Saved coverage trace changed")
    return case


def coverage_summary(
    plan: dict[str, Any], results: list[dict[str, Any]], planned: int
) -> dict[str, Any]:
    counts = dict(Counter(row["status"] for row in results))
    inventory_complete = not (
        plan["runtime_missing_classes"]
        or plan["unregistered_runtime_classes"]
        or plan["unknown_target_types"]
        or any(row["status"] == "metadata_incomplete" for row in plan["models"])
    )
    named = {
        row["spec"]["case_id"]: row["status"]
        for row in results
        if row["spec"]["kind"] == "named_regression"
    }
    requirements = {
        key: {
            "status": "exercised_native_diagnostic"
            if named.get(value) == "effect_exercised"
            else value
            if value in {"unsupported", "unverified", "existing_unit_tests_only"}
            else "unverified",
            "evidence_case": value,
        }
        for key, value in REQUIREMENTS.items()
    }
    generated = [case for case in plan["cases"] if case["kind"] == "generated_card"]
    actual = {row["spec"]["case_id"]: row["status"] for row in results}
    if (
        generated
        and inventory_complete
        and all(
            actual.get(case["case_id"]) in {"effect_exercised", "observed_prerequisite_blocked"}
            for case in generated
        )
    ):
        for key in ("all_pool_current_card_facts", "current_energy_and_star_costs"):
            requirements[key]["status"] = "observed_all_planned_contexts"
    # An interface smoke success cannot admit training, engine parity or content completeness.
    return {
        "planned_cases": planned,
        "completed_cases": len(results),
        "not_attempted_cases": planned - len(results),
        "case_statuses": counts,
        "requirements": requirements,
        "inventory_complete": inventory_complete,
        "registered_models": len(plan["models"]),
        "model_statuses": dict(Counter(r["status"] for r in plan["models"])),
        "known_gaps": [
            {"case_id": r["spec"]["case_id"], "error": r.get("error"), "status": r["status"]}
            for r in results
            if r["status"] in {"failed", "bounded_incomplete", "required_effect_not_exercised"}
        ],
        "unknown_targets": plan["unknown_target_types"],
        "runtime_missing_models": len(plan["runtime_missing_classes"]),
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "all_interactions_proven": False,
        "privileged_fixture": True,
        "claim_scope": "generated_all_pool_interface_diagnostics_not_exhaustive_gameplay_proof",
    }


def _exercise(worker: EngineWorker, spec: dict[str, Any], maximum: int) -> dict[str, Any]:
    worker.request("mount", seed="SP1RESH1FTCOVERAGE001", timeout=25)
    current = worker.request("fixture", fixture=spec["fixture"], timeout=20)
    _assert_saved_public(current["model_input"])
    started = time.monotonic()
    observations = [current["public_key"]]
    actions: list[dict[str, Any]] = []
    decisions: list[str] = []
    played = False
    initial_context = current["model_input"]["context"]
    purchases = 0
    removal = False
    rest_ids: list[str] = []
    for _ in range(maximum):
        if time.monotonic() - started > 40:
            raise TimeoutError("Per-case diagnostic action wall cap")
        kind = current["snapshot"]["interaction"]["kind"]
        decisions.append(kind)
        if current["facts"]["terminal"]:
            if not played:
                raise ValueError("Fixture ended before its card could be exercised")
            break
        if (
            played
            and spec["case_id"]
            not in {"rest-multiple-options", "shop-restock-remove", "skip-card-reward"}
            and kind
            not in {
                "card_selection",
                "native_generated_card_choice",
                "card_bundle_selection",
            }
        ):
            break
        candidates = current["model_input"]["candidates"]
        if (
            spec["case_id"] in {"rest-multiple-options", "shop-restock-remove"}
            and kind == "map_navigation"
        ):
            break
        if spec["case_id"] == "skip-card-reward":
            if played:
                break
            skip = [i for i, action in enumerate(candidates) if action["verb"] == "skip"]
            index = skip[0] if skip else 0
            played = bool(skip)
        elif spec["case_id"] == "rest-multiple-options" and kind == "rest_site":
            offered = [i for i, action in enumerate(candidates) if action["verb"] == "activate"]
            if offered:
                index = offered[0]
                rest_ids.append(candidates[index]["subject"]["properties"]["option_id"])
                played = True
            else:
                index = next(i for i, action in enumerate(candidates) if action["verb"] == "close")
        elif spec["case_id"] == "shop-restock-remove" and kind == "shop_inventory":
            if purchases < 2:
                index = next(
                    i
                    for i, action in enumerate(candidates)
                    if action.get("subject", {}).get("role") == "shop_card"
                )
                purchases += 1
            elif not removal:
                index = next(
                    i
                    for i, action in enumerate(candidates)
                    if action.get("subject", {}).get("role") == "shop_service"
                )
                removal = True
            else:
                index = next(i for i, action in enumerate(candidates) if action["verb"] == "close")
            played = True
        elif spec["case_id"] == "reward-scroll-boxes" and not played:
            index = next(
                i for i, action in enumerate(candidates) if action["label"] == "Claim Scroll Boxes"
            )
            played = True
        elif kind == "combat_turn":
            if played:
                break
            eligible = [
                i
                for i, action in enumerate(candidates)
                if action["verb"] == ("use" if spec["kind"] == "generated_potion" else "play")
                and str(
                    action.get("subject", {}).get("properties", {}).get("definition_id", "")
                ).split(".")[-1]
                == spec["fixture"].get("potion_id", spec["fixture"]["card_id"])
            ]
            if not eligible:
                return {
                    "status": "required_effect_not_exercised"
                    if spec["required_effect"]
                    else "observed_prerequisite_blocked",
                    "public_keys": observations,
                    "decision_kinds": decisions,
                    "actions": actions,
                    "error": "Native rules did not offer a playable fixture card in this context",
                }
            index = eligible[0]
            played = True
        else:
            # Follow only current native choices. Never guess an exit or retry uncertain delivery.
            eligible = [
                i
                for i, action in enumerate(candidates)
                if action["verb"] in {"confirm", "select", "choose", "proceed"}
            ]
            if not eligible:
                eligible = [
                    i
                    for i, action in enumerate(candidates)
                    if action["verb"] in {"skip", "leave", "cancel"}
                ]
            if not eligible:
                raise ValueError(f"No supported diagnostic continuation for {kind}")
            index = eligible[0]
        actions.append(current["model_input"]["candidates"][index])
        current = worker.request(
            "step", snapshot_id=current["snapshot"]["snapshot_id"], action_index=index, timeout=20
        )
        _assert_saved_public(current["model_input"])
        observations.append(current["public_key"])
    else:
        return {
            "status": "bounded_incomplete",
            "public_keys": observations,
            "decision_kinds": decisions,
            "actions": actions,
            "error": "Diagnostic decision cap; no effect completion claimed",
        }
    if spec["kind"] == "named_regression":
        player = (
            current["model_input"]["context"]["interaction"]["content"]
            .get("context", {})
            .get("player", {})
        )
        name = spec["case_id"]
        if name in {"cold-snap", "meteor-strike"}:
            expected = "FROST_ORB" if name == "cold-snap" else "PLASMA_ORB"
            if not any(
                str(orb["definition_id"]).endswith(expected) for orb in player.get("orbs", [])
            ):
                raise ValueError("Expected native foreign orb did not reach public input")
        if name == "solar-strike" and not (
            player.get("stars_visible") is True and player.get("stars", 0) > 0
        ):
            raise ValueError("Foreign star gain is absent from public input")
        if name == "summon-osty" and not any(
            c.get("is_osty") for c in player.get("companions", [])
        ):
            raise ValueError("Companion was not visible after native summon")
        if name == "reward-scroll-boxes" and "card_bundle_selection" not in decisions:
            raise ValueError("Reward claim did not exercise the nested native bundle choice")
        if name == "enlightenment":
            before = initial_context["interaction"]["content"]["context"]["player"]["hand"]
            after = player.get("hand", [])
            old = [c["cost"] for c in before if str(c["definition_id"]).endswith("METEOR_STRIKE")]
            new = [c["cost"] for c in after if str(c["definition_id"]).endswith("METEOR_STRIKE")]
            if old != ["5"] or new != ["1"]:
                raise ValueError(
                    "Native cost reduction did not update the other card's public current cost"
                )
        if name == "rest-multiple-options" and len(set(rest_ids)) < 4:
            raise ValueError("Native tent fixture did not exercise all four refreshed rest choices")
        if name == "shop-restock-remove" and (
            purchases != 2 or not removal or "card_selection" not in decisions
        ):
            raise ValueError("Shop fixture did not exercise restocking, removal selection and exit")
        if name == "skip-card-reward" and not any(a["verb"] == "skip" for a in actions):
            raise ValueError("Optional card reward did not offer Skip")
        if name == "headbutt-replay" and decisions.count("card_selection") < 2:
            raise ValueError("Replayed selection did not exercise two separate native choices")
    return {
        "status": "effect_exercised",
        "public_keys": observations,
        "decision_kinds": decisions,
        "actions": actions,
        "final_context": current["model_input"]["context"],
    }


def run_mechanics_coverage(
    q: EngineQualificationConfig, path: Path, *, node: Path, stage: str
) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-mechanics-coverage-config-v1"
        or cfg.get("qualification_config_id") != q.config_id
        or cfg.get("training_allowed") is not False
        or cfg.get("privileged_fixture") is not True
        or stage not in {"inventory", "smoke", "sweep"}
    ):
        raise ValueError("Expected separately pinned, privileged mechanics coverage recipe")
    if cfg.get("implementation_sha256") != coverage_implementation(q.root):
        raise ValueError("Coverage implementation changed; freeze a new recipe before running")
    helper_pins = worker_helpers(q.root, SCRIPT)
    if helper_pins != cfg["helpers_sha256"]:
        raise ValueError("Coverage worker helpers changed")
    for key in ("maximum_cases", "maximum_decisions_per_case", "maximum_wall_seconds"):
        if type(cfg.get(key)) is not int or cfg[key] < 1:
            raise ValueError(f"Coverage cap absent: {key}")
    inputs = _run_inputs(q, q.root / cfg["run_config"])
    if manifest_identifier(inputs["recipe"]) != cfg["run_config_id"]:
        raise ValueError("Coverage run input recipe changed")
    registry_path = _private_path(q.root, cfg["registry_path"])
    registry = json.loads(registry_path.read_text())
    if (
        _sha_file(registry_path) != cfg["registry_sha256"]
        or registry["assembly_sha256"] != inputs["build"]["runtime_sts2_sha256"]
    ):
        raise ValueError("Coverage inventory belongs to another game assembly")
    workspace = _private_path(q.root, cfg["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    recipe_id = manifest_identifier(cfg)
    binding = workspace / "recipe.json"
    if binding.exists() and json.loads(binding.read_text()) != cfg:
        raise ValueError("Coverage workspace already belongs to another recipe")
    if not binding.exists():
        atomic_json(binding, cfg)
    catalog_path = workspace / "catalog.json"
    if catalog_path.exists():
        catalog = _read_sealed(catalog_path)
        if catalog["config_id"] != recipe_id:
            raise ValueError("Saved native catalog configuration changed")
    else:
        _require_native_launch_support()
        if _running_games() or not node.is_file():
            raise ValueError("Close the game and use the local Node runtime")
        worker = EngineWorker(
            q,
            inputs,
            workspace / "catalog-worker",
            node,
            helper_pins,
            script=SCRIPT,
            projection_cache=workspace / "shared-projection",
        )
        try:
            raw = worker.request("catalog", timeout=45)
            worker.close()
        except BaseException:
            worker.retire("Native catalog failure")
            raise
        catalog = _sealed(
            {
                "schema_version": "native-mechanics-catalog-v1",
                "config_id": recipe_id,
                "assembly_sha256": registry["assembly_sha256"],
                **raw,
            }
        )
        atomic_json(catalog_path, catalog)
    plan = generate_plan(catalog, registry)
    plan_path = workspace / "plan.json"
    if plan_path.exists() and _read_sealed(plan_path, "plan_id") != plan:
        raise ValueError("Mechanics plan changed; use a new recipe/workspace")
    if not plan_path.exists():
        atomic_json(plan_path, plan)
    if stage == "inventory":
        return _sealed(
            {
                "config_id": recipe_id,
                "plan_id": plan["plan_id"],
                **coverage_summary(plan, [], len(plan["cases"])),
            }
        )
    cases = [c for c in plan["cases"] if stage == "sweep" or c["case_id"] in cfg["smoke_cases"]]
    if len(cases) > cfg["maximum_cases"] or (
        stage == "smoke" and len(cases) != len(cfg["smoke_cases"])
    ):
        raise ValueError("Coverage cases exceed frozen cap or named smoke case absent")
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and use the local Node runtime")
    started = time.monotonic()
    results = []
    for index, spec in enumerate(cases):
        case_dir = workspace / stage / f"case-{spec['case_id']}"
        saved = case_dir / "result.json"
        control = workspace / "smoke" / f"case-{spec['case_id']}" / "result.json"
        if stage == "sweep" and not saved.exists() and control.exists():
            # Verified same-plan controls count once; no unnecessary second game.
            results.append(_saved_case(control, spec, plan["plan_id"]))
            continue
        if saved.exists():
            results.append(_saved_case(saved, spec, plan["plan_id"]))
            continue
        if time.monotonic() - started > cfg["maximum_wall_seconds"]:
            break
        # Exclusive creation preserves interrupted cases; never silently retry them.
        case_dir.mkdir(parents=True, exist_ok=False)
        worker = EngineWorker(
            q,
            inputs,
            case_dir / "worker",
            node,
            helper_pins,
            script=SCRIPT,
            projection_cache=workspace / "shared-projection",
        )
        case_started = time.monotonic()
        try:
            result = _exercise(worker, spec, cfg["maximum_decisions_per_case"])
            shutdown = worker.close()
        except (ValueError, TimeoutError, OSError, StopIteration, KeyError) as error:
            result = {"status": "failed", "error": str(error)}
            shutdown = worker.retire(str(error))
        finally:
            worker.stop()
        result = _sealed(
            {
                "spec": spec,
                "plan_id": plan["plan_id"],
                **result,
                "shutdown": shutdown,
                "wall_seconds": time.monotonic() - case_started,
                "evidence_files": _inventory(case_dir),
            }
        )
        atomic_json(saved, result)
        results.append(result)
        if result["status"] in {"failed", "bounded_incomplete", "required_effect_not_exercised"}:
            print(f"Gap at {spec['case_id']}: {result.get('error', result['status'])}", flush=True)
        if stage == "smoke" or (index + 1) % 25 == 0 or index + 1 == len(cases):
            print(
                f"Coverage {index + 1}/{len(cases)}: {dict(Counter(r['status'] for r in results))}",
                flush=True,
            )
        summary = _sealed(
            {
                "config_id": recipe_id,
                "plan_id": plan["plan_id"],
                "wall_seconds_this_invocation": time.monotonic() - started,
                **coverage_summary(plan, results, len(cases)),
            }
        )
        atomic_json(workspace / stage / f"progress-{index + 1:05d}.json", summary)
    # Recheck every shared input that a diagnostic could have touched; never create app copies.
    if (
        _inventory(inputs["candidate"]) != inputs["candidate_before"]
        or _inventory(inputs["runtime"]) != inputs["runtime_before"]
    ):
        raise ValueError("Protected native coverage inputs changed")
    result = _sealed(
        {
            "config_id": recipe_id,
            "plan_id": plan["plan_id"],
            "case_reports": [r["report_id"] for r in results],
            "wall_seconds_this_invocation": time.monotonic() - started,
            **coverage_summary(plan, results, len(cases)),
        }
    )
    if len(results) == len(cases):
        final_path = workspace / f"{stage}-summary.json"
        if final_path.exists():
            previous = _read_sealed(final_path)
            if (
                previous.get("case_reports") != result["case_reports"]
                or previous["config_id"] != recipe_id
            ):
                raise ValueError("Saved coverage summary differs from verified cases")
            return previous
        atomic_json(final_path, result)
    return result


def require_mechanics_coverage(
    q: EngineQualificationConfig, inputs: dict[str, Any], reference: dict[str, Any] | None
) -> None:
    """New all-pool learning must bind full diagnostics plus resolved requirements.

    This never admits bulk learning by itself. Existing worker, short-control,
    information-boundary and explicit experiment-admission checks still apply.
    """
    if inputs["inputs"].get("combat_surface_revision") != "v3":
        return
    if not isinstance(reference, dict) or set(reference) != {"config", "report_id"}:
        raise ValueError("All-pool learning requires a frozen mechanics coverage gate")
    cfg = json.loads((q.root / reference["config"]).read_text())
    if cfg.get("implementation_sha256") != coverage_implementation(q.root):
        raise ValueError("Mechanics coverage implementation changed before learning")
    workspace = _private_path(q.root, cfg["workspace"])
    report = _read_sealed(workspace / "sweep-summary.json")
    if (
        report["report_id"] != reference["report_id"]
        or report["config_id"] != manifest_identifier(cfg)
        or report.get("not_attempted_cases") != 0
        or report.get("inventory_complete") is not True
        or report.get("known_gaps")
        or report["planned_cases"] < 1
    ):
        raise ValueError("Mechanics sweep is incomplete or has unresolved native gaps")
    plan = _read_sealed(workspace / "plan.json", "plan_id")
    catalog = _read_sealed(workspace / "catalog.json")
    if (
        report["plan_id"] != plan["plan_id"]
        or plan["catalog_id"] != catalog["report_id"]
        or catalog["assembly_sha256"] != inputs["build"]["runtime_sts2_sha256"]
        or report["planned_cases"] != len(plan["cases"])
        or cfg["helpers_sha256"] != worker_helpers(q.root, SCRIPT)
    ):
        raise ValueError("Mechanics gate belongs to another game, plan or public adapter")
    case_ids = []
    for spec in plan["cases"]:
        saved = workspace / "sweep" / f"case-{spec['case_id']}" / "result.json"
        if not saved.exists():
            saved = workspace / "smoke" / f"case-{spec['case_id']}" / "result.json"
        case_ids.append(_saved_case(saved, spec, plan["plan_id"])["report_id"])
    if case_ids != report["case_reports"]:
        raise ValueError("Mechanics gate case/trace denominator changed")
    unresolved = [
        key
        for key, value in report["requirements"].items()
        if value["status"] not in {"exercised_native_diagnostic", "observed_all_planned_contexts"}
    ]
    if unresolved:
        raise ValueError("Mechanics requirements remain unresolved: " + ", ".join(unresolved))
