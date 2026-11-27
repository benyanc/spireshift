import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import spireshift.engine_connector as connector


@pytest.mark.parametrize("mode", ["ordinary", "clone", "clone_unavailable"])
def test_disposable_asset_has_independent_writable_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    source, destination = tmp_path / "source.pck", tmp_path / "disposable.pck"
    with source.open("wb") as stream:
        stream.write(b"original")
        if mode != "ordinary":
            stream.truncate(100_000_000)
    calls = []

    class Clone:
        def __call__(self, src: bytes, dst: bytes, flags: int) -> int:
            calls.append((src, dst, flags))
            if mode == "clone_unavailable":
                return -1
            shutil.copyfile(src, dst)
            return 0

    monkeypatch.setattr("spireshift.engine_connector.sys.platform", "darwin")
    monkeypatch.setattr(
        "spireshift.engine_connector.ctypes.CDLL",
        lambda *a, **k: SimpleNamespace(clonefile=Clone()),
    )
    connector._copy_disposable_game_file(source, destination)
    assert source.stat().st_ino != destination.stat().st_ino
    assert source.stat().st_size == destination.stat().st_size
    assert len(calls) == (0 if mode == "ordinary" else 1)
    with destination.open("r+b") as target_stream:
        target_stream.write(b"changed!")
    with source.open("rb") as source_stream:
        assert source_stream.read(8) == b"original"


def test_clone_cannot_be_a_hard_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, destination = tmp_path / "source", tmp_path / "target"
    with source.open("wb") as stream:
        stream.truncate(100_000_000)

    class BadClone:
        def __call__(self, src: bytes, dst: bytes, flags: int) -> int:
            Path(dst.decode()).hardlink_to(Path(src.decode()))
            return 0

    monkeypatch.setattr("spireshift.engine_connector.sys.platform", "darwin")
    monkeypatch.setattr(
        "spireshift.engine_connector.ctypes.CDLL",
        lambda *a, **k: SimpleNamespace(clonefile=BadClone()),
    )
    with pytest.raises(ValueError, match="independent inode"):
        connector._copy_disposable_game_file(source, destination)
