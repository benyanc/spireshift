"""Loss-only sparse storage: immutable integer positions and exact float64 values.

Keep the qualified public encoder and numerical PPO kernel unchanged. Stream one
episode at a time into compact rows so larger independent-game batches fit in RAM.
"""

from __future__ import annotations

import json
import math
from array import array
from bisect import bisect_left
from collections.abc import ItemsView, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.full_run_ppo_math import Sample
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_game import verified_samples
from spireshift.native_value_credit import cross_fitted_predictions, prediction_metrics, value_run
from spireshift.training_objective import TrainingScoreSpec


class PackedItems(ItemsView[int, float]):
    def __init__(self, row: PackedRow) -> None:
        super().__init__(row)
        self.row = row

    def __iter__(self) -> Iterator[tuple[int, float]]:
        row = self.row
        yield from zip(row.positions, row.amounts, strict=True)


class PackedRow(Mapping[int, float]):
    """Read-only Mapping accepted by the frozen kernel's row.items() interface."""

    __slots__ = ("positions", "amounts")

    def __init__(self, row: dict[int, float]) -> None:
        if any(
            type(i) is not int or not 0 <= i < 65536 or not math.isfinite(v) for i, v in row.items()
        ):
            raise ValueError("Invalid compact loss coordinate")
        items = sorted(row.items())
        self.positions = memoryview(array("H", (i for i, _ in items)).tobytes()).cast("H")
        self.amounts = memoryview(array("d", (v for _, v in items)).tobytes()).cast("d")

    def __getitem__(self, index: int) -> float:
        i = bisect_left(self.positions, index)
        if i == len(self.positions) or self.positions[i] != index:
            raise KeyError(index)
        return float(self.amounts[i])

    def __iter__(self) -> Iterator[int]:
        yield from self.positions

    def __len__(self) -> int:
        return len(self.positions)

    def items(self) -> ItemsView[int, float]:
        return PackedItems(self)


def pack(sample: Sample) -> Sample:
    # The historical annotation is dict, but the pinned kernel reads only .items()
    # and lengths. The Mapping view preserves every coordinate and float64 bit.
    rows = tuple(cast(dict[int, float], PackedRow(row)) for row in sample.rows)
    return replace(sample, rows=rows)


def prepare_compact(
    paths: list[Path],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    credit: dict[str, Any],
    index: int,
) -> tuple[list[Sample], dict[str, Any]]:
    runs = []
    samples: list[Sample] = []
    for path in paths:
        header = json.loads(path.read_text())
        binding = header["binding"]
        if (
            binding["partition"] not in {"train", "control"}
            or binding["panel_purpose"] != "training"
            or binding["model_id"] != model.model_id
            or binding["environment_id"] != model.actor.environment_id
            or binding["training_spec_id"] != score.spec_id
        ):
            raise ValueError("Compact training requires its own current-behavior training games")
        case = read_native_episode(path, binding)
        if case["status"] != "terminal":
            continue
        case["score"] = score_episode(case, binding["seed_id"], score)
        runs.append(value_run(case, binding["seed_id"], index, score))
        # Never retain raw public/native histories across games.
        original = verified_samples(
            case, model, score, case["score"]["training_return"], settings["temperature"]
        )
        samples.extend(pack(s) for s in original)
        del case, original
    if len(runs) < 2 or len({r.seed for r in runs}) != len(runs):
        raise ValueError("Compact cross-fitting needs distinct clean whole games")
    predictions, folds = cross_fitted_predictions(
        sorted(runs, key=lambda r: r.seed),
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    values = [v for run in runs for v in predictions[run.seed]]
    samples = [replace(s, advantage=s.target - v) for s, v in zip(samples, values, strict=True)]
    body = {
        "round": index,
        "clean_complete_training_games": len(runs),
        "decisions": len(samples),
        "choice_decisions": sum(len(s.rows) > 1 for s in samples),
        "cross_fit": folds,
        "prediction_quality": prediction_metrics(sorted(runs, key=lambda r: r.seed), predictions),
        "no_self_outcome_fitting": all(
            set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in folds
        ),
        "discount": 1.0,
        "trace_lambda": 1.0,
        "hand_written_HP_rewards": False,
        "oracle_labels": 0,
        "row_storage": "readonly_sparse_uint16_float64_v1",
        "maximum_raw_episode_histories_retained": 1,
        "all_source_decisions_retained": True,
    }
    return samples, {**body, "report_id": manifest_identifier(body)}
