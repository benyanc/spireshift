"""A bounded public-menu probe from sixteen predeclared completed TRAIN games."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_experience_plan import plan, request
from spireshift.native_inventory_credit_data import verify_binding
from spireshift.native_situation_bank import extract_case
from spireshift.native_structured_inputs import exclude_worlds
from spireshift.native_teaching_diagnostic_inputs import HISTORY, local
from spireshift.native_teaching_diagnostic_metrics import remaining

SALT = "native-plan-teaching-diagnostic-public-probes-v1"


def rank(row: dict[str, Any]) -> str:
    return manifest_identifier([SALT, row["world"], row["decision"], row["public_input_id"]])


def select(rows: list[dict[str, Any]], limit: int, per_world_family: int) -> list[dict[str, Any]]:
    """Public-only deterministic sampling; no action, outcome or probability selection."""
    seen, counts = set(), Counter[tuple[str, str]]()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=rank):
        key = (row["world"], row["description"]["family"])
        if row["public_input_id"] in seen or counts[key] >= per_world_family:
            continue
        seen.add(row["public_input_id"])
        counts[key] += 1
        groups[key[1]].append(row)
    selected: list[dict[str, Any]] = []
    for i in range(max((len(v) for v in groups.values()), default=0)):
        for family in sorted(groups):
            if len(groups[family]) > i and len(selected) < limit:
                selected.append(groups[family][i])
    return selected


def historical_probes(
    root: Path, context: dict[str, Any], deadline: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg, sources = context["config"], context["sources"]
    ref = cfg["history_recipe"]
    if ref["path"] != HISTORY:
        raise ValueError("Use the declared historical TRAIN cohort, never current evaluations")
    source = json.loads(local(root, HISTORY).read_text())
    if manifest_identifier(source) != ref["id"]:
        raise ValueError("Historical recipe identity changed")
    ref = cfg["history_report"]
    if ref["path"] != source["workspace"] + "/report.json":
        raise ValueError("The historical report must belong to its recipe")
    report = identified(local(root, ref["path"]))
    if (
        report["report_id"] != ref["id"]
        or report["status"] != "native_experience_comparison_complete"
        or report["config_id"] != manifest_identifier(source)
        or report["completed_units"] != report["planned_units"]
        or source["environment_manifest"] != context["bank"]["runtime"]["environment_manifest"]
        or source["training_spec"] != context["bank"]["runtime"]["training_spec"]
        or any(sources.get(n) != h for n, h in report["sources"].items())
    ):
        raise ValueError("Require the already sealed, compatible completed historical source")
    for name in (HISTORY, ref["path"]):
        if sources.get(name) != _sha_file(local(root, name)):
            raise ValueError("Historical inputs must be sealed by the completed teaching source")
    manifest = identified(local(root, source["seed_manifest"]["path"]), "manifest_id")
    if manifest["manifest_id"] != source["seed_manifest"]["id"]:
        raise ValueError("Historical TRAIN manifest changed")
    tasks = {t["key"]: t for t in plan(source, manifest["seeds"])}
    journal = ChunkJournal(root, source)  # Read only; never lock or resume the source.
    probes, games = [], []
    counts: Counter[str] = Counter()
    for key in cfg["history_chunks"]:
        remaining(deadline)
        task = tasks[key]
        if task["kind"] != "collect" or task["round"] != 1 or task["player"] != 2:
            raise ValueError("Only the two frozen first-round TRAIN collections are eligible")
        expected = {s["id"]: s["seed"] for s in task["seeds"]}
        exclude_worlds(
            task["seeds"],
            [{"id": r["seed_id"], "seed": r["world"]} for r in context["bank"]["roots"]]
            + context["protected_config"]["evaluation_seeds"]
            + context["source"]["evaluation_seeds"],
        )
        sealed = journal.completed(
            key, request(task, {"initial-p2": context["states"][2]["initial"]})
        )
        if sealed is None:
            raise ValueError("Historical TRAIN chunks must already be committed")
        result = sealed["result"]
        if (
            result["kind"] != "collect"
            or result["failed_games"]
            or result["games_recorded"] != len(expected)
            or any(sources.get(n) != h for n, h in sealed["sources"].items())
            or sources.get(str((journal.path(key) / "done.json").relative_to(root)))
            != _sha_file(journal.path(key) / "done.json")
        ):
            raise ValueError("Retain all expected clean, audited TRAIN sources")
        seen = set()
        for outcome in result["outcomes"]:
            remaining(deadline)
            seed = outcome["seed_id"]
            if (
                seed not in expected
                or seed in seen
                or outcome["status"] != "terminal"
                or not all(
                    outcome.get(k) is True
                    for k in (
                        "ordinary_PPO_eligible",
                        "native_delivery_audit_valid",
                        "all_behavior_probabilities_reconstructed",
                    )
                )
                or outcome["model_id"] != context["models"][2]["initial"].model_id
            ):
                raise ValueError("Reject missing, duplicate, evaluation or unaudited TRAIN games")
            seen.add(seed)
            path = local(root, outcome["episode_path"])
            wrapper = json.loads(path.read_text())
            verify_binding(wrapper["binding"], source, outcome["model_id"], expected)
            case = read_native_episode(path, wrapper["binding"])
            game = {
                "cohort": key,
                "source_ref": outcome["episode_path"],
                "world": expected[seed],
                "seed_id": seed,
                "model_id": outcome["model_id"],
                "player": 2,
                "arm": task["arm"],
                "round": 1,
            }
            refs, observed = extract_case(case, game, wrapper["case_id"], deadline)
            counts.update(observed)
            candidates = []
            for row in refs:
                public = case["decisions"][row["decision_index"]]["public_input"]
                public = {
                    **public,
                    "candidates": [
                        public["candidates"][i] for i in row["effective_candidate_indices"]
                    ],
                }
                if manifest_identifier(public) != row["effective_input_id"]:
                    raise ValueError("Historical effective menu changed during extraction")
                candidates.append(
                    {
                        "public_input": public,
                        "public_input_id": row["effective_input_id"],
                        "description": row["description"],
                        "world": expected[seed],
                        "decision": row["decision_index"],
                        "source": {
                            "episode_path": outcome["episode_path"],
                            "case_id": wrapper["case_id"],
                            "decision": row["decision_index"],
                        },
                    }
                )
            probes.extend(select(candidates, 128, cfg["per_world_family_cap"]))
            games.append({"seed_id": seed, "world": expected[seed], "case_id": wrapper["case_id"]})
            del case, candidates, refs
        if seen != set(expected):
            raise ValueError("Every predeclared historical TRAIN game must be accounted for")
    selected = select(probes, cfg["maximum_probe_states"], cfg["per_world_family_cap"])
    if len(games) != 16 or len({g["world"] for g in games}) != 16 or not selected:
        raise ValueError("The bounded probe requires sixteen distinct completed TRAIN worlds")
    return selected, {
        "source_report_id": report["report_id"],
        "games": games,
        "raw_source_counts": dict(counts),
        "probe_states": len(selected),
        "worlds_in_probe": len({r["world"] for r in selected}),
        "families": dict(Counter(r["description"]["family"] for r in selected)),
        "deck_signatures": len({r["description"]["deck_signature"] for r in selected}),
        "relic_state_signatures": len({r["description"]["relic_signature"] for r in selected}),
        "available_families_missing_from_probe": sorted(
            {r["description"]["family"] for r in probes}
            - {r["description"]["family"] for r in selected}
        ),
        "selection_uses_actions_probabilities_or_final_outcomes": False,
        "observed_menu_distribution_is_natural_gameplay_distribution": False,
        "source_behavior_and_native_audits_reused_not_recomputed": True,
        "maximum_raw_episode_histories_retained": 1,
        "current_experiment_training_or_evaluation_records_decoded": 0,
    }
