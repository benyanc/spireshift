"""CSV and standard matplotlib plots of fixed offline fitting snapshots."""

from __future__ import annotations

import csv
import importlib
from pathlib import Path
from typing import Any

from spireshift.native_matched_value import ARMS, PRIMARY_STEP

METRICS = (
    "fitting_mse",
    "fitting_clipped_mse",
    "held_mse",
    "held_clipped_mse",
    "weight_penalty",
    "regularized_fitting_loss",
)


def curve_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        for arm in ARMS:
            for point in result["fit"]["arms"][arm]["curve"]:
                rows.append(
                    {
                        "cohort": result["cohort"],
                        "fold": result["fold"],
                        "initializer": result["fit"]["network_initializer"],
                        "arm": arm,
                        "fitting_games": len(result["fit"]["fitting_games"]),
                        "held_games": len(result["fit"]["held_games"]),
                        **point,
                    }
                )
    return rows


def aggregate_curves(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows = curve_rows(results)
    return {
        arm: [
            {
                "step": step,
                **{
                    metric: sum(
                        row[metric] for row in rows if row["arm"] == arm and row["step"] == step
                    )
                    / sum(row["arm"] == arm and row["step"] == step for row in rows)
                    for metric in METRICS
                },
            }
            for step in sorted({row["step"] for row in rows if row["arm"] == arm})
        ]
        for arm in ARMS
    }


def write_curves(
    directory: Path, results: list[dict[str, Any]], complete: bool, snapshot: int | None = None
) -> list[Path]:
    """Aggregate fixed snapshots only; never choose an epoch from held errors."""
    rows = curve_rows(results)
    if not rows:
        return []
    stem = (
        "curves"
        if complete
        else ("progress-curves" if snapshot is None else f"progress-{snapshot:04}-curves")
    )
    csv_path = directory / f"{stem}.csv"
    output = directory / f"{stem}.png"
    if csv_path.exists() or output.exists():
        raise FileExistsError("Preserve existing curve artifacts; inspect the incomplete report")
    with csv_path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    matplotlib = importlib.import_module("matplotlib")
    matplotlib.use("Agg")
    plt = importlib.import_module("matplotlib.pyplot")
    curves = aggregate_curves(results)
    figure, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    labels = {"coarse_masked": "Basic information; extras masked", "rich": "Rich information"}
    panels = (
        ("fitting_mse", "Prediction error on fitting games"),
        ("held_mse", "Prediction error on withheld games"),
        ("weight_penalty", "Weight penalty alone"),
        ("regularized_fitting_loss", "Fitting error + weight penalty"),
    )
    for ax, (metric, title) in zip(axes.flat, panels, strict=True):
        for arm in ARMS:
            points = curves[arm]
            ax.plot(
                [p["step"] for p in points],
                [p[metric] for p in points],
                marker="o",
                markersize=3,
                label=labels[arm],
            )
        ax.axvline(PRIMARY_STEP, color="grey", linewidth=1, linestyle=":")
        if metric in {"fitting_mse", "held_mse"}:
            partition = "fit" if metric == "fitting_mse" else "held"
            reference = sum(
                r["reference_errors"]["current_ridge"][partition]["mse"] for r in results
            ) / len(results)
            ax.axhline(reference, color="black", linewidth=1, linestyle="--", label="Current ridge")
        ax.set_title(title)
        ax.set_xlabel("Optimizer updates (24 is the fixed primary comparison)")
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        ax.grid(alpha=0.2)
    axes.flat[0].legend(fontsize=8)
    count = len({(r["cohort"], game) for r in results for game in r["fit"]["held_games"]})
    figure.suptitle(
        f"{'Completed' if complete else 'Partial'} matched-input value diagnosis: "
        f"{count} unique withheld TRAIN games\n"
        "Equal game weighting; numerical repeats are not additional games; no player updates",
        fontsize=11,
    )
    figure.savefig(output, dpi=150)
    plt.close(figure)
    return [csv_path, output]
