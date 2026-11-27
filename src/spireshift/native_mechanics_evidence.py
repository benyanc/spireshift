"""Audit saved model menus and exercise the new encoder without fitting."""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift import native_a8_archive_fit_inputs as learner
from spireshift import native_a8_card_display_model as display
from spireshift import native_a8_card_display_study as source
from spireshift import native_combat_intent_model as intents
from spireshift.engine_learning import identified
from spireshift.native_a8_head_policy import HeadChooser, save
from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.training_objective import TrainingScoreSpec

RESULT = "sha256:e727767ce10b62a654f91d14b54e0e505e65a26bdc95e7a247401920a577d18e"


def sealed(store: ChunkJournal, key: str, seal_id: str) -> dict[str, Any]:
    task = json.loads((store.path(key) / "active.json").read_text())["request"]
    seal = store.completed(key, task)
    if seal is None or seal["report_id"] != seal_id:
        raise ValueError(f"Require the exact latest card-display evidence for {key}")
    return dict(seal["result"])


def audit(root: Path, score: TrainingScoreSpec, output: Path, deadline: float) -> dict[str, Any]:
    cfg = json.loads((root / source.RECIPE).read_text())
    check_sources(root, cfg["implementation"])
    store = ChunkJournal(root, cfg)
    report = identified(store.workspace / "report.json")
    if (
        report["report_id"] != RESULT
        or report["status"] != source.COMPLETE
        or report["config_id"] != store.config_id
        or report["verified_games"] != 128
        or len(report["game_seals"]) != 128
        or not all(report["frozen_checks"].values())
    ):
        raise ValueError("Require all 128 sealed latest frozen native games")
    totals: Counter[str] = Counter()
    advertised: Counter[tuple[str, str, str]] = Counter()
    transitions: Counter[tuple[str, str, str, str]] = Counter()
    examples: dict[str, tuple[dict[str, Any], int, int]] = {}
    finals = {}
    for key, seal_id in sorted(report["game_seals"].items()):
        if time.monotonic() >= deadline:
            raise TimeoutError("The saved native menu audit reached its time limit")
        result = sealed(store, key, seal_id)
        path = store.path(key)
        if result["outcome"] not in {"loss", "win"}:
            raise ValueError("The mechanics corpus includes an incomplete game")
        last = None
        before = totals["corrected_menus"]
        deliveries = 0
        for group in groups(path, result["model_id"]):
            frame, choice = group[-1]
            family = frame["source_family"]
            if last is not None:
                transitions[(*last, group[0][0]["source_family"])] += 1
            candidate = frame["public_input"]["candidates"][choice["action_index"]]
            last = (family, candidate["verb"], (candidate.get("subject") or {}).get("role", ""))
            deliveries += 1
            for factor, selected in group:
                public = factor["public_input"]
                owner = factor["source_family"]
                totals["menus"] += 1
                totals["combat_menus"] += owner == "combat_turn"
                corrected = False
                for i, offered in enumerate(public["candidates"]):
                    subject = (offered.get("subject") or {}).get("role", "")
                    advertised[owner, offered["verb"], subject] += 1
                    amount = intents.candidate_attack(offered)
                    if amount is None:
                        continue
                    totals["enemy_bound_rows"] += 1
                    targets = [
                        arg["entity"]["properties"]
                        for arg in offered["arguments"]
                        if arg["role"] == "target"
                        and (arg.get("entity") or {}).get("role") == "enemy"
                    ]
                    old = sum(intent.get("damage", 0) for intent in targets[-1]["intents"])
                    if amount != old:
                        totals["corrected_rows"] += 1
                        totals["corrected_sampled_actions"] += i == selected["action_index"]
                        examples.setdefault("multi_hit", (public, i, amount))
                        corrected = True
                totals["corrected_menus"] += corrected
        if deliveries != result["native_decisions"] or last is None:
            raise ValueError("Saved delivery count differs from the sealed game")
        # The final frame is an observed native boundary with no model submission.
        _, final, submitted = next(row for row in decisions(path / TRACE) if row[2] is None)
        if submitted is not None or not final["terminal"]:
            raise ValueError("The saved trace lacks a genuine ending")
        transitions[(*last, final["source_family"])] += 1
        totals["native_deliveries"] += deliveries
        totals["affected_games"] += totals["corrected_menus"] > before
        totals["games"] += 1

    fit_records = {row["player"]: row for row in report["fits"]}
    for player in PLAYERS:
        fit = fit_records[player]
        result = sealed(store, f"fit-p{player}", fit["seal_id"])
        path = store.path(f"fit-p{player}") / "shared.json"
        parent, parent_id = display.load(path)
        if (
            parent_id != report["final_states"][str(player)]
            or result["states"]["shared"]["state_id"] != parent_id
        ):
            raise ValueError("The frozen current model copy differs from the sealed fit")
        copied = intents.copy_with_intents(parent)
        target = output / f"intent-player-{player}.json"
        state_id = save(target, copied)
        restored, restored_id = intents.load(target)
        if (
            restored_id != state_id
            or restored != copied
            or copied.model.model_id == parent.model.model_id
            or copied.model.weights() != parent.model.weights()
            or copied.actor_adam != parent.actor_adam
            or copied.value_adam != parent.value_adam
        ):
            raise ValueError("The repaired inputs changed the copied weights or full Adam")
        finals[str(player)] = {"source_state_id": parent_id, "copied_state_id": state_id}
        public, index, amount = examples["multi_hit"]
        old_rows, old_state = display.encode(public, parent.model, score)
        rows, state = intents.encode(public, restored.model, score)
        slot = intents.TARGET_ATTACK
        if (
            old_state != state
            or rows[index][slot] != math.asinh(amount) / 5
            or rows[index][slot] == old_rows[index][slot]
            or any(
                {j: x for j, x in a.items() if j != slot}
                != {j: x for j, x in b.items() if j != slot}
                for a, b in zip(rows, old_rows, strict=True)
            )
        ):
            raise ValueError("The saved control changed features beyond the bound intent amount")
        with intents.using_intent_encoder():
            chooser = HeadChooser(restored.model, score, "SP1RESH1FTM1XINTENT")
            chosen = chooser(public)
            labels = learner.encode_answer(
                {
                    "act": public["context"]["persistent"]["run"]["act"],
                    "family": public["context"]["interaction"]["kind"],
                    "factors": [{"public_input": public, "action_index": index}],
                },
                restored.model,
                score,
            )
            if (
                chooser.last is None
                or chooser.last[0] != rows
                or chosen["model_id"] != restored.model.model_id
                or labels.factors[0].rows[index][slot] != rows[index][slot]
                or len(labels.factors[0].rows) != len(public["candidates"])
            ):
                raise ValueError("Inference and the learner do not use the same corrected menu")
        if display.load(path)[1] != parent_id:
            raise ValueError("A frozen input checkpoint changed")
    return {
        "source_report_id": report["report_id"],
        "counts": dict(totals),
        "advertised": [
            {"owner": f, "verb": v, "subject": s, "rows": n}
            for (f, v, s), n in sorted(advertised.items())
        ],
        "delivered": [
            {"owner": f, "verb": v, "subject": s, "next_owner": nxt, "receipts": n}
            for (f, v, s, nxt), n in sorted(transitions.items())
        ],
        "copied_state_controls": finals,
        "inference_and_learner_encoder_match": True,
    }
