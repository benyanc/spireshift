"""Local preparation only: freeze fresh seed reservations and pinned comparison inputs.

No games, fitting, downloads or overwrites. The long recipe can be frozen only
once its separate small integration control has completed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_selection_worker import PROTOCOL, SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_context_journal import load_state
from spireshift.native_exploration_admission import SOURCES
from spireshift.native_exploration_plan import ARMS
from spireshift.native_rest_exploration import CONTRACT


def put(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f"Preserve existing frozen file: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        f.write(json.dumps(value, indent=2) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    short = not a.main
    old_path = "configs/native-learning/sts2-v0.111.0-a8-runtime-continuation-v1.json"
    source_path = "artifacts/native-runtime-learning/sts2-v0.111.0-a8-continuation-v1/report.json"
    parent_path = "configs/native-learning/sts2-v0.111.0-a8-input-normalized-v1.json"
    effects_path = (
        "artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/"
        "selection-effects-v4/report.json"
    )
    old = json.loads((root / old_path).read_text())
    source = identified(root / source_path)
    parent = json.loads((root / parent_path).read_text())
    effects = identified(root / effects_path)
    players = []
    for n in (2, 3):
        receipt = (
            Path(source_path).parent / "chunks" / source["ending"]["states"][str(n)] / "done.json"
        )
        state = identified(root / receipt)["result"]
        m, o, state_id = load_state(root / state["state_path"])
        players.append(
            {
                "numerical_seed": n,
                "path": state["state_path"],
                "sha256": _sha_file(root / state["state_path"]),
                "model_id": m.model_id,
                "state_id": state_id,
                "optimizer_steps": o.steps,
                "round": 56,
                "scheduled_training_games": 1792,
            }
        )
    excludes = []
    for path in sorted((root / "manifests/splits").glob("sts2-v0.111.0-native-a8-*.json")):
        if "rest-exploration" in path.name:
            continue
        previous = identified(path, "manifest_id")
        excludes.append({"path": str(path.relative_to(root)), "id": previous["manifest_id"]})
    if not short:
        control = identified(
            root / "artifacts/native-rest-exploration/sts2-v0.111.0-a8-control-v1/report.json"
        )
        cc = json.loads((root / control["recipe_path"]).read_text())
        excludes.append(cc["seed_manifest"])
    rows = []
    for n in (2, 3):
        for part, size in [
            ("control" if short else "train", 2 if short else 128),
            ("control_eval" if short else "holdout", 2 if short else 64),
        ]:
            for i in range(size):
                rows.append(
                    {
                        "id": (1600000 if short else 1610000) + len(rows),
                        "seed": (
                            f"SP1RESH1FTREST{'C' if short else 'M'}{n}"
                            f"{part.replace('_', '').upper()}{i:04d}"
                        ),
                        "partition": part,
                        "numerical_seed": n,
                    }
                )
    body = {
        "schema_version": "native-rest-exploration-seed-manifest-v1",
        "environment_id": parent["environment_manifest"]["id"],
        "scope": "matched_training_seeds_with_separate_final_holdout",
        "seeds": rows,
    }
    seeds = {**body, "manifest_id": manifest_identifier(body)}
    suffix = "control" if short else "comparison"
    seed_path = f"manifests/splits/sts2-v0.111.0-native-a8-rest-exploration-{suffix}-v1.json"
    put(root / seed_path, seeds)
    cfg = {
        "schema_version": "native-rest-exploration-config-v1",
        "stage": "short_bridge_control" if short else "bounded_rest_exploration",
        "arms": ARMS,
        "training_seeds": [2, 3],
        "starting_round": 56,
        "starting_training_games": 1792,
        "rounds": 1 if short else 4,
        "batch_games": 2 if short else 32,
        "chunk_games": 2 if short else 8,
        "holdout_games": 2 if short else 64,
        "checkpoint_selection": "all_current_final_states_no_selection_or_early_stopping",
        "evaluation_uniform_weight": 0.0,
        "invocation_wall_seconds": 240 if short else 7200,
        "session_limits": {
            "wall_seconds": 240 if short else 900,
            "cpu_seconds": 480 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 4000000000,
        },
        "players": players,
        "policy_contract": CONTRACT,
        "selection_protocol": PROTOCOL,
        "workspace": f"artifacts/native-rest-exploration/sts2-v0.111.0-a8-{suffix}-v1",
        "source_config": {"path": old_path, "id": manifest_identifier(old)},
        "source_report": {"path": source_path, "id": source["report_id"]},
        "qualified_parent": {"path": parent_path, "id": manifest_identifier(parent)},
        "selection_effects": {"path": effects_path, "id": effects["report_id"]},
        "seed_manifest": {"path": seed_path, "id": seeds["manifest_id"]},
        "excluded_seed_manifests": excludes,
        "implementation_sha256": {
            name: _sha_file(root / "src/spireshift" / name) for name in SOURCES
        },
        "entry_sha256": _sha_file(root / "scripts/rest-exploration-v1.py"),
        "worker_helpers_sha256": worker_helpers(root, SCRIPT),
        "verifier_sha256": _sha_file(root / "scripts/verify-selection-cursor-v1.mjs"),
    }
    if not short:
        cfg["control_report"] = {
            "path": "artifacts/native-rest-exploration/sts2-v0.111.0-a8-control-v1/report.json",
            "id": control["report_id"],
        }
    put(
        root
        / (
            "configs/native-controls/rest-exploration-control-v1.json"
            if short
            else "configs/native-learning/sts2-v0.111.0-a8-rest-exploration-v1.json"
        ),
        cfg,
    )
    print(
        json.dumps(
            {
                "frozen_config_id": manifest_identifier(cfg),
                "games_launched": 0,
                "optimizer_steps": 0,
                "players": players,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
