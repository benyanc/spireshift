"""Saved-frame, generated-envelope and consumer-contract checks; zero native attempts."""

from __future__ import annotations

import argparse
import ast
import gzip
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_interface_audit import inventory
from spireshift.native_interface_controls_inputs import load, prepare
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines

CONSUMERS = (
    "native_shop_policy.py",
    "native_turn_teacher_policy.py",
    "native_combat_behavior_policy.py",
    "native_live_policy.py",
    "native_structured_policy.py",
    "native_structured_model.py",
    "native_value_credit.py",
)


def consumer_paths(paths: list[Path]) -> list[dict[str, str]]:
    """Inventory literal public subscripts, not a claim of complete static type inference."""
    rows: list[dict[str, str]] = []
    for path in paths:
        for function in ast.walk(ast.parse(path.read_text())):
            if not isinstance(function, ast.FunctionDef):
                continue
            bindings: dict[str, tuple[str, ...]] = {"public": ()}

            def resolve(
                node: ast.expr, names: dict[str, tuple[str, ...]] = bindings
            ) -> tuple[str, ...] | None:
                if isinstance(node, ast.Name):
                    return names.get(node.id)
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)
                ):
                    prefix = resolve(node.value, names)
                    return None if prefix is None else (*prefix, node.slice.value)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    prefix = resolve(node.func.value, names)
                    return None if prefix is None else (*prefix, node.args[0].value)
                if isinstance(node, ast.IfExp):
                    return resolve(node.body, names)
                return None

            for _ in range(8):
                for node in ast.walk(function):
                    if (
                        isinstance(node, ast.Assign)
                        and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                    ):
                        value = resolve(node.value)
                        if value is not None:
                            bindings[node.targets[0].id] = value
                    elif (
                        isinstance(node, ast.Assign)
                        and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Tuple)
                        and isinstance(node.value, ast.Tuple)
                        and len(node.targets[0].elts) == len(node.value.elts)
                    ):
                        for target, source in zip(
                            node.targets[0].elts, node.value.elts, strict=True
                        ):
                            if isinstance(target, ast.Name):
                                value = resolve(source)
                                if value is not None:
                                    bindings[target.id] = value
            found = set()
            for node in ast.walk(function):
                if isinstance(node, ast.Subscript):
                    value = resolve(node)
                    if value:
                        found.add("/" + "/".join(value))
                elif (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_number"
                    and len(node.args) == 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                ):
                    value = resolve(node.args[0])
                    if value is not None:
                        found.add("/" + "/".join((*value, node.args[1].value)))
            rows.extend(
                {"file": path.name, "function": function.name, "path": value}
                for value in sorted(found)
            )
    return rows


