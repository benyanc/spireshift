"""An isolated confirmation adapter for the original headless binary."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_boss_worker
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_worker import BossWorker
from spireshift.native_a8_own_training_inputs import admitted_context, declaration
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win4_game import write

SCRIPT = "engine-combat-feedback-worker-v1.mjs"
PROJECTION = "native_a8_abandon_confirmation_and_verified_ending_v1"
AREA = "artifacts/native-a8-combat-feedback"
ADAPTER = f"{AREA}/adapter-v2"
PROJECT = Path("mod/SpireShift.HeadlessConfirmation")
ASSEMBLY = "SpireShift.HeadlessConfirmation.dll"


def build_adapter(root: Path) -> dict[str, Any]:
    ctx, _ = admitted_context(root, declaration(root))
    before = frozen(root, ctx)
    out = root / ADAPTER
    out.mkdir(parents=True, exist_ok=False)
    sdk = identified(root / "artifacts/native-entry-text-repair/native-build-v56/report.json")[
        "build"
    ]["toolchain"]
    if (
        subprocess.check_output(["dotnet", "--version"], text=True, timeout=10).strip()
        != sdk["sdk_version"]
    ):
        raise ValueError("Pinned compiler version changed")
    listing = subprocess.check_output(["dotnet", "--list-sdks"], text=True, timeout=10)
    directory = next(
        line.split(" [", 1)[1].rstrip("]")
        for line in listing.splitlines()
        if line.startswith(sdk["sdk_version"] + " [")
    )
    compiler = Path(directory) / sdk["sdk_version"] / "Roslyn/bincore/csc.dll"
    if _sha_file(compiler) != sdk["csc_sha256"]:
        raise ValueError("Pinned compiler bytes changed")

    paths = [*sorted((root / PROJECT).glob("*.*")), Path(__file__).resolve()]
    sources = {p.relative_to(root).as_posix(): _sha_file(p) for p in paths}
    builds = []
    for name in ("build", "independent-build"):
        with (out / f"{name}.log").open("wb") as log:
            subprocess.run(
                [
                    "dotnet",
                    "build",
                    str(root / PROJECT / "SpireShift.HeadlessConfirmation.csproj"),
                    "-c",
                    "Release",
                    "-v:q",
                    "--disable-build-servers",
                    "--artifacts-path",
                    str(out / name),
                    f"-p:CandidateDirectory={ctx['native']['candidate']}",
                ],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=40,
                check=True,
            )
        (assembly,) = (out / name / "bin").rglob(ASSEMBLY)
        builds.append(
            {"path": assembly.relative_to(root).as_posix(), "sha256": _sha_file(assembly)}
        )
    check_sources(root, sources)
    if builds[0]["sha256"] != builds[1]["sha256"] or frozen(root, ctx) != before:
        raise ValueError("Confirmation adapter was not reproducible on the frozen host")
    return write(
        out / "report.json",
        {
            "status": "frozen_host_confirmation_adapter_built",
            "environment_id": ctx["environment_id"],
            "builds": builds,
            "sources": sources,
            "frozen_checks": before,
        },
    )


def load_adapter(root: Path, ctx: dict[str, Any], reference: dict[str, Any]) -> dict[str, str]:
    report = identified(verified(root, reference))
    if (
        report["status"] != "frozen_host_confirmation_adapter_built"
        or report["environment_id"] != ctx["environment_id"]
        or not all(report["frozen_checks"].values())
        or len(report["builds"]) != 2
        or report["builds"][0]["sha256"] != report["builds"][1]["sha256"]
    ):
        raise ValueError("Require the independently built adapter for this frozen host")
    check_sources(root, report["sources"])
    for ref in report["builds"]:
        verified(root, ref)
    ref = report["builds"][0]
    return {"path": str(root / ref["path"]), "sha256": ref["sha256"]}


class FeedbackWorker(BossWorker):
    def __init__(self, ctx: dict[str, Any], target: Path, *, control: bool = False) -> None:
        self.adapter = ctx["confirmation_adapter"]
        self.control = control
        qualification = ctx["qualification"]
        # The isolated constructor is pinned by earlier studies. Select the new
        # entry point only while constructing this separately versioned worker.
        with patch.multiple(native_a8_boss_worker, SCRIPT=SCRIPT, PROJECTION=PROJECTION):
            super().__init__(
                qualification,
                ctx["native"],
                target,
                Path(ctx["node"]),
                worker_helpers(qualification.root, SCRIPT),
                ctx["execution_id"],
            )

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {
                **values["spec"],
                "confirmation_adapter": self.adapter,
                "confirmation_control": self.control,
            }
        return super().request(command, timeout=timeout, **values)


def worker(ctx: dict[str, Any], target: Path) -> FeedbackWorker:
    return FeedbackWorker(ctx, target)


if __name__ == "__main__":
    print(json.dumps(build_adapter(Path.cwd())))
