from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_chest_endings, native_entry_text_endings, native_entry_text_inputs


@pytest.mark.parametrize("name", ["native_run", "observations", "preflight", "run", "main"])
def test_new_panel_preserves_qualified_delivery_compute_and_ending_checks(name: str) -> None:
    before = ast.parse(inspect.getsource(getattr(native_chest_endings, name)))
    after = ast.parse(inspect.getsource(getattr(native_entry_text_endings, name)))
    assert ast.dump(before) == ast.dump(after)


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def source_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    old, new = tmp_path / "old-native", tmp_path / "new-native"
    method = "    private static string? StripVisibleText(string? value)"
    boundary = "    /// <summary>Common context added to every decision point.</summary>"
    for folder, body in [(old, "old"), (new, "new")]:
        write(
            folder / "src/Sts2Headless/RunSimulator.cs",
            f"fixed prefix\n{method}\n{body}\n{boundary}\nfixed suffix",
        )
        write(folder / "src/Sts2Headless/Mechanics.cs", "same game behavior")
    before_host, after_host = tmp_path / "old-host", tmp_path / "new-host"
    for folder, value in [(before_host, "old"), (after_host, "new")]:
        write(folder / "LiveHost/TutorialModalSurfaceReader.cs", value)
        write(folder / "PlayerEnvironment/Observation/SnapshotBuilder.cs", value)
        write(folder / "LiveHost/Unrelated.cs", "unchanged")
    write(after_host / "NativeUi/NativeTutorialEntryTransition.cs", "new readiness guard")
    monkeypatch.setattr(
        native_entry_text_inputs,
        "_hashed",
        lambda _: {"artifact": str(before_host / "out/STS2_MCP.dll")},
    )
    ctx = {
        "native": {"candidate": old},
        "connector": type(
            "Connector", (), {"document": {"local_build": {"build_report": "unused"}}}
        )(),
    }
    return ctx, {"candidate_directory": str(new)}, after_host


def test_declared_source_scope_accepts_only_formatter_and_tutorial_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, candidate, host = source_pair(tmp_path, monkeypatch)
    result = native_entry_text_inputs.source_delta(tmp_path, ctx, candidate, host)
    assert result["native_changes_outside_StripVisibleText"] is False
    assert result["counter_rules_unchanged"] is True
    assert result["native_unchanged_production_files"] == 1


@pytest.mark.parametrize(
    "location", ["before_formatter", "after_formatter", "mechanics", "other_connector"]
)
def test_unrelated_production_edit_revokes_inherited_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    ctx, candidate, host = source_pair(tmp_path, monkeypatch)
    simulator = Path(candidate["candidate_directory"]) / "src/Sts2Headless/RunSimulator.cs"
    if location == "before_formatter":
        simulator.write_text(simulator.read_text().replace("fixed prefix", "changed prefix"))
    elif location == "after_formatter":
        simulator.write_text(simulator.read_text().replace("fixed suffix", "changed suffix"))
    elif location == "mechanics":
        write(simulator.parent / "Mechanics.cs", "changed game behavior")
    else:
        write(host / "LiveHost/Unrelated.cs", "changed unrelated behavior")
    with pytest.raises(ValueError, match="changes exceed|production sources|production Connector"):
        native_entry_text_inputs.source_delta(tmp_path, ctx, candidate, host)
