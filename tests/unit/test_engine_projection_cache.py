"""Local support-code sharing and corruption/concurrency controls; no game process."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

import spireshift.engine_projection_cache as cache
from spireshift.engine_qualification import _sha_file


@pytest.fixture
def inputs(tmp_path: Path) -> Iterator[tuple[Path, Path, dict[str, Any]]]:
    source = tmp_path / "artifacts/source"
    # Real caches live inside the SpireShift checkout. Reproduce that outer
    # repository so git-apply must not silently skip nested source paths.
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, timeout=5)
    (source / "src").mkdir(parents=True)
    (source / cache.ENTRY).write_text("export const marker = 'before';\n")
    (source / "src/json-line-process.mjs").write_text("export const transport = 'synthetic';\n")
    (source / "package.json").write_text('{"type":"module"}')
    sdk = tmp_path / "artifacts/sdk/node_modules"
    sdk.mkdir(parents=True)
    for args in (
        ["init", "--quiet"],
        ["add", "."],
        [
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "synthetic fixture",
        ],
    ):
        subprocess.run(["git", *args], cwd=source, capture_output=True, check=True, timeout=5)
    patch = tmp_path / "hook.patch"
    patch.write_text(
        "diff --git a/src/managed-player-environment.mjs b/src/managed-player-environment.mjs\n"
        "--- a/src/managed-player-environment.mjs\n+++ b/src/managed-player-environment.mjs\n"
        "@@ -1 +1 @@\n-export const marker = 'before';\n+export const marker = 'after';\n"
    )
    import hashlib

    pin = {
        "source_revision": cache._git(source, ["rev-parse", "HEAD"], "fixture"),
        "source_sha256": _sha_file(source / cache.ENTRY),
        "patch": str(patch),
        "patch_sha256": _sha_file(patch),
        "node_modules": str(sdk),
        "patched_source_sha256": hashlib.sha256(b"export const marker = 'after';\n").hexdigest(),
        "sdk_inventory_id": "synthetic-unused-sdk",
    }
    yield tmp_path, source, pin
    # The cache deliberately uses read-only directories. Restore fixture-only
    # permissions so pytest can remove its temporary sandbox, never the real cache.
    for path in [tmp_path, *tmp_path.rglob("*")]:
        if not path.is_symlink() and path.is_dir():
            path.chmod(0o700)


def test_cold_parallel_preparation_and_subprocess_free_reuse(
    inputs: tuple[Path, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, pin = inputs
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(cache.prepare_projection_cache, root, source, pin) for _ in range(2)]
        first, second = [j.result() for j in jobs]
    assert first == second
    doc = json.loads((Path(first["directory"]) / "identity.json").read_text())
    assert doc["git_clones"] == doc["game_apps_created"] == 0
    assert not (Path(first["directory"]) / "player-projection/.git").exists()
    assert (source / cache.ENTRY).read_text() == "export const marker = 'before';\n"

    def reject_git(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("A warm worker tried to run Git")

    monkeypatch.setattr(cache, "_git", reject_git)
    assert cache.prepare_projection_cache(root, source, pin) == first


@pytest.mark.parametrize("fault", ["bytes", "extra_file", "interrupted", "sdk_link"])
def test_changed_cache_is_preserved_and_never_rebuilt(
    inputs: tuple[Path, Path, dict[str, Any]],
    fault: str,
) -> None:
    root, source, pin = inputs
    ref = cache.prepare_projection_cache(root, source, pin)
    folder = Path(ref["directory"])
    staged = folder / "player-projection"
    if fault == "bytes":
        file = staged / cache.ENTRY
        file.chmod(0o600)
        file.write_text("changed")
    elif fault == "extra_file":
        (staged / "src").chmod(0o700)
        (staged / "src/unknown.mjs").write_text("changed")
    elif fault == "interrupted":
        folder.chmod(0o700)
        (folder / "active.json").write_text("interrupted")
    else:
        staged.chmod(0o700)
        (staged / "node_modules").unlink()
        (staged / "node_modules").symlink_to(source)
    with pytest.raises(ValueError):
        cache.prepare_projection_cache(root, source, pin)
    assert folder.exists()
    assert len(list(folder.parent.glob("projection-*"))) == 2  # original directory plus lock


def test_patch_cannot_change_unadvertised_source_bytes(
    inputs: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, source, pin = inputs
    with pytest.raises(ValueError, match="unexpected files or bytes"):
        cache.prepare_projection_cache(root, source, {**pin, "patched_source_sha256": "wrong"})
    failures = list((root / "artifacts/engine-runtime-code").glob("*/failure.json"))
    assert len(failures) == 1
    assert (failures[0].parent / "active.json").is_file()


def test_node_loads_the_verified_cache_without_git(
    inputs: tuple[Path, Path, dict[str, Any]],
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node not installed on this test host")
    root, source, pin = inputs
    ref = cache.prepare_projection_cache(root, source, pin)
    helper = Path("scripts/engine-player-projection-v3.mjs").resolve().as_uri()
    script = (
        "const {preparePlayerProjection} = await import(process.argv[1]); "
        "const p=await preparePlayerProjection(JSON.parse(process.argv[2])); "
        "console.log(JSON.stringify({marker:p.module.marker,transport:p.transport.transport}));"
    )
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            script,
            helper,
            json.dumps({"shared_projection": ref, "projection": pin}),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert json.loads(result.stdout) == {"marker": "after", "transport": "synthetic"}