def audit(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    ctx = load(root, recipe)
    cfg = ctx["config"]
    if cfg["stage"] != "saved_only_checks":
        raise ValueError("This entry point never launches live cases")
    workspace = root / cfg["workspace"]
    if workspace.exists():
        if not (workspace / "completed.json").exists():
            raise ValueError("Preserve the unfinished offline controls audit")
        saved = identified(workspace / "report.json")
        if saved["config_id"] != manifest_identifier(cfg):
            raise ValueError("Saved controls audit has different settings")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    source = identified(verified(root, cfg["completed_live_report"]))
    check_sources(root, source["sources"])
    check_sources(root, source["evidence"])
    old_audit = identified(verified(root, cfg["completed_frame_audit"]))
    check_sources(root, old_audit["sources"])
    check_sources(root, old_audit["evidence"])
    protected = json.loads(verified(root, cfg["protection_receipt"]).read_text())
    check_sources(root, protected)
    workspace.mkdir(parents=True)
    atomic_json(workspace / "active.json", {"config_id": manifest_identifier(cfg)})
    snapshots = workspace / "source-at-launch"
    for name in cfg["sources"]:
        target = snapshots / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    atomic_json(snapshots / "recipe.json", cfg)
    imported = prepare(root, ctx)
    before = {
        player: (manifest_identifier(model.as_dict()), manifest_identifier(adam.as_dict()))
        for player, (model, adam, _) in imported.items()
    }
    service = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/audit-interface-controls-v1.mjs")],
        workspace / "audit-stderr.log",
    )
    sequence = 0

    def request(body: dict[str, Any]) -> dict[str, Any]:
        nonlocal sequence
        sequence += 1
        service.send({"request_id": sequence, **body})
        response = service.receive(started + 210)
        if response.get("request_id") != sequence or response.get("ok") is not True:
            raise ValueError(f"Offline controls service failed: {response.get('error')}")
        return response

    counts: Counter[str] = Counter()
    problems: list[dict[str, Any]] = []
    policy_probes: list[dict[str, Any]] = []

    def probe(frame: dict[str, Any], key: str) -> None:
        if frame["terminal"]:
            return
        for player, (model, _, _) in imported.items():
            try:
                choice = LivePolicy(model, ctx["score"], "OFFLINEINTERFACECHECK").choose(frame)
                if not 0 <= choice["action_index"] < len(frame["actions"]) or not math.isfinite(
                    choice["value"]
                ):
                    raise ValueError("Invalid frozen inference result")
                policy_probes.append({"key": key, "player": player, "passed": True})
            except (ValueError, KeyError, TypeError) as error:
                policy_probes.append(
                    {"key": key, "player": player, "passed": False, "error": str(error)}
                )
                problems.append(
                    {
                        "code": "frozen_policy_input_rejected",
                        "key": key,
                        "player": player,
                        "error": str(error),
                    }
                )

    captures = old_audit["evidence"]
    # The sealed audit recipe selects exactly one record kind per official frame.
    audit_recipe = json.loads(
        (root / cfg["completed_frame_audit"]["path"])
        .parent.joinpath("source-at-launch/recipe.json")
        .read_text()
    )
    observed: Counter[str] = Counter()
    total = converted = repaired = 0
    try:
        with gzip.open(workspace / "frames.jsonl.gz", "wt") as output:
            for capture in audit_recipe["captures"]:
                path = root / capture["path"]
                if captures.get(capture["path"]) != _sha_file(path):
                    raise ValueError("Completed public capture changed")
                ordinal = 0
                with gzip.open(path, "rt") as file:
                    for line in file:
                        if len(line) > 16_000_000:
                            raise ValueError("Saved public frame exceeds the memory bound")
                        row = json.loads(line)
                        if (
                            capture["host"] == "official"
                            and row.get("kind") != capture["record_kind"]
                        ):
                            continue
                        if "snapshot" not in row or "reads" not in row:
                            continue
                        total += 1
                        if total > 1000:
                            raise ValueError("Finite saved-frame limit exceeded")
                        family = row["snapshot"]["interaction"]["kind"]
                        group = f"{capture['host']}/{family}"
                        observed[group] += 1
                        response = request(
                            {
                                "snapshot": row["snapshot"],
                                "reads": row["reads"],
                                "include_input": True,
                            }
                        )
                        result = response["result"]
                        converted += result["converted"]
                        repaired += result["repaired_previous_failure"]
                        frame = result.pop("input", None)
                        problems.extend(
                            {"capture": capture["path"], "frame": ordinal, **issue}
                            for issue in result["issues"]
                        )
                        if frame is not None:
                            probe(frame, f"saved/{group}/{ordinal}")
                        output.write(
                            json.dumps({"capture": capture["path"], "frame": ordinal, **result})
                            + "\n"
                        )
                        counts[group] += 1
                        ordinal += 1
        bank = request({"command": "case_bank"})
        catalog = inventory([root / name for name in cfg["inventory_sources"]])
        declared = set(catalog["official_surface_kinds"])
        covered = set(bank["policy_kinds"]) | set(bank["presentation_kinds"]) | {"game_over"}
        if covered != declared:
            problems.append(
                {
                    "code": "source_kind_registry_changed",
                    "missing": sorted(declared - covered),
                    "extra": sorted(covered - declared),
                }
            )
        for case in bank["cases"]:
            probe(case["frame"], f"artificial/{case['key']}")
        mutations = request({"command": "mutations"})["results"]
        problems.extend(
            {"code": "mutation_check_failed", **row} for row in mutations if not row["passed"]
        )
        service.close()
    finally:
        service.stop()
    requirements = consumer_paths([root / "src/spireshift" / name for name in CONSUMERS])
    atomic_json(
        workspace / "source-and-consumer-inventory.json",
        {
            "source_inventory": catalog,
            "literal_required_public_paths": requirements,
            "static_analysis_limits": (
                "literal_subscript_and_simple_alias_inventory_not_complete_control_flow_proof"
            ),
            "explicit_adapter_mappings": {
                "inventory_open": (
                    "typed ShopRoomSurface/ShopInventorySurface plus exact current control evidence"
                ),
                "is_selected": (
                    "same owned card, per-surface/read/referent view, never merged globally"
                ),
                "description_and_legality": (
                    "BuildCard displayPile and includeCombatLegality are scoped"
                ),
                "terminal_result": (
                    "public standard RunHistory.Win context; result controls remain presentation"
                ),
            },
            "structural_policy_and_terminal_envelopes": sorted(
                set(bank["policy_kinds"]) | {"game_over"}
            ),
            "presentation_families_use_existing_startup_tutorial_handlers": bank[
                "presentation_kinds"
            ],
            "unobserved_runtime_families": sorted(
                declared - {key.split("/", 1)[1] for key in observed}
            ),
            "exhaustive_mechanics_or_effect_proof": False,
        },
    )
    atomic_json(workspace / "mutations.json", mutations)
    atomic_json(workspace / "frozen-inference-probes.json", policy_probes)
    for player, (model, adam, _) in imported.items():
        if before[player] != (
            manifest_identifier(model.as_dict()),
            manifest_identifier(adam.as_dict()),
        ):
            raise ValueError("Offline inference changed numerical weights or optimizer state")
    check_sources(root, ctx["sources"])
    check_sources(root, protected)
    check_sources(root, source["evidence"])
    evidence = {str(p.relative_to(root)): _sha_file(p) for p in workspace.rglob("*") if p.is_file()}
    body = {
        "schema_version": "native-interface-controls-audit-v1",
        "config_id": manifest_identifier(cfg),
        "environment_id": ctx["environment"]["manifest_id"],
        "implementation_id": manifest_identifier(cfg["implementation_sha256"]),
        "helpers_id": manifest_identifier(cfg["helpers_sha256"]),
        "status": "saved_interface_controls_pass"
        if not problems
        else "saved_interface_controls_blocked",
        "source_live_report_id": source["report_id"],
        "source_frame_audit_id": old_audit["report_id"],
        "saved_frames": total,
        "converted_frames": converted,
        "old_conversion_failures_repaired": repaired,
        "families": dict(counts),
        "issues": problems,
        "declared_surface_kinds": len(declared),
        "artificial_policy_terminal_envelopes": len(bank["cases"]),
        "generated_mutations": len(mutations),
        "passed_mutations": sum(row["passed"] for row in mutations),
        "frozen_policy_input_probes": len(policy_probes),
        "passed_frozen_policy_input_probes": sum(row["passed"] for row in policy_probes),
        "probe_is_not_gameplay_or_action_correctness": True,
        "original_full_weights_and_all_Adam_unchanged": True,
        "protected_files_unchanged": len(protected),
        "game_apps_created": 0,
        "games_launched": 0,
        "optimizer_updates": 0,
        "training_allowed": False,
        "full_input_equivalence_granted": False,
        "live_compatibility_granted": False,
        "full_run_objective": ctx["score"].evaluation_objective.as_dict(),
        "sources": ctx["sources"],
        "evidence": evidence,
        "wall_seconds": time.monotonic() - started,
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(workspace / "report.json", body)
    atomic_json(workspace / "completed.json", {"report_id": body["report_id"]})
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    result = audit(Path.cwd(), args.recipe.resolve())
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"sources", "evidence", "families"}
            },
            indent=2,
        )
    )
    return 0 if result["status"] == "saved_interface_controls_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
