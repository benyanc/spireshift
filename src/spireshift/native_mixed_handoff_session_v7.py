"""Import two qualified pairs without games; launch only six unstarted counterparts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_mixed_handoff_session_v1 as session_v1
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_mixed_handoff_inputs_v7 import MODULE, SCHEMA, context, load
from spireshift.native_mixed_handoff_session_v6 import prior_pairs
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
            raise ValueError("Preserve the incomplete saved-pair adoption")
        check_sources(root, result["sources"])
        return result
    prior_pairs(ctx, cfg, area.parent / "historical-assessment-v1", deadline)
    original = verified(root, cfg["qualified_native_controls"])
    source = original.parent
    native = identified(original)
    area.mkdir()
    for row in native["cases"]:
        shutil.copytree(source / row["case"]["key"], area / row["case"]["key"])
    short = identified(verified(root, cfg["qualified_short_result"]))
    for row in short["pairs"]:
        key = row["case"]["key"]
        if identified(source.parent / "pairs" / key / "report.json") != row:
            raise ValueError("The original qualified official seal changed")
        check_sources(root, row["sources"])
        target = area.parent / "pairs" / key
        target.parent.mkdir(exist_ok=True)
        shutil.copytree(source.parent / "pairs" / key / "official", target / "official")
        imported = {name: value for name, value in row.items() if name != "report_id"}
        write(
            target / "report.json",
            {
                **imported,
                "config_id": manifest_identifier(cfg),
                "imported_official_report_id": row["report_id"],
                "sources": evidence(root, target),
            },
        )
        # Reconstruct raw public inputs and actual SDK completion again in the
        # new assessment directory. No fixture is loaded and no action delivered.
        expected = next(item for item in native["cases"] if item["case"]["key"] == key)
        session_v1.saved_pair(ctx, cfg, expected, target, deadline)
    return write(
        seal,
        {
            "schema_version": SCHEMA,
            "status": "native_controls_verified",
            "config_id": manifest_identifier(cfg),
            "cases": native["cases"],
            "stop": None,
            "imported_native_controls": 8,
            "imported_official_pairs": 2,
            "sources": evidence(root, area),
            "optimizer_updates": 0,
        },
    )


def main() -> int:
    with patch.multiple(
        session_v1,
        MODULE=MODULE,
        SCHEMA=SCHEMA,
        load=load,
        context=context,
        native_cases=native_cases,
    ):
        return session_v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
