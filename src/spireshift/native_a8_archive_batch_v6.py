"""Recover a completed A8 replay and qualify the remaining clean cases."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_batch_v2 as runner
from spireshift import native_a8_archive_batch_v4 as predecessors
from spireshift import native_a8_archive_batch_v5 as previous
from spireshift import native_a8_archive_transitions_v6 as transitions
from spireshift import native_a8_replay_probe as replay
from spireshift.engine_learning import identified
from spireshift.native_a8_archive_delivery_audit_v6 import check_private_run
from spireshift.native_a8_mix_session import Study, admit
from spireshift.native_compatibility_contract import local, verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-qualification-v6.json"
SCHEMA = "native-a8-archive-batch-v6"
REQUIRED = previous.REQUIRED | {
    "src/spireshift/native_a8_archive_batch_v6.py",
    "src/spireshift/native_a8_archive_delivery_audit_v6.py",
    "src/spireshift/native_a8_archive_transitions_v6.py",
    "scripts/engine-ordered-plan-v1.mjs",
    "scripts/qualify-a8-archive-batch-v6.sh",
}


def historical_cases(root: Path, cfg: dict[str, Any]) -> dict[str, str]:
    result_path = verified(root, cfg["parent_result"])
    result = identified(result_path)
    parent = json.loads((result_path.parent / "config-at-launch.json").read_text())
    store = ChunkJournal(root, parent)
    replay.equal(
        "parent archive batch",
        (result_path.parent, result["config_id"]),
        (store.workspace, store.config_id),
    )
    for key in (
        "environment_id",
        "objective",
        "game_limits",
        "development_seeds",
        "final_test_seeds",
        "boss_map_adapter_sha256",
    ):
        replay.equal(f"preserved {key}", parent[key], cfg[key])
    replay.equal("parent archive outcomes", "stopped_preserving_evidence", result["status"])
    check_sources(root, parent["replay_implementation"])
    originals = {case["run_id"]: case for case in parent["cases"]}
    replay.equal(
        "same planned archive worlds", originals.keys(), {c["run_id"] for c in cfg["cases"]}
    )
    recovered = cfg["recovered_case"]
    check_sources(root, cfg["recovered_native_files"])
    statuses = {}
    for case in cfg["cases"]:
        key = case["run_id"]
        original = originals[key]
        status = result["worlds"][key]["status"]
        replay.equal(
            "preserved archive source",
            (original["seed"], original["source"]),
            (case["seed"], case["source"]),
        )
        if key == recovered:
            path = verified(root, case["saved"])
            relative = str(path.relative_to(root))
            report = identified(path)
            if (
                status != "failed"
                or store.path(key) not in path.parents
                or (store.path(key) / "done.json").exists()
                or cfg["recovered_native_files"].get(relative) != case["saved"]["sha256"]
                or report["status"] != "native_archive_victory_verified"
                or report["clean_shutdown"] is not True
                or report["stop"] is not None
            ):
                raise ValueError("Require the exact unsealed terminal replay for saved recovery")
        elif case.get("saved"):
            replay.equal(
                "historical verified winner",
                (batch.WIN, original["saved"]),
                (status, case["saved"]),
            )
        else:
            ref = cfg["clean_stops"][key]
            if status == "diverged":
                replay.equal(
                    "v5 clean stop",
                    (
                        str(store.workspace.relative_to(root)),
                        key,
                        result["seals"][key],
                        result["worlds"][key]["replay_report_id"],
                    ),
                    (ref["workspace"], ref["chunk"], ref["seal_id"], ref["native_report_id"]),
                )
            elif status == "unattempted":
                replay.equal("earlier clean predecessor", parent["clean_stops"][key], ref)
                if store.path(key).exists():
                    raise ValueError("An unattempted archive case has a v5 attempt")
            else:
                raise ValueError(
                    "Preserve uncertain or unsealed cases without another native attempt"
                )
            statuses[key] = status
    return statuses


@contextmanager
def continuation(
    base: Study,
    cfg: dict[str, Any],
    priors: dict[str, predecessors.Predecessor],
    statuses: dict[str, str],
) -> Iterator[None]:
    execution = base.root / batch.AREA / "execution"
    native = previous.adapter_study(base, cfg)

    class ContinuationJournal(ChunkJournal):
        def begin(self, key: str, request: dict[str, Any]) -> Path:
            run = request.get("run_id", "")
            if self.workspace == execution and key.startswith("seed-") and run in priors:
                if not self.path(f"v4-{key}").is_dir():
                    raise ValueError("The archive seed has no preserved v4 attempt")
                if self.path(f"v5-{key}").is_dir() != (statuses[run] == "diverged"):
                    raise ValueError("The v5 archive attempt does not match the saved result")
                return super().begin(
                    f"v6-{key}", {**request, "preceding_native_report": priors[run].report_id}
                )
            return super().begin(key, request)

    with (
        predecessors.continuation(base.root, priors),
        patch.multiple(
            batch, ChunkJournal=ContinuationJournal, check_private_run=check_private_run
        ),
        patch.object(replay, "admit", lambda _: native),
    ):
        yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    try:
        recipe = local(root, RECIPE)
        with patch.multiple(runner, SCHEMA=SCHEMA, MATCHER=transitions.MATCHER, REQUIRED=REQUIRED):
            cfg = runner.load(root, recipe)
        statuses = historical_cases(root, cfg)
        screened = {case["run_id"]: transitions.screen(root, case) for case in cfg["cases"]}
        with transitions.installed():
            priors, preflight = predecessors.preflight(root, cfg, screened)
            if args.run:
                with continuation(admit(root), cfg, priors, statuses):
                    result = batch.execute(root, recipe, cfg, screened)
            else:
                result = {
                    "status": "archive_qualification_ready",
                    "preceding_choices": preflight,
                    "optimizer_updates": 0,
                    "training_admission_granted": False,
                }
        check_sources(root, cfg["replay_implementation"])
    except (*batch.FAILURES, subprocess.SubprocessError) as exc:
        result = {
            "status": "stopped_preserving_evidence",
            "error": str(exc),
            "optimizer_updates": 0,
            "training_admission_granted": False,
        }
    print(json.dumps(result))
    return 2 if result["status"] == "stopped_preserving_evidence" else 0


if __name__ == "__main__":
    raise SystemExit(main())
