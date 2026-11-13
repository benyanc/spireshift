"""Admit the sealed A8 demonstrations as complete public menu choices."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_archive_batch import WIN, known_seeds, summarize
from spireshift.native_a8_archive_batch_v5 import adapter_study
from spireshift.native_a8_bank_fit import (
    ACTOR_RATE,
    GRADIENT_CLIP,
    TEMPERATURE,
    Decision,
    Factor,
    Worlds,
)
from spireshift.native_a8_mix_session import WORKER, Study, admit
from spireshift.native_a8_own_policy import CONTRACT
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compact_training import PackedRow
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_flow_verification_v12 import records
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_structured_model import encode
from spireshift.native_win4_plan import PLAN
from spireshift.native_win_teacher import validate_student_input
from spireshift.training_objective import TrainingScoreSpec

SCHEMA = "native-a8-archive-copy-fit-v1"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-archive-copy-fit-v1.json"
WRAPPER = "scripts/fit-and-compare-a8-archive-v1.sh"
PER_WORLD = 8
UPDATES = 112
CONTROL_UPDATES = 2
FIT = {
    "updates_per_copy": UPDATES,
    "draws_per_world_per_update": PER_WORLD,
    "actor_learning_rate": ACTOR_RATE,
    "gradient_clip": GRADIENT_CLIP,
    "temperature": TEMPERATURE,
}
CONTROL: dict[str, Any] = {
    "prefix_world": "SP1RESH1FTA8ARF1C001",
    "ending_world": "SP1RESH1FTA8ARF1C002",
    "updates_per_copy": CONTROL_UPDATES,
}
LIMITS = {
    "wall_seconds": 2400,
    "cpu_seconds": 3600,
    "storage_bytes": 4_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
SHORT_LIMITS = {**LIMITS, "wall_seconds": 250, "cpu_seconds": 420}


@dataclass(frozen=True)
class ArchiveFit:
    base: Study
    cfg: dict[str, Any]
    bank: dict[str, Any]
    audit: dict[str, Any]
    frozen_checks: dict[str, bool]


def implementation(root: Path) -> dict[str, str]:
    files = {
        WRAPPER,
        *(f"scripts/{name}" for name in worker_helpers(root, WORKER)),
        *(f"scripts/{name}" for name in worker_helpers(root, "engine-shared-input-v16.mjs")),
        *(
            f"src/spireshift/{name}.py"
            for name in (
                "full_run_policy",
                "full_run_ppo_math",
                "native_a8_archive_batch",
                "native_a8_archive_batch_v5",
                "native_a8_archive_fit_inputs",
                "native_a8_archive_fit_session",
                "native_a8_bank_fit",
                "native_a8_mix_session",
                "native_a8_own_experience",
                "native_a8_own_policy",
                "native_a8_paired_report",
                "native_compact_training",
                "native_context_journal",
                "native_live_policy",
                "native_policy_updates",
                "native_structured_model",
                "native_structured_policy",
                "native_structured_state",
                "native_win4_game",
                "native_win4_plan",
                "resource_tracking",
            )
        ),
    }
    return {name: _sha_file(root / name) for name in sorted(files)}


def archive_fit(root: Path) -> ArchiveFit:
    cfg = json.loads((root / RECIPE).read_text())
    bank_path = verified(root, cfg["archive_result"])
    bank = identified(bank_path)
    audit = identified(verified(root, cfg["learner_input_audit"]))
    bank_cfg = json.loads(verified(root, cfg["archive_config"]).read_text())
    store = ChunkJournal(root, bank_cfg)
    base = admit(root)
    checks = frozen(root, base.ctx)
    objective = ObjectiveSpec.from_mapping(cfg["objective"])
    worlds = bank["coverage"]["bank"]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["fit"] != FIT
        or cfg["control"] != CONTROL
        or cfg["limits"] != LIMITS
        or cfg["control_limits"] != SHORT_LIMITS
        or cfg["policy_contract"] != CONTRACT
        or SETTINGS["temperature"] != TEMPERATURE
        or cfg["score_id"] != base.ctx["score"].spec_id
        or objective != base.ctx["score"].evaluation_objective
        or cfg["objective"] != bank_cfg["objective"]
        or cfg["game_limits"] != bank_cfg["game_limits"]
        or cfg["game_limits"] != base.cfg["game_limits"]
        or cfg["runtime_id"] != manifest_identifier(base.runtime)
        or cfg["original_state_ids"] != {str(p): base.originals[p][2] for p in PLAYERS}
        or cfg["environment_id"] != base.ctx["environment_id"]
        or bank["environment_id"] != cfg["environment_id"]
        or audit["environment_id"] != cfg["environment_id"]
        or bank_path.parent != store.workspace
        or bank["config_id"] != store.config_id
        or bank["status"] != "archive_bank_candidate"
        or not bank["coverage"]["candidate_for_separate_fitting_admission"]
        or json.loads(json.dumps(summarize(bank_cfg, bank["worlds"]))) != bank["coverage"]
        or len(worlds) != 3
        or set(bank["seals"]) != {case["run_id"] for case in bank_cfg["cases"]}
        or audit["status"] != "verified_full_menu_inputs_for_copy_fitting"
        or audit["source_bank_report_id"] != bank["report_id"]
        or audit["initializers"] != list(PLAYERS)
        or audit["worlds"].keys() != worlds.keys()
        or audit["total_native_decisions"] != 2380
        or bank["optimizer_updates"] != 0
        or audit["optimizer_updates"] != 0
        or bank["final_test_worlds_used"] is not False
        or bank["frozen_checks"] != checks
        or audit["frozen_checks"] != checks
        or not all(checks.values())
        or cfg["implementation"] != implementation(root)
    ):
        raise ValueError("Require the exact qualified archive bank and frozen fitting inputs")

    development, final_test = cfg["development"], cfg["final_test"]
    training = {ref["seed"] for ref in worlds.values()}
    control = [CONTROL["prefix_world"], CONTROL["ending_world"]]
    seeds = [*development, *final_test, *control, *training]
    if (
        bank["seed_ownership"] != {"development": development, "final_test": final_test}
        or audit["seed_ownership"] != bank["seed_ownership"]
        or len(development) != 12
        or len(final_test) != 12
        or len(training) != len(worlds)
        or len(seeds) != len(set(seeds))
        or set(seeds) & known_seeds(base)
        or set(development + final_test + control) & {c["seed"] for c in bank_cfg["cases"]}
        or any(seed != canonical_seed(seed) for seed in seeds)
        or cfg["control_workspace"] == cfg["workspace"]
    ):
        raise ValueError(
            "Archive training, controls, development and final-test worlds must be disjoint"
        )

    for case in bank_cfg["cases"]:
        key = case["run_id"]
        seal, row = store.completed(key, case), bank["worlds"][key]
        if seal is None or seal["report_id"] != bank["seals"][key] or seal["result"] != row:
            raise ValueError("A sealed archive case differs from the qualified result")
        if row["status"] == WIN:
            facts = audit["worlds"][key]
            labels = row["labels"]
            if (
                worlds[key] != {**labels, "seed": case["seed"]}
                or facts["labels"] != labels
                or seal["sources"].get(labels["path"]) != labels["sha256"]
                or (facts["seed"], facts["decisions"], facts["factors"])
                != (case["seed"], row["decisions"], row["deliveries"])
            ):
                raise ValueError("Only the sealed winning worlds may supply exact public labels")

    check_sources(root, bank_cfg["replay_implementation"])
    return ArchiveFit(adapter_study(base, bank_cfg), cfg, bank, audit, checks)


def encode_answer(
    row: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> Decision:
    if set(row) != {"act", "family", "factors"} or not row["factors"]:
        raise ValueError("Expected a complete archive decision")
    factors = []
    selected: list[int] = []
    for index, item in enumerate(row["factors"]):
        public, action = item["public_input"], item["action_index"]
        validate_student_input(public)
        context = public["context"]
        owner, candidates = context["interaction"], public["candidates"]
        if (
            context["persistent"]["run"]["act"] != row["act"]
            or owner["kind"] != row["family"]
            or type(action) is not int
            or not 0 <= action < len(candidates)
        ):
            raise ValueError("Archive choice is outside the current public menu")
        surface = owner["content"].get("surface", {})
        if surface.get("selection_contract") == PLAN:
            chosen = candidates[action]
            final = index + 1 == len(row["factors"])
            if (
                owner["kind"] != "card_selection"
                or surface["answer_plan"]["selected"] != selected
                or chosen["verb"] not in ({"confirm", "cancel"} if final else {"select"})
            ):
                raise ValueError(
                    "An ordered answer must contain its exact public prefixes and commit"
                )
            if not final:
                (slot,) = (
                    i
                    for i, card in enumerate(surface["cards"])
                    if card["entity_id"]["public_slot"] == chosen["subject"]["public_slot"]
                )
                if slot in selected:
                    raise ValueError("An ordered answer repeated a selected card")
                selected.append(slot)
        elif len(row["factors"]) != 1:
            raise ValueError("Only an ordered answer may span multiple menus")
        rows, _ = encode(public, model, score)
        if len(rows) != len(candidates):
            raise ValueError("Every advertised action must reach the learner")
        packed = tuple(cast(dict[int, float], PackedRow(features)) for features in rows)
        factors.append(Factor(packed, action, manifest_identifier(public)))
    return Decision(row["family"], tuple(factors))


def dataset(study: ArchiveFit, deadline: float) -> Worlds:
    base = study.base
    left, right = (base.originals[p][0] for p in PLAYERS)

    def contract(model: CachedContextModel) -> tuple[Any, ...]:
        return (
            model.mode,
            model.feature_spec_id,
            model.actor.dimension,
            model.actor.input_normalization,
        )

    if (
        type(left) is not CachedContextModel
        or type(right) is not CachedContextModel
        or contract(left) != contract(right)
    ):
        raise ValueError("Both initializers must use the same frozen full-menu encoder")
    worlds = {}
    for key, reference in study.bank["coverage"]["bank"].items():
        path = verified(base.root, reference)
        labels = []
        by_act: dict[str, Counter[str]] = defaultdict(Counter)
        for raw in records(path):
            if time.monotonic() >= deadline:
                raise TimeoutError("Archive encoding reached the study deadline")
            labels.append(encode_answer(raw, left, base.ctx["score"]))
            by_act[str(raw["act"])][raw["family"]] += 1
        facts = study.bank["worlds"][key]
        if (
            len(labels) != facts["decisions"]
            or sum(len(label.factors) for label in labels) != facts["deliveries"]
            or by_act != facts["by_act"]
            or _sha_file(path) != reference["sha256"]
        ):
            raise ValueError("Encoded decisions differ from the sealed winning world")
        worlds[reference["seed"]] = tuple(labels)
    if max(map(len, worlds.values())) != UPDATES * PER_WORLD:
        raise ValueError("The predeclared schedule must visit every decision")
    return worlds
