"""Versioned headless worker and reproducible build of its card cleanup adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_feedback_host import FeedbackWorker

SCRIPT = "engine-action-lifecycle-worker-v1.mjs"
PROJECTION = "native_a8_action_lifecycle_v1"
PROJECT = Path("mod/SpireShift.HeadlessActionLifecycle")
ASSEMBLY = f"{PROJECT.name}.dll"


def build_adapter(
    root: Path, candidate: Path, out: Path, compiler: dict[str, str]
) -> dict[str, str]:
    version = compiler["sdk_version"]
    if subprocess.check_output(["dotnet", "--version"], text=True, timeout=10).strip() != version:
        raise ValueError("Require the frozen adapter compiler")
    sdks = subprocess.check_output(["dotnet", "--list-sdks"], text=True, timeout=10)
    (location,) = (
        line.split(" [", 1)[1].rstrip("]")
        for line in sdks.splitlines()
        if line.startswith(f"{version} [")
    )
    csc = Path(location) / version / "Roslyn/bincore/csc.dll"
    if _sha_file(csc) != compiler["csc_sha256"]:
        raise ValueError("The pinned compiler bytes changed")

    out.mkdir()
    references = []
    for name in ("build", "independent-build"):
        build = out / name
        with (out / f"{name}.log").open("xb") as log:
            process = subprocess.run(
                [
                    "dotnet",
                    "build",
                    str(root / PROJECT / f"{PROJECT.name}.csproj"),
                    "-c",
                    "Release",
                    "-v:q",
                    "--disable-build-servers",
                    "--artifacts-path",
                    str(build),
                    f"-p:CandidateDirectory={candidate}",
                ],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=40,
            )
        if process.returncode:
            raise ValueError(f"Lifecycle adapter build failed. See {out / f'{name}.log'}")
        (library,) = (build / "bin").rglob(ASSEMBLY)
        references.append({"path": str(library), "sha256": _sha_file(library)})
    if references[0]["sha256"] != references[1]["sha256"]:
        raise ValueError("Lifecycle adapter did not reproduce byte for byte")
    return references[0]


class LifecycleWorker(FeedbackWorker):
    def __init__(
        self,
        ctx: dict[str, Any],
        target: Path,
        *,
        fixture: bool = False,
    ) -> None:
        self.lifecycle_adapter = ctx["lifecycle_adapter"]
        self.fixture = fixture
        with patch.multiple(native_a8_feedback_host, SCRIPT=SCRIPT, PROJECTION=PROJECTION):
            super().__init__(ctx, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {
                **values["spec"],
                "lifecycle_adapter": self.lifecycle_adapter,
                "lifecycle_fixture": self.fixture,
            }
        return super().request(command, timeout=timeout, **values)
