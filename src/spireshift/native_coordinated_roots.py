"""Outcome-blind first-turn roots on TRAIN worlds excluded from the old teacher."""

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
from spireshift.native_natural_inputs import load
from spireshift.native_natural_roots import BANK as OLD_BANK
from spireshift.native_situation_features import describe

BANK = "artifacts/native-coordinated/roots-v1/report.json"
PREVIOUS = "artifacts/native-natural/sts2-v0.111.0-a8-comparison-v1/teacher/report.json"
ASSESSMENT = "artifacts/native-natural/main-assessment-v1/report.json"


def base(root: Path) -> dict[str, Any]:
    context = load(root, root / "configs/native-natural/sts2-v0.111.0-a8-comparison-v1.json")
    report, audit = identified(root / PREVIOUS), identified(root / ASSESSMENT)
    if (
        report["report_id"]
        != "sha256:11a4e1fddc5a5e658daa4395b4109be2732729f399d671ca3e6b6305fe2b196e"
        or audit["report_id"]
        != "sha256:896b1bd81ea597958d8e1270335c3493cba8eba5615c5f32d114f4e57b03e2cb"
        or not audit["valid"]
        or audit["teacher_report_id"] != report["report_id"]
        or report["gate"]["passed"]
    ):
        raise ValueError(
            "Preserve the assessed insufficient natural teacher; do not relax its gate"
        )
    for name, sha in report["sources"].items():
        if name in context["sources"] and context["sources"][name] != sha:
            raise ValueError("A preserved natural-teacher source changed")
    check_sources(root, {n: s for n, s in report["sources"].items() if n not in context["sources"]})
    context["sources"].update(report["sources"])
    context["sources"].update({p: _sha_file(root / p) for p in (PREVIOUS, ASSESSMENT)})
    return context


def rank(value: Any) -> str:
    return manifest_identifier(["first-turn-coordinated-whole-world-v1", value])


def eligible(public: dict[str, Any]) -> dict[str, Any] | None:
    c = public["context"]["interaction"]
    s = c.get("content", {}).get("context", {})
    if (
        c["kind"] != "combat_turn"
        or s.get("round") != 1
        or s.get("is_play_phase") is not True
        or public["context"]["persistent"]["run"]["floor"] < 5
        or not 3 <= len(public["candidates"]) <= 24
        or sum(a["verb"] in {"play", "use"} for a in public["candidates"]) < 2
    ):
        return None
    d = describe(public)
    if not d["relic_counters_available"]:
        raise ValueError("First-turn source requires actual repaired public counters")
    return d


def choose(pool: list[dict[str, Any]], excluded: set[str]) -> list[dict[str, Any]]:
    pool = [r for r in pool if r["world"] not in excluded]
    chosen: list[dict[str, Any]] = []
    used = set(excluded)
    for player in (2, 3):
        available = [
            r
            for r in pool
            if r["player"] == player
            and r["world"] not in used
            and r["descriptor"]["encounter_type"] == "normal"
            and len(r["descriptor"]["enemy_definitions"]) >= 2
        ]
        if not available:
            raise ValueError("No multi-enemy natural control root; do not replace with a fixture")
        pick = min(available, key=lambda r: (-r["descriptor"]["hp_fraction"], rank(r["key"])))
        chosen.append({**pick, "pool": "control", "partition": "control"})
        used.add(pick["world"])
    worlds = sorted({r["world"] for r in pool} - used, key=rank)
    split = {w: "fit" if i % 2 else "heldout" for i, w in enumerate(worlds)}
    for partition in ("fit", "heldout"):
        for player in (2, 3):
            for _ in range(2):
                available = [
                    r
                    for r in pool
                    if r["player"] == player
                    and r["world"] not in used
                    and split[r["world"]] == partition
                ]
                previous = [r["descriptor"] for r in chosen if r["partition"] == partition]

                def novelty(
                    r: dict[str, Any], previous: list[dict[str, Any]] = previous
                ) -> tuple[int, str]:
                    d = r["descriptor"]
                    return (
                        -sum(
                            d[k] not in [p[k] for p in previous]
                            for k in (
                                "enemy_definitions",
                                "encounter_type",
                                "hp_band",
                                "floor_band",
                                "deck_signature",
                                "relic_signature",
                            )
                        ),
                        rank(r["key"]),
                    )

                if not available:
                    raise ValueError("Insufficient whole-world first-turn source coverage")
                pick = min(available, key=novelty)
                chosen.append({**pick, "pool": "main", "partition": partition})
                used.add(pick["world"])
    return chosen


