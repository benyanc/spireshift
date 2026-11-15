"""Interface-wide source inventory and streaming saved-frame diagnosis. Never gameplay."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_live_inputs import load
from spireshift.native_shared_transport import JsonLines


def inventory(paths: list[Path]) -> dict[str, Any]:
    official: set[str] = set()
    decisions: set[str] = set()
    reads: set[str] = set()
    records: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        text = path.read_text()
        if path.suffix == ".cs" and "host/" in str(path):
            for name, parameters in re.findall(
                r"(?:public|internal)\s+(?:sealed\s+)?record\s+(\w+)\s*\((.*?)\)\s*[;:{]",
                text,
                re.S,
            ):
                # Split generic type arguments without treating their commas as
                # record fields. These are declarations, not runtime proof.
                parts, offset, depth = [], 0, 0
                for index, char in enumerate(parameters):
                    depth += char in "<(["
                    depth -= char in ">)]"
                    if char == "," and depth == 0:
                        parts.append(parameters[offset:index])
                        offset = index + 1
                parts.append(parameters[offset:])
                declared = []
                for part in parts:
                    match = re.fullmatch(r"\s*(.*?)\s+(\w+)\s*(?:=.*)?", part, re.S)
                    if match:
                        kind, field = match.groups()
                        snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", field).lower()
                        declared.append(
                            {
                                "field": snake,
                                "type": kind.strip(),
                                "nullable": kind.strip().endswith("?"),
                            }
                        )
                records[name] = declared
            official.update(
                re.findall(
                    r"(?:public|internal)\s+(?:const\s+)?string\s+(?:Kind|SurfaceKind)"
                    r'\s*(?:=>|=)\s*"([a-z_]+)"',
                    text,
                )
            )
            if path.name == "LiveObservationReader.cs":
                official.update(re.findall(r'new\("([a-z_]+)",\s*static', text))
            if path.name == "PlayerVisibleReadBuilder.cs":
                reads.update(re.findall(r'const string \w+Kind\s*=\s*"([a-z_]+)"', text))
            if path.name == "ReadService.cs":
                reads.update(re.findall(r'"(surface_card)"', text))
        elif path.name == "RunSimulator.cs":
            decisions.update(re.findall(r'\["decision"\]\s*=\s*"([a-z_]+)"', text))
    return {
        "official_surface_kinds": sorted(official),
        "CLI_decisions": sorted(decisions),
        "official_read_kinds": sorted(reads),
        "declared_record_fields": records,
    }


def audit(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    cfg = json.loads(recipe.read_text())
    if (
        cfg.get("schema_version") != "native-interface-audit-config-v1"
        or cfg.get("games_allowed") is not False
    ):
        raise ValueError("Use a finite saved-record interface audit recipe")
    check_sources(root, cfg["sources"])
    contract = json.loads((root / cfg["contract"]).read_text())
    if cfg.get("input_generation", "original") == "repaired":
        from spireshift.native_interface_inputs import load as repaired_load

        context = repaired_load(root, root / cfg["live_recipe"])
    else:
        context = load(root, root / cfg["live_recipe"])
    workspace = root / cfg["workspace"]
    if not workspace.is_relative_to(root / "artifacts/native-interface-audit"):
        raise ValueError("Audit evidence belongs in the separate private workspace")
    if workspace.exists():
        if (workspace / "active.json").exists():
            raise ValueError("Preserve the interrupted saved-record audit")
        saved = identified(workspace / "report.json")
        if saved["config_id"] != manifest_identifier(cfg):
            raise ValueError("Preserve a different saved interface diagnosis")
        check_sources(root, saved["sources"])
        check_sources(root, saved["evidence"])
        return saved
    evidence = {}
    for ref in cfg["reports"]:
        report = identified(root / ref["path"])
        if report["report_id"] != ref["id"] or _sha_file(root / ref["path"]) != ref["sha256"]:
            raise ValueError("Saved source report changed")
        check_sources(root, report["sources"])
        check_sources(root, report["evidence"])
        evidence[ref["path"]] = ref["sha256"]
    for capture in cfg["captures"]:
        path = root / capture["path"]
        if _sha_file(path) != capture["sha256"]:
            raise ValueError("Saved public capture changed")
        evidence[capture["path"]] = capture["sha256"]
    workspace.mkdir(parents=True)
    atomic_json(workspace / "active.json", {"config_id": manifest_identifier(cfg)})
    source_copy = workspace / "source-at-launch"
    for name in cfg["sources"]:
        destination = source_copy / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((root / name).read_bytes())
    atomic_json(source_copy / "recipe.json", cfg)
    service = JsonLines(
        root,
        [cfg["node"], str(root / "scripts/audit-engine-interface-v1.mjs")],
        workspace / "audit-stderr.log",
    )
    observations: Counter[str] = Counter()
    read_counts: Counter[str] = Counter()
    issues: Counter[str] = Counter()
    fields: dict[str, set[str]] = defaultdict(set)
    witnesses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total = converted = repaired = 0
    resolved_issues = remaining_issues = 0
    try:
        with gzip.open(workspace / "frame-diagnostics.jsonl.gz", "wt") as output:
            for capture in cfg["captures"]:
                with gzip.open(root / capture["path"], "rt") as source:
                    ordinal = 0
                    for line in source:
                        if len(line) > 16_000_000:
                            raise ValueError("Public frame exceeds the audit memory contract")
                        row = json.loads(line)
                        # Official policy_input duplicates public_frame in v3/main.
                        if capture["host"] == "official":
                            if row.get("kind") != capture["record_kind"]:
                                continue
                        elif "snapshot" not in row or "reads" not in row:
                            continue
                        total += 1
                        if total > cfg["maximum_frames"] or time.monotonic() > started + 180:
                            raise TimeoutError("Finite saved-record interface audit cap")
                        request = {
                            "request_id": total,
                            "snapshot": row["snapshot"],
                            "reads": row["reads"],
                            "contract": contract,
                        }
                        service.send(request)
                        response = service.receive(started + 180)
                        if response.get("request_id") != total or response.get("ok") is not True:
                            raise ValueError(f"Interface auditor failed: {response.get('error')}")
                        result = response["result"]
                        key = f"{capture['host']}/{result['family']}"
                        observations[key] += 1
                        read_counts.update(f"{capture['host']}/{r['kind']}" for r in row["reads"])
                        fields[key].update(result.pop("fields"))
                        converted += result["converted"]
                        repaired += result["slot_reference_repair_exercised"]
                        for issue in result["issues"]:
                            if issue.get("resolution") == "resolved_from_existing_public_facts":
                                resolved_issues += 1
                            else:
                                remaining_issues += 1
                            grouped = re.sub(r"/\d+(?=/|$)", "/*", issue["path"])
                            identity = f"{key}/{issue['code']}:{grouped}"
                            issues[identity] += 1
                            if len(witnesses[identity]) < 3:
                                witnesses[identity].append(
                                    {
                                        "capture": capture["path"],
                                        "frame": ordinal,
                                        "detail": issue.get("detail"),
                                        "resolution": issue.get("resolution", "remaining_gap"),
                                    }
                                )
                        output.write(
                            json.dumps(
                                {"capture": capture["path"], "frame": ordinal, **result},
                                allow_nan=False,
                            )
                            + "\n"
                        )
                        ordinal += 1
        service.close()
    finally:
        service.stop()
    catalog = inventory([root / p for p in cfg["inventory_sources"]])
    coverage = []
    known = set()
    for family in contract["families"]:
        known.update(family["kinds"])
        counts = {
            host: sum(observations[f"{host}/{k}"] for k in family["kinds"])
            for host in ("native", "official")
        }
        coverage.append(
            {
                "family": family["name"],
                "role": family["role"],
                "kinds": family["kinds"],
                "observed_frames": counts,
                "per_kind": {
                    kind: {host: observations[f"{host}/{kind}"] for host in ("native", "official")}
                    for kind in family["kinds"]
                },
                "runtime_evidence": "both_hosts_observed_not_effect_equivalence"
                if all(counts.values())
                else "missing_observation_coverage",
            }
        )
    sources = {
        str(recipe.relative_to(root)): _sha_file(recipe),
        **cfg["sources"],
        **context["sources"],
    }
    check_sources(root, sources)
    check_sources(root, evidence)
    protected = json.loads((root / cfg["protection_receipt"]).read_text())
    check_sources(root, protected)
    atomic_json(
        workspace / "field-inventory.json", {k: sorted(v) for k, v in sorted(fields.items())}
    )
    differences = []
    for family in contract["families"]:
        left = set().union(*(fields[f"native/{kind}"] for kind in family["kinds"]))
        right = set().union(*(fields[f"official/{kind}"] for kind in family["kinds"]))
        differences.append(
            {
                "family": family["name"],
                "native_only_paths": sorted(left - right),
                "official_only_paths": sorted(right - left),
                "comparison_scope": "unmatched_schema_coverage_not_equal_game_state",
            }
        )
    atomic_json(workspace / "schema-differences.json", differences)
    body = {
        "schema_version": "native-interface-audit-result-v1",
        "config_id": manifest_identifier(cfg),
        "source_inventory": catalog,
        "unclassified_official_surface_kinds": sorted(
            set(catalog["official_surface_kinds"]) - known
        ),
        "coverage": coverage,
        "observations": dict(observations),
        "advertised_read_observations": dict(read_counts),
        "frames": total,
        "converted_with_consolidated_slot_fix": converted,
        "slot_reference_repaired_frames": repaired,
        "resolved_issue_occurrences": resolved_issues,
        "remaining_issue_occurrences": remaining_issues,
        "issues": [
            {"key": k, "occurrences": n, "witnesses": witnesses[k]}
            for k, n in sorted(issues.items())
        ],
        "source_field_inventory_is_not_exhaustive_state_proof": True,
        "source_inventory_limits": (
            "registered_surface/read_literals_and_literal_CLI_decisions; "
            "dynamic dispatch and all value combinations are not proved"
        ),
        "unmatched_states_used_as_paired_effect_evidence": False,
        "full_compatibility_granted": False,
        "training_allowed": False,
        "games_launched": 0,
        "optimizer_updates": 0,
        "protected_prior_files_unchanged": len(protected),
        "sources": sources,
        "evidence": evidence,
        "wall_seconds": time.monotonic() - started,
    }
    body["report_id"] = manifest_identifier(body)
    atomic_json(workspace / "report.json", body)
    (workspace / "active.json").rename(workspace / "completed.json")
    return body


def from_live(root: Path, recipe: Path) -> dict[str, Any]:
    """Seal an audit recipe from a finished live result, including a blocked one."""
    live = json.loads(recipe.read_text())
    template = json.loads((root / live["saved_audit_template"]).read_text())
    report_path = root / live["workspace"] / "report.json"
    report = identified(report_path)
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    workspace = root / "artifacts/native-interface-audit" / f"live-{report['report_id'][7:23]}"
    cfg = {
        **template,
        "live_recipe": str(recipe.relative_to(root)),
        "input_generation": "repaired",
        "workspace": str(workspace.relative_to(root)),
        "reports": [
            {
                "path": str(report_path.relative_to(root)),
                "sha256": _sha_file(report_path),
                "id": report["report_id"],
            }
        ],
        "captures": [],
    }
    for case in report["cases"]:
        for host, filename in [
            ("native", "worker/public-observations.jsonl.gz"),
            ("official", "live-public.jsonl.gz"),
        ]:
            path = root / live["workspace"] / case["key"] / host / filename
            cfg["captures"].append(
                {
                    "host": host,
                    "record_kind": "public_frame" if host == "official" else "snapshot",
                    "path": str(path.relative_to(root)),
                    "sha256": _sha_file(path),
                }
            )
    cfg_path = workspace.with_suffix(".recipe.json")
    if cfg_path.exists():
        if json.loads(cfg_path.read_text()) != cfg:
            raise ValueError("Preserve an audit recipe bound to different live evidence")
    else:
        atomic_json(cfg_path, cfg)
    return audit(root, cfg_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--from-live", action="store_true")
    args = parser.parse_args()
    try:
        report = (from_live if args.from_live else audit)(Path.cwd(), args.recipe.resolve())
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k
                    not in {
                        "sources",
                        "evidence",
                        "issues",
                        "source_inventory",
                        "coverage",
                        "observations",
                    }
                },
                indent=2,
            )
        )
        print(f"Grouped interface gaps: {len(report['issues'])}; no gameplay or training follows.")
        return 0
    except (ValueError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
