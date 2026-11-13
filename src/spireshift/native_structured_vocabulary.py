"""Fit a bounded named-fact layout from varied saved TRAIN inputs, never outcomes.

Family-balanced, equal-game document frequency prevents combat row counts from
consuming every column. Full public inputs still reach the original encoder.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode
from spireshift.engine_learning import identified
from spireshift.engine_neural import public_tokens, validate_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources
from spireshift.native_shop_policy import ShopNavigation

TEXT = {"label", "description", "formatted_description", "flavor", "text", "title"}
REQUIRED = {"combat_turn", "rest_site", "shop_inventory", "card_reward_selection", "map_navigation"}
HIDDEN = {"rng", "rng_state", "random_seed", "seed", "draw_order", "draw_pile_order", "hidden"}


def validate(public: dict[str, Any]) -> None:
    validate_public_input(public)

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.keys() & HIDDEN:
                raise ValueError("Private future or RNG information reached structured input")
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(public)


@lru_cache(maxsize=100000)
def eligible(name: str) -> bool:
    return not (set(name.split("=", 1)[0].split("/")) & TEXT)


def facts(public: dict[str, Any]) -> tuple[dict[str, float], ...]:
    validate(public)
    shared: dict[str, float] = {}
    public_tokens(public["context"], "state", shared)
    shared = {n: v for n, v in shared.items() if eligible(n)}
    result = []
    for candidate in public["candidates"]:
        values: dict[str, float] = {}
        public_tokens(candidate, "candidate", values)
        # Zero is a known observed field too. Reserve its column when fitting the
        # layout so a free card's later nonzero cost is not an unfamiliar field.
        result.append({**shared, **{n: v for n, v in values.items() if eligible(n)}})
    return tuple(result)


def select_columns(counts: dict[str, Counter[str]], size: int) -> tuple[str, ...]:
    if size < 1 or not counts:
        raise ValueError("Choose a positive finite named-input vocabulary")
    ranked = {family: sorted(c, key=lambda n: (-c[n], n)) for family, c in counts.items()}
    selected: set[str] = set()
    for index in range(max(map(len, ranked.values()))):
        for family in sorted(ranked):
            if index < len(ranked[family]):
                selected.add(ranked[family][index])
                if len(selected) == size:
                    return tuple(sorted(selected))
    raise ValueError("The source does not supply enough distinct public named facts")


def build(root: Path, source: Path, output: Path, *, size: int = 1024) -> dict[str, Any]:
    report = identified(source)
    if report["status"] != "native_policy_update_comparison_complete":
        raise ValueError("Use the completed clean comparison's TRAIN inputs only")
    check_sources(root, report["sources"])
    if output.exists():
        cached = identified(output)
        if cached["source_report_id"] != report["report_id"] or cached["size"] != size:
            raise ValueError("Preserve the named layout under its original TRAIN source")
        check_sources(root, cached["sources"])
        return cached
    if (
        output.with_name("examples.json").exists()
        or output.with_name("fact-inventory.json").exists()
    ):
        raise FileExistsError("Preserve unfinished named-layout evidence before another build")
    workspace = source.parent
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    families: Counter[str] = Counter()
    source_files = {str(source.relative_to(root)): _sha_file(source)}
    games, seeds, input_ids = 0, set(), set()
    examples: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for receipt in sorted((workspace / "chunks").glob("train-*/done.json")):
        saved = identified(receipt)
        check_sources(root, saved["sources"])
        for name in saved["result"]["paths"]:
            path = root / name
            header = json.loads(path.read_text())
            bound = header["binding"]
            if bound["partition"] != "train" or bound["panel_purpose"] != "training":
                raise ValueError("No development/test/privileged inputs may fit the vocabulary")
            case = read_native_episode(path, bound)
            if case["status"] != "terminal" or case["privileged_fixture"] is not False:
                raise ValueError("Use only complete unprivileged source games")
            per_game: dict[str, set[str]] = defaultdict(set)
            navigation = ShopNavigation()
            for row in case["decisions"]:
                public = row["public_input"]
                effective, _, forced = navigation.view(public)
                navigation.advance(public, row["choice"]["action_index"])
                if forced:
                    continue
                family = effective["context"]["interaction"]["kind"]
                families[family] += 1
                public_id = manifest_identifier(effective)
                input_ids.add(public_id)
                if len(examples[family]) < 4:
                    examples[family][public_id] = effective
                for tokens in facts(effective):
                    per_game[family].update(tokens)
            for family, names in per_game.items():
                counts[family].update(names)
            if sum(map(len, counts.values())) > 500000:
                raise ValueError("Vocabulary inventory exceeded its bounded memory scope")
            games += 1
            seeds.add(bound["native_seed"])
            for p in (path, path.with_suffix(".jsonl.gz"), receipt):
                source_files[str(p.relative_to(root))] = _sha_file(p)
            del case
    if games != 128 or not families.keys() >= REQUIRED:
        raise ValueError(
            "Require 128 saved TRAIN games spanning combat, shops, rest, rewards and paths"
        )
    columns = select_columns(dict(counts), size)
    examples_path = output.with_name("examples.json")
    atomic_json(
        examples_path,
        {
            "schema_version": "unlabelled_native_TRAIN_representation_examples_v1",
            "rows": [
                {"family": f, "public_input_id": i, "public_input": p}
                for f in sorted(examples)
                for i, p in sorted(examples[f].items())
            ],
        },
    )
    source_files[str(examples_path.relative_to(root))] = _sha_file(examples_path)
    inventory_path = output.with_name("fact-inventory.json")
    inventory = sorted(set().union(*(set(c) for c in counts.values())))
    atomic_json(
        inventory_path, {"schema_version": "native_TRAIN_fact_inventory_v1", "names": inventory}
    )
    source_files[str(inventory_path.relative_to(root))] = _sha_file(inventory_path)
    body = {
        "schema_version": "native-structured-vocabulary-v1",
        "builder_sha256": _sha_file(Path(__file__)),
        "source_report_id": report["report_id"],
        "size": size,
        "columns": list(columns),
        "vocabulary_id": manifest_identifier(
            {"schema": "frozen_named_public_fact_columns_v1", "columns": list(columns)}
        ),
        "selection": "sorted_family_round_robin_equal_game_document_frequency_v1",
        "free_text_in_supplement": False,
        "unknown_and_text_facts_retain_original_encoder": True,
        "source_games": games,
        "source_worlds": len(seeds),
        "distinct_source_public_inputs": len(input_ids),
        "source_decision_families": dict(sorted(families.items())),
        "examples_path": str(examples_path.relative_to(root)),
        "inventory_path": str(inventory_path.relative_to(root)),
        "observed_source_fact_names": len(inventory),
        "family_tokens_selected": {f: sum(n in counts[f] for n in columns) for f in sorted(counts)},
        "outcomes_or_chosen_actions_used_as_labels": False,
        "old_games_used_for_PPO": False,
        "new_games": 0,
        "optimizer_steps": 0,
        "sources": source_files,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result
