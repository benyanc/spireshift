from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Diagnostic:
    name: str
    status: str
    detail: str


def collect_diagnostics() -> list[Diagnostic]:
    diagnostics = [
        Diagnostic("platform", "ok", platform.platform()),
        _command_diagnostic("git", ["git", "--version"]),
        _command_diagnostic("github", ["gh", "auth", "status"]),
        _command_diagnostic("uv", ["uv", "--version"]),
        _command_diagnostic("dotnet", ["dotnet", "--version"]),
    ]
    game_path = find_game_path()
    diagnostics.append(
        Diagnostic(
            "sts2",
            "ok" if game_path else "missing",
            str(game_path) if game_path else "Set SPIRESHIFT_GAME_DIR or install via Steam",
        )
    )
    return diagnostics


def diagnostics_as_dict() -> list[dict[str, str]]:
    return [asdict(item) for item in collect_diagnostics()]


def find_game_path() -> Path | None:
    configured = os.environ.get("SPIRESHIFT_GAME_DIR")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.home() / "Library/Application Support/Steam/steamapps/common/Slay the Spire 2",
            Path.home() / ".steam/steam/steamapps/common/Slay the Spire 2",
            Path("C:/Program Files (x86)/Steam/steamapps/common/Slay the Spire 2"),
        ]
    )
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _command_diagnostic(name: str, command: list[str]) -> Diagnostic:
    if shutil.which(command[0]) is None:
        return Diagnostic(name, "missing", f"{command[0]} not found")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    output = (completed.stdout or completed.stderr).strip().splitlines()
    detail = output[0] if output else f"exit {completed.returncode}"
    return Diagnostic(name, "ok" if completed.returncode == 0 else "error", detail)