def prepare(root: Path) -> dict[str, Any]:
    output = root / BANK
    if output.exists():
        saved = identified(output)
        check_sources(root, saved["sources"])
        return saved
    context = base(root)
    source = context["source"]
    sources = dict(context["sources"])
    old = identified(root / OLD_BANK)
    excluded = {r["world"] for r in old["roots"]}
    manifest = identified(root / source["seed_manifest"]["path"], "manifest_id")
    seeds = {s["id"]: s for s in manifest["seeds"] if s["partition"] == "train"}
    pool, games = [], 0
    for player in (2, 3):
        for chunk in range(16):
            name = (
                source["workspace"] + f"/chunks/train-p{player}-batch128-r02-c{chunk:02d}/done.json"
            )
            if name not in sources:
                raise ValueError("Only sealed repaired completed TRAIN episodes supply roots")
            for path in identified(root / name)["result"]["paths"]:
                header = json.loads((root / path).read_text())
                binding = header["binding"]
                seed = seeds[binding["seed_id"]]
                if (
                    binding["partition"] != "train"
                    or binding["panel_purpose"] != "training"
                    or binding["native_seed"] != seed["seed"]
                    or binding["environment_id"] != source["environment_manifest"]["id"]
                ):
                    raise ValueError("No evaluation or silently migrated sources")
                case = read_native_episode(root / path, binding)
                if (
                    case["status"] != "terminal"
                    or not case["ordinary_PPO_eligible"]
                    or case["recovered"]
                    or case["privileged_fixture"]
                ):
                    raise ValueError("First-turn roots require complete natural own-policy sources")
                seen = set()
                for i, step in enumerate(case["decisions"][:513]):
                    d = eligible(step["public_input"])
                    if d is None:
                        continue
                    # The first offered play menu in this room, never later hand-picked moves.
                    bucket = d["floor"], tuple(d["enemy_definitions"])
                    if bucket not in seen:
                        seen.add(bucket)
                        pool.append(
                            {
                                "key": [path, i],
                                "episode": path,
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
        raise ValueError("Preserve the full 256-source denominator")
    roots = []
    for item in choose(pool, excluded):
        header = json.loads((root / item["episode"]).read_text())
        case = read_native_episode(root / item["episode"], header["binding"])
        p = case["decisions"][item["decision"]]["public_input"]
        body = {
            **item,
            "entry": "early",
            "public_input": p,
            "public_input_id": manifest_identifier(p),
            "prefix": [
                {
                    "public_input_id": manifest_identifier(s["public_input"]),
                    "action_index": s["choice"]["action_index"],
                }
                for s in case["decisions"][: item["decision"]]
            ],
            "environment_id": source["environment_manifest"]["id"],
            "source_outcomes_used_for_selection": False,
        }
        roots.append({**body, "root_id": manifest_identifier(body)})
    sources["src/spireshift/native_coordinated_roots.py"] = _sha_file(Path(__file__))
    body = {
        "schema_version": "coordinated-first-turn-root-bank-v1",
        "roots": roots,
        "source_games": games,
        "candidate_roots": len(pool),
        "sources": sources,
        "excluded_old_teacher_worlds": sorted(excluded),
        "games_launched": 0,
        "optimizer_steps": 0,
        "root_selection_uses_final_outcomes": False,
        "late_roots_derived_from_new_greedy_reference_only": True,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result
