"""Keep correction fitting error, inner validation and penalty visually separate."""

from __future__ import annotations

import csv
import importlib
from pathlib import Path
from typing import Any

from spireshift.native_linear_value import REGULARIZATION


def curve_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cohort": result["cohort"],
            "outer_fold": result["fold"],
            "inner_fold": inner["fold"],
            "fitting_games": len(inner["fitting_games"]),
            "validation_games": len(inner["validation_games"]),
            "selected_after_inner_validation": result["selected"]["regularization"]
            == point["regularization"],
            **{k: v for k, v in point.items() if k != "parameter_digest"},
        }
        for result in results
        for inner in result["inner"]
        for point in inner["path"]
    ]


def write_curves(
    directory: Path, results: list[dict[str, Any]], complete: bool, snapshot: int
) -> tuple[Path, Path]:
    prefix = "correction-curves" if complete else f"progress-{snapshot:04}-correction-curves"
    csv_path, png_path = directory / (prefix + ".csv"), directory / (prefix + ".png")
    if csv_path.exists() or png_path.exists():
        raise FileExistsError("Preserve earlier correction curves")
    rows = curve_rows(results)
    with csv_path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["regularization"])
        writer.writeheader()
        writer.writerows(rows)
    matplotlib = importlib.import_module("matplotlib")
    matplotlib.use("Agg")
    plt = importlib.import_module("matplotlib.pyplot")
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
    try:
        for axis, key, title in zip(
            axes,
            ("fitting_mse", "validation_clipped_mse", "correction_penalty"),
            ("Fitting prediction error", "Inner whole-game validation error", "Rich penalty only"),
            strict=True,
        ):

            def average(value: float | None, key: str = key) -> float:
                selected = [r for r in rows if r["regularization"] == value]
                mass_key = "validation_games" if key.startswith("validation") else "fitting_games"
                mass = sum(r[mass_key] for r in selected)
                return sum(r[key] * r[mass_key] for r in selected) / mass if mass else 0

            axis.plot(REGULARIZATION, [average(v) for v in REGULARIZATION], label="Rich correction")
            axis.axhline(average(None), linestyle="--", color="black", label="No correction")
            axis.set(xscale="log", xlabel="Separate rich regularization", title=title)
            axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
            axis.grid(alpha=0.2)
            axis.legend(fontsize=8)
        fig.suptitle("Fixed coarse predictor; saved TRAIN development, no player updates")
        fig.savefig(png_path, dpi=150)
    finally:
        plt.close(fig)
    return csv_path, png_path
