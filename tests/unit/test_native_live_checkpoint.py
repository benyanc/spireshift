from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_live_checkpoint import compare_prefixes, run
from spireshift.native_live_verification import same
from spireshift.native_official_session import finish_client


def test_open_game_blocks_before_imports_markers_or_any_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spireshift.native_live_checkpoint._running_games", lambda: [123])
    context = {"config": {"workspace": "artifacts/native-live-adapter/not-created"}}
    with pytest.raises(ValueError, match="Close the game"):
        run(tmp_path, context)
    assert not (tmp_path / "artifacts").exists()


def saved(root: Path) -> dict[str, Any]:
    cfg = {"workspace": "artifacts/native-live-adapter/saved"}
    directory = root / cfg["workspace"]
    directory.mkdir(parents=True)
    (root / "implementation.py").write_text("original implementation")
    (directory / "outcome.json").write_text("original evidence")
    body = {
        "config_id": manifest_identifier(cfg),
        "status": "verified_saved_result",
        "sources": {"implementation.py": _sha_file(root / "implementation.py")},
        "evidence": {
            str((directory / "outcome.json").relative_to(root)): _sha_file(
                directory / "outcome.json"
            )
        },
    }
    body["report_id"] = manifest_identifier(body)
    (directory / "report.json").write_text(json.dumps(body))
    return {"config": cfg}


def test_saved_result_is_reused_without_starting_even_a_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = saved(tmp_path)

    def forbidden() -> Any:
        pytest.fail("A complete sealed result must not launch or inspect a game")

    monkeypatch.setattr("spireshift.native_live_checkpoint._running_games", forbidden)
    assert run(tmp_path, context)["status"] == "verified_saved_result"


@pytest.mark.parametrize(
    "name", ["implementation.py", "artifacts/native-live-adapter/saved/outcome.json"]
)
def test_changed_code_or_completed_evidence_cannot_resume(tmp_path: Path, name: str) -> None:
    context = saved(tmp_path)
    (tmp_path / name).write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        run(tmp_path, context)


def test_divergent_states_are_not_realigned_into_fake_paired_evidence(tmp_path: Path) -> None:
    def file(name: str, values: list[int]) -> Path:
        path = tmp_path / name
        with gzip.open(path, "wt") as output:
            for value in values:
                output.write(
                    json.dumps(
                        {
                            "kind": "policy_input",
                            "frame": {
                                "public_input": {"value": value},
                                "actions": [{"key": "same-action"}],
                            },
                        }
                    )
                    + "\n"
                )
        return path

    result = compare_prefixes(file("native.gz", [1, 2, 3]), file("official.gz", [1, 9, 3]))
    assert result["equal_input_prefix"] == 1
    assert result["first_difference"]["decision"] == 1
    assert not result["complete_prefix_input_equivalence"]
    assert result["later_divergent_states_realignable"] is False


def test_replayed_choices_preserve_types_and_do_not_hide_extra_transport_fields() -> None:
    assert same({"value": 0.0}, {"value": 0})
    assert same(
        {"probability": 0.123, "action_index": 1}, {"probability": 0.123 + 1e-13, "action_index": 1}
    )
    assert not same({"action_index": 1}, {"action_index": True})
    assert not same({"probability": 0.1}, {"probability": 0.11})
    assert not same({"probability": 0.1}, {"probability": 0.1, "override": True})


def test_shared_input_contract_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node not on PATH; bundled-runtime tests run explicitly")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", "scripts/engine-shared-input-v1.test.mjs"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_rejected_client_still_waits_for_natural_game_shutdown() -> None:
    calls: list[str] = []

    class RejectedClient:
        def close(self) -> None:
            calls.append("client_closed")
            raise ValueError("SDK input rejected")

    class Game:
        def wait(self, *, timeout: float) -> int:
            assert timeout > 0
            calls.append("natural_game_exit")
            return 0

    client: Any = RejectedClient()
    child: Any = Game()
    assert finish_client(client, child, time.monotonic() + 5) == "SDK input rejected"
    assert calls == ["client_closed", "natural_game_exit"]
