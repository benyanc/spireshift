"""Outcome-blind, whole-world natural curriculum selection from repaired TRAIN games."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources
from spireshift.native_delayed_inputs import load
from spireshift.native_natural_data import CONTRACT, LIMITS
from spireshift.native_situation_features import describe

PARENT = "configs/native-delayed/sts2-v0.111.0-a8-comparison-v1.json"
RESULT = "artifacts/native-delayed/sts2-v0.111.0-a8-comparison-v1/report.json"
BANK = "artifacts/native-natural/roots-v1/report.json"


def base(root: Path) -> dict[str, Any]:
    context = load(root, root / PARENT)
    report = identified(root / RESULT)
    if report["status"] != "delayed_comparison_complete" or report["fitting_passes_by_arm"] != {
        "learned": 2,
        "exact": 2,
    }:
        raise ValueError("Assess the completed delayed comparison before another intervention")
    check_sources(root, report["sources"])
    context["sources"].update(report["sources"])
    context["sources"][RESULT] = _sha_file(root / RESULT)
    return context


def rank(value: Any) -> str:
    return manifest_identifier(["natural-multiturn-outcome-blind-world-v1", value])


def eligible(public: dict[str, Any]) -> dict[str, Any] | None:
    if public["context"]["interaction"]["kind"] != "combat_turn":
        return None
    c = public["context"]["interaction"]["content"]["context"]
    if not (
        c.get("round", 0) >= 2
        and c.get("is_play_phase") is True
        and 3 <= len(public["candidates"]) <= 16
        and public["context"]["persistent"]["run"]["floor"] >= 5
        and sum(a["verb"] in {"play", "use"} for a in public["candidates"]) >= 2
    ):
        return None
    d = describe(public)
    if not d["relic_counters_available"]:
        raise ValueError("Never silently migrate a missing-counter historical root")
    return d


def choose(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Control, fitting and withheld worlds are disjoint before any native proposals."""
    selected, used = [], set()
    for p in (2, 3):
        available = [
            x
            for x in pool
            if x["player"] == p
            and x["world"] not in used
            and x["descriptor"]["encounter_type"] == "normal"
        ]
        if not available:
            raise ValueError("No natural normal-fight integration root for a preserved parent")
        pick = min(available, key=lambda x: (-x["descriptor"]["hp_fraction"], rank(x["key"])))
        selected.append({**pick, "partition": "control_fit" if p == 2 else "control_heldout"})
        used.add(pick["world"])
    worlds = sorted({x["world"] for x in pool} - used, key=rank)
    partition = {w: "heldout" if i % 4 == 0 else "fit" for i, w in enumerate(worlds)}
    for split, count in (("fit", 4), ("heldout", 2)):
        for p in (2, 3):
            for _ in range(count):
                available = [
                    x
                    for x in pool
                    if x["player"] == p
                    and x["world"] not in used
                    and partition[x["world"]] == split
                ]
                if not available:
                    raise ValueError("Preserve root quotas and public-only world assignment")
                previous = [x["descriptor"] for x in selected if x["partition"] == split]

                def novelty(
                    x: dict[str, Any], previous: list[dict[str, Any]] = previous
                ) -> tuple[int, str]:
                    d = x["descriptor"]
                    score = sum(
                        d[k] not in [r[k] for r in previous]
                        for k in (
                            "deck_signature",
                            "relic_signature",
                            "hp_band",
                            "floor_band",
                            "enemy_definitions",
                            "encounter_type",
                        )
                    )
                    return -score, rank(x["key"])

                pick = min(available, key=novelty)
                selected.append({**pick, "partition": split})
                used.add(pick["world"])
    return selected


