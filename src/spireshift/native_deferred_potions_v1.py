"""Reproduce a separate acknowledgement adapter without changing game/host inputs."""

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

PROJECT = Path("mod/SpireShift.HeadlessDeferredPotions")
AREA = "artifacts/native-deferred-potions/v2"


def sources(root: Path) -> dict[str, str]:
    paths = [
        *sorted((root / PROJECT).glob("*.*")),
        *(root / "mod/SpireShift.HeadlessPotionQueue").glob("*.cs"),
        root / "mod/SpireShift.HeadlessActionLifecycle/StartupHook.cs",
        root / "mod/SpireShift.HeadlessMerchantOverlayV2/MerchantOverlay.cs",
    ]
    return {str(p.relative_to(root)): _sha_file(p) for p in paths}


def build(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    out = root / AREA
    report = out / "adapter.json"
    if report.exists():
        return receipt(root, ctx)
    out.mkdir(parents=True, exist_ok=True)
    before = frozen(root, ctx)
    compiler = identified(root / "artifacts/native-entry-text-repair/native-build-v56/report.json")[
        "build"
    ]["toolchain"]
    pinned = sources(root)
    with patch.multiple(native_lifecycle_worker, PROJECT=PROJECT, ASSEMBLY=f"{PROJECT.name}.dll"):
        adapter = native_lifecycle_worker.build_adapter(
            root, Path(ctx["native"]["candidate"]), out / "adapter-build", compiler
        )
    check_sources(root, pinned)
    if frozen(root, ctx) != before:
        raise ValueError("The frozen game, host or original full Adam changed during adapter build")
    return write(
        report,
        {
            "status": "deferred_potion_adapter_reproduced",
            "builds": 2,
            "adapter": adapter,
            "previous_adapter": ctx["lifecycle_adapter"],
            "sources": pinned,
            "frozen_checks": before,
        },
    )


def receipt(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    result = identified(root / AREA / "adapter.json")
    check_sources(root, result["sources"])
    if (
        result["status"] != "deferred_potion_adapter_reproduced"
        or result["builds"] != 2
        or result["sources"] != sources(root)
        or result["previous_adapter"] != ctx["lifecycle_adapter"]
        or _sha_file(Path(result["adapter"]["path"])) != result["adapter"]["sha256"]
    ):
        raise ValueError("Require the exact separately reproduced deferred-potion adapter")
    return result


def with_adapter(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    return {**ctx, "lifecycle_adapter": receipt(root, ctx)["adapter"]}
