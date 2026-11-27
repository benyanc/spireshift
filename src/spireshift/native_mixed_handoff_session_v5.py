"""Qualify the merchant-map repair and finish only unstarted mixed controls."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_mixed_handoff_cases_v1 as cases_v1
from spireshift import native_mixed_handoff_session_v1 as session_v1
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_merchant_overlay_checks_v1 import merchant_map_use, merchant_target
from spireshift.native_mixed_handoff_checks_v2 import rest_menu
from spireshift.native_mixed_handoff_checks_v3 import control_label
from spireshift.native_mixed_handoff_inputs_v5 import MODULE, SCHEMA, context, load
from spireshift.native_mixed_handoff_worker_v2 import MixedWorker
from spireshift.native_selector_lifecycle_checks import enter_next_room as original_travel
from spireshift.native_selector_lifecycle_checks import player
from spireshift.native_selector_paired_session import evidence
from spireshift.native_win4_game import write


def shop(trace: Any, case: dict[str, Any]) -> dict[str, Any]:
    if case["operation"] == "merchant_map_use":
        return merchant_map_use(trace, case)
    return _shop(trace, case)


def enter_next_room(trace: Any) -> None:
    if any(row["definition_id"] == "FOUL_POTION" for row in player(trace.current)["potions"]):
        merchant_target(trace, True)
    original_travel(trace)
    if any(row["role"] == "merchant" for row in trace.current["snapshot"]["referents"]):
        raise ValueError("Actual room travel retained the merchant target")


_shop = cases_v1.shop


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
            raise ValueError("Preserve incomplete merchant overlay controls")
        check_sources(root, result["sources"])
        return result
    area.mkdir()
    imports = {identified(verified(root, ref))["case"]["key"]: ref for ref in cfg["native_imports"]}
    rows, stop = [], None
    for case in cfg["cases"]:
        directory = area / case["key"]
        if case["key"] in imports:
            source = verified(root, imports[case["key"]])
            row = identified(source)
            shutil.copytree(source.parent, directory)
            rows.append(row)
            print(f"Imported native {case['key']}: verified", flush=True)
            continue
        directory.mkdir()
        try:
            worker = MixedWorker(ctx, directory / "preparation")
            try:
                fixture = worker.request("prepare", case=case)
                shutdown = worker.close()
                if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
                    raise ValueError("Merchant overlay preparation did not exit cleanly")
            finally:
                worker.stop()
            save = directory / "shared-fixture.save"
            atomic_json(save, fixture["save"])
            effects = cases_v1.run_case(ctx, case, save, directory, deadline)
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
                        "fixture_source_sha256": fixture["original_save_sha256"],
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
            "imported_native_controls": len(imports),
            "optimizer_updates": 0,
        },
    )


def main() -> int:
    with (
        patch.multiple(
            session_v1,
            MODULE=MODULE,
            SCHEMA=SCHEMA,
            load=load,
            context=context,
            native_cases=native_cases,
        ),
        patch.multiple(
            cases_v1,
            MixedWorker=MixedWorker,
            shop=shop,
            enter_next_room=enter_next_room,
            rest_menu=rest_menu,
            label=control_label,
        ),
    ):
        return session_v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
