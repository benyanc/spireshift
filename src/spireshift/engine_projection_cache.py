"""One verified local JS projection per frozen input identity, with no Git cloning.

Only immutable support code and the existing SDK link are shared. Sessions,
ledgers, game processes and profiles remain owned by individual workers.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json

POLICY = "immutable_shared_local_projection_v2"
ENTRY = "src/managed-player-environment.mjs"


def _files(directory: Path) -> dict[str, str]:
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Projection source code cannot contain symlinks")
        if path.is_file():
            result[str(path.relative_to(directory))] = _sha_file(path)
    return result


def _git(directory: Path, args: list[str], phase: str) -> str:
    command = ["git", "-c", "protocol.allow=never", *args]
    try:
        done = subprocess.run(
            command,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_NO_LAZY_FETCH": "1",
                # A staged cache is nested inside SpireShift's own repository.
                # Never let git-apply discover that unrelated working tree and skip
                # the hook because its source paths lie outside the current prefix.
                "GIT_CEILING_DIRECTORIES": str(directory.parent),
            },
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ValueError(
            f"Projection setup {phase}: local command {args!r} failed: {error}"
        ) from error
    return done.stdout.strip()


def verify_projection_cache(
    cache: Path, pin: dict[str, Any], source_files: dict[str, str] | None = None
) -> dict[str, Any]:
    """Verify exact membership/content, including unexpected files and the SDK link."""
    marker = cache / "identity.json"
    if not marker.is_file() or marker.is_symlink() or (cache / "active.json").exists():
        raise ValueError("Interrupted projection cache; preserve it for explicit inspection")
    doc = json.loads(marker.read_text())
    if (
        doc.get("report_id")
        != manifest_identifier({k: v for k, v in doc.items() if k != "report_id"})
        or doc.get("policy") != POLICY
        or doc.get("projection") != pin
        or (source_files is not None and doc.get("source_files") != source_files)
        or {p.name for p in cache.iterdir()} != {"identity.json", "player-projection"}
    ):
        raise ValueError("Projection cache identity/membership changed")
    staged = cache / "player-projection"
    link = staged / "node_modules"
    if (
        cache.is_symlink()
        or staged.is_symlink()
        or (staged / "src").is_symlink()
        or not link.is_symlink()
        or link.resolve() != Path(pin["node_modules"]).resolve()
        or {p.name for p in staged.iterdir()} != {"src", "package.json", "node_modules"}
        or {f"src/{k}": v for k, v in _files(staged / "src").items()}
        | {"package.json": _sha_file(staged / "package.json")}
        != doc["files"]
        or doc["files"].get(ENTRY) != pin["patched_source_sha256"]
    ):
        raise ValueError("Shared immutable projection bytes or SDK link changed")
    return {"directory": str(cache), "identity_sha256": _sha_file(marker), "policy": POLICY}


def prepare_projection_cache(root: Path, headless: Path, pin: dict[str, Any]) -> dict[str, Any]:
    """Bounded exclusive preparation; a warm cache requires no subprocess or clone."""
    if (
        _sha_file(headless / ENTRY) != pin["source_sha256"]
        or _sha_file(Path(pin["patch"])) != pin["patch_sha256"]
    ):
        raise ValueError("Pinned local projection source/patch changed")
    source_files = {f"src/{k}": v for k, v in _files(headless / "src").items()}
    source_files["package.json"] = _sha_file(headless / "package.json")
    identifier = manifest_identifier({"policy": POLICY, "projection": pin, "files": source_files})
    cache = _private_path(root, f"artifacts/engine-runtime-code/projection-{identifier[7:]}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    lock = cache.with_suffix(".lock")
    with lock.open("a+b") as handle:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Projection preparation lock cap; no worker launched"
                    ) from None
                time.sleep(0.01)
        try:
            if cache.exists():
                return verify_projection_cache(cache, pin, source_files)
            cache.mkdir()
            atomic_json(cache / "active.json", {"owner_process": os.getpid(), "policy": POLICY})
            try:
                if (
                    _git(headless, ["rev-parse", "HEAD"], "source_revision")
                    != pin["source_revision"]
                ):
                    raise ValueError("Projection source revision changed")
                if _git(headless, ["status", "--porcelain"], "source_status"):
                    raise ValueError("Projection source checkout is dirty")
                staged = cache / "player-projection"
                staged.mkdir()
                shutil.copytree(headless / "src", staged / "src", symlinks=False)
                shutil.copyfile(headless / "package.json", staged / "package.json")
                # --no-index applies this already pinned local hook without a checkout,
                # object fetch, remote connection or mutation of the source repository.
                for check in (True, False):
                    _git(
                        staged,
                        [
                            "apply",
                            "--no-index",
                            "--whitespace=error-all",
                            *(["--check"] if check else []),
                            pin["patch"],
                        ],
                        "patch_check" if check else "patch_apply",
                    )
                files = {f"src/{k}": v for k, v in _files(staged / "src").items()}
                files["package.json"] = _sha_file(staged / "package.json")
                expected = {**source_files, ENTRY: pin["patched_source_sha256"]}
                if files != expected:
                    raise ValueError("Projection patch changed unexpected files or bytes")
                (staged / "node_modules").symlink_to(
                    Path(pin["node_modules"]), target_is_directory=True
                )
                doc = {
                    "schema_version": "native-shared-projection-v1",
                    "policy": POLICY,
                    "projection": pin,
                    "source_files": source_files,
                    "files": files,
                    "game_apps_created": 0,
                    "git_clones": 0,
                }
                atomic_json(cache / "identity.json", {**doc, "report_id": manifest_identifier(doc)})
                (cache / "active.json").unlink()
                verified = verify_projection_cache(cache, pin, source_files)
                for name in files:
                    (staged / name).chmod(0o444)
                (cache / "identity.json").chmod(0o444)
                for folder in sorted((staged / "src").rglob("*"), reverse=True):
                    if folder.is_dir():
                        folder.chmod(0o555)
                (staged / "src").chmod(0o555)
                staged.chmod(0o555)
                cache.chmod(0o555)
                return verified
            except BaseException as error:
                atomic_json(cache / "failure.json", {"error": str(error), "policy": POLICY})
                raise
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