def prepare(root: Path) -> dict[str, Any]:
    output = root / BANK
    if output.exists():
        saved = identified(output)
        check_sources(root, saved["sources"])
        return saved
    context = base(root)
    source = context["source"]
    sources = dict(context["sources"])
    manifest = identified(root / source["seed_manifest"]["path"], "manifest_id")
    train = {s["id"]: s for s in manifest["seeds"] if s["partition"] == "train"}
    pool, games = [], 0
    for player in (2, 3):
        for chunk in range(16):
            path = (
                root
                / source["workspace"]
                / f"chunks/train-p{player}-batch128-r02-c{chunk:02d}/done.json"
            )
            if str(path.relative_to(root)) not in sources:
                raise ValueError("Natural source must be sealed by the completed comparison")
            unit = identified(path)["result"]
            for name in unit["paths"]:
                header = json.loads((root / name).read_text())
                binding = header["binding"]
                seed = train[binding["seed_id"]]
                if (
                    binding["partition"] != "train"
                    or binding["panel_purpose"] != "training"
                    or binding["environment_id"] != source["environment_manifest"]["id"]
                    or binding["native_seed"] != seed["seed"]
                ):
                    raise ValueError("Read only completed own-policy repaired TRAIN episodes")
                case = read_native_episode(root / name, binding)
                if (
                    case["status"] != "terminal"
                    or case["privileged_fixture"]
                    or case["recovered"]
                    or not case["ordinary_PPO_eligible"]
                ):
                    raise ValueError("Incomplete or privileged sources cannot supply natural roots")
                seen = set()
                for i, row in enumerate(case["decisions"][: LIMITS["prefix_decisions"] + 1]):
                    d = eligible(row["public_input"])
                    if d is None:
                        continue
                    bucket = tuple(d["enemy_definitions"]), d["floor"]
                    if bucket in seen:
                        continue
                    seen.add(bucket)
                    pool.append(
                        {
                            "key": [name, i],
                            "episode": name,
                            "case_id": header["case_id"],
                            "decision": i,
                            "player": player,
                            "world": seed["seed"],
                            "seed_id": seed["id"],
                            "descriptor": d,
                        }
                    )
                games += 1
                del case
    if games != 256:
        raise ValueError("Retain all 256 declared TRAIN source attempts")
    roots = []
    for item in choose(pool):
        path = root / item["episode"]
        header = json.loads(path.read_text())
        case = read_native_episode(path, header["binding"])
        public = case["decisions"][item["decision"]]["public_input"]
        body = {
            **item,
            "pool": "control" if item["partition"].startswith("control_") else "main",
            "partition": item["partition"].removeprefix("control_"),
            "public_input": public,
            "public_input_id": manifest_identifier(public),
            "prefix": [
                {
                    "public_input_id": manifest_identifier(r["public_input"]),
                    "action_index": r["choice"]["action_index"],
                }
                for r in case["decisions"][: item["decision"]]
            ],
            "environment_id": source["environment_manifest"]["id"],
            "source_outcomes_used_for_selection": False,
        }
        roots.append({**body, "root_id": manifest_identifier(body)})
        del case
    sources["src/spireshift/native_natural_roots.py"] = _sha_file(Path(__file__))
    sources["src/spireshift/native_natural_data.py"] = _sha_file(
        root / "src/spireshift/native_natural_data.py"
    )
    body = {
        "schema_version": "natural-combat-root-bank-v1",
        "contract": CONTRACT,
        "roots": roots,
        "source_games": games,
        "candidate_roots": len(pool),
        "source_environment": source["environment_manifest"],
        "sources": sources,
        "root_selection_uses_final_outcomes": False,
        "games_launched": 0,
        "optimizer_steps": 0,
        "old_missing_counter_bank_migrated": False,
        "available_public_groups": sorted(
            {
                str(
                    (
                        x["descriptor"]["encounter_type"],
                        x["descriptor"]["floor_band"],
                        x["descriptor"]["hp_band"],
                    )
                )
                for x in pool
            }
        ),
        "selected_public_groups": sorted(
            {
                str(
                    (
                        x["descriptor"]["encounter_type"],
                        x["descriptor"]["floor_band"],
                        x["descriptor"]["hp_band"],
                    )
                )
                for x in roots
            }
        ),
        "complete_mechanics_coverage_claimed": False,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, report)
    return report
