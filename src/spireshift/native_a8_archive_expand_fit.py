"""Compare a world-balanced expanded demonstration fit on copies."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.native_a8_archive_act1_game import CLEAR
from spireshift.native_a8_archive_fit_inputs import (
    UPDATES,
    ArchiveFit,
    archive_fit,
    dataset,
    encode_answer,
)
from spireshift.native_a8_archive_fit_session import (
    ERRORS,
    check_inputs,
    fit_copy,
    fit_request,
    journal,
)
from spireshift.native_a8_bank_fit import Worlds, metrics
from spireshift.native_a8_own_training import State, restored
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-expanded-archive-fit-v1.json"
SCHEMA = "native-a8-expanded-archive-fit-v1"
WORKSPACE = "artifacts/native-a8-archive-fitting/expanded-fit-v1"
SOURCE_CASES = (
    {"train": "c2d89ae06f0cb160", "holdout": "f57f56dc8aaaa022"},
    {"train": "e65b66a983586853", "holdout": "37b61b4895014be7"},
)
SHORT_SECONDS = 250


def sources(study: ArchiveFit, cfg: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    root = study.base.root
    partitions: dict[str, dict[str, dict[str, Any]]] = {"train": {}, "holdout": {}}
    seeds = {case["seed"] for case in study.bank["worlds"].values()}
    seeds.update(study.cfg["development"] + study.cfg["final_test"])
    for ref, cases in zip(cfg["act1_results"], SOURCE_CASES, strict=True):
        path = verified(root, ref)
        result = identified(path)
        source_store = ChunkJournal(
            root, json.loads((path.parent / "config-at-launch.json").read_text())
        )
        if (
            source_store.workspace != path.parent
            or result["config_id"] != source_store.config_id
            or result["stop"] is not None
            or result["frozen_checks"] != study.frozen_checks
        ):
            raise ValueError("Require the exact saved Act 1 qualification")
        for partition, key in cases.items():
            directory = source_store.path(key)
            request = json.loads((directory / "active.json").read_text())["request"]
            case = request.get("case", request)
            row = result["cases"][key]
            seal = source_store.completed(key, request)
            episode = identified(directory / "report.json")
            entry = episode["native_act2_entry"]
            labels = row["labels"]
            if (
                seal is None
                or seal["report_id"] != result["seals"][key]
                or seal["result"] != row
                or row["partition"] != partition
                or case["partition"] != partition
                or episode["status"] != CLEAR
                or row["status"] != CLEAR
                or episode["report_id"] != row.get("native_report_id", row.get("report_id"))
                or episode["seed"] != row["seed"]
                or case["seed"] != row["seed"]
                or entry["operation"] != "proceed"
                or entry["act"] != 2
                or entry["hp"] <= 0
                or episode["stop"] is not None
                or row["seed"] in seeds
                or not labels
                or seal["sources"].get(labels["path"]) != labels["sha256"]
            ):
                raise ValueError("A fitting or holdout source lacks an exact native Act 2 entry")
            seeds.add(row["seed"])
            partitions[partition][row["seed"]] = {
                "labels": labels,
                "seal_id": seal["report_id"],
                "deliveries": row["verified_deliveries"],
                "act1_boss": row["act1_boss"],
            }
    return partitions


def admit(
    root: Path,
) -> tuple[ArchiveFit, dict[str, Any], dict[str, dict[str, dict[str, Any]]], dict[int, State]]:
    study = archive_fit(root)
    cfg = json.loads((root / RECIPE).read_text())
    reference = journal(study, False)
    baseline = identified(verified(root, cfg["baseline_result"]))
    assessment = identified(verified(root, cfg["on_policy_assessment"]))
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["workspace"] != WORKSPACE
        or cfg["objective"] != study.cfg["objective"]
        or cfg["environment_id"] != study.base.ctx["environment_id"]
        or cfg["updates_per_copy"] != UPDATES
        or baseline["config_id"] != reference.config_id
        or baseline["status"] != "a8_archive_fit_development_complete"
        or assessment["games_verified"] != 80
        or assessment["frozen_checks"] != study.frozen_checks
    ):
        raise ValueError("Require the exact frozen copies and completed comparisons")
    check_sources(root, cfg["implementation"])
    parents = {}
    for p in PLAYERS:
        key = f"fit-p{p}"
        seal = reference.completed(key, fit_request(study, p, UPDATES))
        if seal is None or baseline["seals"][key] != seal["report_id"]:
            raise ValueError("Require the exact archive-fitted reference")
        parents[p] = restored(reference, key, seal)
    return study, cfg, sources(study, cfg), parents


def new_worlds(study: ArchiveFit, entries: dict[str, dict[str, Any]], deadline: float) -> Worlds:
    model = study.base.originals[2][0]
    root = study.base.root
    result: Worlds = {}
    for seed, ref in entries.items():
        rows = []
        for raw in records(verified(root, ref["labels"])):
            if time.monotonic() >= deadline:
                raise TimeoutError("The saved archive fit reached its deadline")
            if raw["act"] != 1:
                raise ValueError("The additional sources are scoped to Act 1")
            rows.append(encode_answer(raw, model, study.base.ctx["score"]))
        if sum(len(row.factors) for row in rows) != ref["deliveries"]:
            raise ValueError("The source label count differs from the verified native transport")
        result[seed] = tuple(rows)
    return result


def request(study: ArchiveFit, partitions: dict[str, Any], player: int) -> dict[str, Any]:
    return {**fit_request(study, player, UPDATES), "added_training_worlds": partitions["train"]}


def prepare(root: Path, deadline: float) -> dict[str, Any]:
    study, cfg, partitions, parents = admit(root)
    store = ChunkJournal(root, cfg)
    training = {**dataset(study, deadline), **new_worlds(study, partitions["train"], deadline)}
    holdout = {
        seed: tuple(row for row in rows if any(len(f.rows) > 1 for f in row.factors))
        for seed, rows in new_worlds(study, partitions["holdout"], deadline).items()
    }
    if set(training) & set(holdout) or len(training) != 5 or len(holdout) != 2:
        raise ValueError("Require five independent fitting worlds and two separate holdouts")
    path = store.workspace / "report.json"
    with store.lock():
        result: dict[str, Any] = identified(path) if path.is_file() else {}
        if result and (
            result["config_id"] != store.config_id or result["partitions"] != partitions
        ):
            raise ValueError("The saved expanded fit changed")
        scores, seals = {}, {}
        for p in PLAYERS:
            key = f"fit-p{p}"
            spec = request(study, partitions, p)
            seal = store.completed(key, spec)
            if seal is None:
                if result:
                    raise ValueError("The saved fit seal is missing")
                print(f"Fitting copy {p} on five declared worlds", flush=True)
                row = fit_copy(study, p, store.begin(key, spec), training, UPDATES, deadline)
                seal = store.commit(key, spec, row)
            model, _, state_id = restored(store, key, seal)
            seals[key] = seal["report_id"]
            scores[str(p)] = {
                "expanded_state_id": state_id,
                "reference_state_id": parents[p][2],
                "reference": metrics(parents[p][0], holdout),
                "expanded": metrics(model, holdout),
            }
        check_inputs(study)
        check_sources(root, cfg["implementation"])
        if frozen(root, study.base.ctx) != study.frozen_checks:
            raise ValueError("Frozen model or game inputs changed")
        if result:
            if result["seals"] != seals or result["held_out"] != scores:
                raise ValueError("The saved held-out fit scores do not reconstruct")
            return result
        return write(
            path,
            {
                "schema_version": SCHEMA,
                "status": "expanded_archive_fits_sealed",
                "config_id": store.config_id,
                "partitions": partitions,
                "held_out": scores,
                "seals": seals,
                "optimizer_updates_per_copy": UPDATES,
                "original_optimizer_updates": 0,
                "game_launches": 0,
                "frozen_checks": study.frozen_checks,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the frozen numerical settings")
        result = prepare(Path.cwd(), time.monotonic() + SHORT_SECONDS)
        print(
            json.dumps(
                {
                    "report_id": result["report_id"],
                    "status": result["status"],
                    "held_out": {
                        p: {arm: row[arm]["all"] for arm in ("reference", "expanded")}
                        for p, row in result["held_out"].items()
                    },
                }
            )
        )
        return 0
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
