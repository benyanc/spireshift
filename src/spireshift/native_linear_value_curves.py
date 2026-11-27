"""Separate fitting error, validation error and penalties along the fixed ridge grid."""

from __future__ import annotations

import csv
import importlib
from pathlib import Path
from typing import Any

from spireshift.native_linear_value import ARMS, REGULARIZATION


def curve_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cohort": result["cohort"],
            "outer_fold": result["fold"],
            "arm": arm,
            "inner_fold": inner["fold"],
            "fitting_games": len(inner["fitting_games"]),
            "validation_games": len(inner["validation_games"]),
            "selected_after_all_inner_folds": result["selected"][arm]["regularization"]
            == point["regularization"],
            **{key: value for key, value in point.items() if key != "parameter_digest"},
        }
        for result in results
        for arm in ARMS
        for inner in result["inner"][arm]
        for point in inner["path"]
    ]


def write_curves(
    directory: Path, results: list[dict[str, Any]], complete: bool, snapshot: int
) -> tuple[Path, Path]:
    prefix = "validation-curves" if complete else f"progress-{snapshot:04}-validation-curves"
    csv_path, png_path = directory / (prefix + ".csv"), directory / (prefix + ".png")
    if csv_path.exists() or png_path.exists():
        raise FileExistsError("Preserve earlier linear-validation curves")
    rows = curve_rows(results)
    with csv_path.open("x", newline="") as stream:
        fields = list(rows[0]) if rows else ["cohort", "outer_fold", "arm", "regularization"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    matplotlib = importlib.import_module("matplotlib")
    matplotlib.use("Agg")
    plt = importlib.import_module("matplotlib.pyplot")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    try:
        for axis, arm in zip(axes, ARMS, strict=True):
            for key, label, style in (
                ("fitting_mse", "Fitting prediction error", "-"),
                ("validation_mse", "Inner whole-game validation error", "--"),
                ("weight_penalty", "Weight penalty (separate)", ":"),
            ):
                values = []
                for value in REGULARIZATION:
                    selected = [r for r in rows if r["arm"] == arm and r["regularization"] == value]
                    mass_key = (
                        "validation_games" if key.startswith("validation") else "fitting_games"
                    )
                    mass = sum(r[mass_key] for r in selected)
                    values.append(sum(r[key] * r[mass_key] for r in selected) / mass if mass else 0)
                axis.plot(REGULARIZATION, values, style, label=label)
            axis.set(
                xscale="log",
                yscale="log",
                xlabel="Ridge strength",
                ylabel="Equal-game error / penalty",
            )
            axis.set_title(arm.replace("_", " ").capitalize())
            axis.grid(alpha=0.2)
            axis.legend(fontsize=8)
        fig.suptitle("Saved TRAIN development: nested validation, no player updates")
        fig.savefig(png_path, dpi=150)
    finally:
        plt.close(fig)
    return csv_path, png_path
