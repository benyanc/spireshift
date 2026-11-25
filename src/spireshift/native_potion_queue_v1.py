"""Build and load a separate queue-eligibility adapter; the game and host stay fixed."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_lifecycle_worker
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win4_game import write

PROJECT = Path("mod/SpireShift.HeadlessPotionQueue")
AREA = "artifacts/native-potion-queue/v1"


def build(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    out = root / AREA
    report = out / "adapter.json"
    if report.exists():
        result = identified(report)
        check_sources(root, result["sources"])
        if _sha_file(Path(result["adapter"]["path"])) != result["adapter"]["sha256"]:
            raise ValueError("The built potion queue adapter changed")
        return result
    out.mkdir(parents=True, exist_ok=True)
    before = frozen(root, ctx)
    compiler = identified(root / "artifacts/native-entry-text-repair/native-build-v56/report.json")[
        "build"
    ]["toolchain"]
    paths = [
        *sorted((root / PROJECT).glob("*.*")),
        root / "mod/SpireShift.HeadlessActionLifecycle/StartupHook.cs",
        root / "mod/SpireShift.HeadlessMerchantOverlayV2/MerchantOverlay.cs",
    ]
    sources = {str(p.relative_to(root)): _sha_file(p) for p in paths}
    with patch.multiple(native_lifecycle_worker, PROJECT=PROJECT, ASSEMBLY=f"{PROJECT.name}.dll"):
        adapter = native_lifecycle_worker.build_adapter(
            root, Path(ctx["native"]["candidate"]), out / "adapter-build", compiler
        )
    check_sources(root, sources)
    if frozen(root, ctx) != before:
        raise ValueError("Frozen game or checkpoints changed during support-adapter build")
    return write(
        report,
        {
            "status": "potion_queue_adapter_reproduced",
            "builds": 2,
            "adapter": adapter,
            "original_lifecycle_adapter": ctx["lifecycle_adapter"],
            "sources": sources,
            "frozen_checks": before,
        },
    )


def with_adapter(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    result = identified(root / AREA / "adapter.json")
    check_sources(root, result["sources"])
    adapter = result["adapter"]
    if (
        result["status"] != "potion_queue_adapter_reproduced"
        or result["builds"] != 2
        or result["original_lifecycle_adapter"] != ctx["lifecycle_adapter"]
        or _sha_file(Path(adapter["path"])) != adapter["sha256"]
    ):
        raise ValueError("Require the exact reproducible queue adapter on the qualified lineage")
    return {**ctx, "lifecycle_adapter": adapter}
