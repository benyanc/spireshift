"""Finish native preparations once; pair short and full mixed handoff controls."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_mixed_handoff_cases_v1, native_mixed_handoff_session_v1
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_mixed_handoff_cases_v1 import run_case
from spireshift.native_mixed_handoff_cases_v4 import rest
from spireshift.native_mixed_handoff_checks_v2 import rest_menu
from spireshift.native_mixed_handoff_checks_v3 import control_label
from spireshift.native_mixed_handoff_inputs_v4 import MODULE, SCHEMA, load
from spireshift.native_mixed_handoff_worker_v1 import MixedWorker
from spireshift.native_selector_paired_session import evidence
from spireshift.native_win4_game import write


def native_cases(
    ctx: dict[str, Any], cfg: dict[str, Any], area: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    seal = area / "report.json"
    if seal.exists():
        result = identified(seal)
        if result["status"] != "native_controls_verified" or result[
            "config_id"
        ] != manifest_identifier(cfg):
            raise ValueError("Preserve incomplete native mixed preparations")
        check_sources(root, result["sources"])
        return result
    area.mkdir()
    rows = []
    stop = None
    for ref in cfg["native_imports"]:
        source = verified(root, ref)
        row = identified(source)
        shutil.copytree(source.parent, area / row["case"]["key"])
        rows.append(row)
        print(f"Imported native {row['case']['key']}: verified", flush=True)
    for case in cfg["cases"][2:]:
        directory = area / case["key"]
        directory.mkdir()
        try:
            worker = MixedWorker(ctx, directory / "preparation")
            try:
                result = worker.request("prepare", case=case)
                shutdown = worker.close()
                if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
                    raise ValueError("Mixed preparation shutdown failed")
            finally:
                worker.stop()
            save = directory / "shared-fixture.save"
            atomic_json(save, result["save"])
            effects = run_case(ctx, case, save, directory, deadline)
            rows.append(
                write(
                    directory / "report.json",
                    {
                        "status": "verified",
                        "case": case,
                        "fixture_save": {
                            "path": str(save.relative_to(root)),
                            "sha256": _sha_file(save),
                        },
                        "fixture_source_sha256": result["original_save_sha256"],
                        **effects,
                    },
                )
            )
            print(f"Native {case['key']}: verified", flush=True)
        except (ValueError, KeyError, OSError, TimeoutError, StopIteration) as error:
            stop = {"case": case["key"], "error": f"{type(error).__name__}: {error}"}
            write(directory / "failure.json", stop)
            break
    return write(
        seal,
        {
            "schema_version": SCHEMA,
            "status": "native_controls_verified" if stop is None else "blocked_preserving_evidence",
            "config_id": manifest_identifier(cfg),
            "cases": rows,
            "stop": stop,
            "sources": evidence(root, area),
            "imported_native_controls": 2,
            "optimizer_updates": 0,
        },
    )


def main() -> int:
    with (
        patch.multiple(
            native_mixed_handoff_session_v1,
            MODULE=MODULE,
            SCHEMA=SCHEMA,
            load=load,
            native_cases=native_cases,
        ),
        patch.multiple(
            native_mixed_handoff_cases_v1, rest_menu=rest_menu, label=control_label, rest=rest
        ),
    ):
        return native_mixed_handoff_session_v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
