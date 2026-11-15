"""Exercise reproduced code against saved failures and frozen content, without games."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_e2e_contract import difference_paths
from spireshift.native_entry_text_inputs import load
from spireshift.native_flow_verification_v12 import records

SAVED = Path("artifacts/native-chest-repair/natural-ending-panel-v1")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def entry_vectors() -> list[dict[str, Any]]:
    settled: dict[str, Any] = {
        "tutorial_id": "map_select_ftue",
        "traveling": False,
        "map_open": False,
        "combat_room": True,
        "context_known": True,
        "starting": False,
        "in_progress": True,
        "has_combat_state": True,
        "live_room": True,
        "live_hand": True,
        "native_play_phase": True,
        "readiness": "ready",
    }
    cases = []

    def add(key: str, pending: bool, **changes: Any) -> None:
        cases.append({**settled, **changes, "key": key, "expected_pending": pending})

    add(
        "saved_unknown_before_rejected_click",
        True,
        context_known=False,
        starting=True,
        in_progress=False,
        has_combat_state=False,
        live_room=False,
        live_hand=False,
        native_play_phase=False,
    )
    add("saved_round_one_empty_hand_before_first_input", True, native_play_phase=False)
    add("settled_modal_actions_disabled_does_not_deadlock", False)
    add(
        "open_map_retains_completed_combat",
        False,
        map_open=True,
        context_known=False,
        in_progress=False,
        has_combat_state=False,
        live_room=False,
        live_hand=False,
        native_play_phase=False,
    )
    add("travel_wins_over_open_map", True, traveling=True, map_open=True)
    add(
        "known_event_needs_no_combat_state",
        False,
        combat_room=False,
        in_progress=False,
        has_combat_state=False,
        live_room=False,
        live_hand=False,
        native_play_phase=False,
    )
    add("unknown_noncombat_entry_waits", True, combat_room=False, context_known=False)
    for tutorial in [
        "shuffle_ftue",
        "combat_rules_ftue",
        "accept_tutorials_ftue",
        "power_card_ftue",
        "unmapped_future_tutorial",
    ]:
        add(
            tutorial,
            False,
            tutorial_id=tutorial,
            context_known=False,
            native_play_phase=False,
            traveling=True,
        )
    for readiness in ["settling", "degraded"]:
        add("preserve_" + readiness, False, readiness=readiness)
    for mask in range(128):
        flags = [bool(mask & (1 << bit)) for bit in range(7)]
        add(
            f"combat_entry_prerequisites_{mask}",
            mask != 127,
            context_known=flags[0],
            starting=not flags[1],
            in_progress=flags[2],
            has_combat_state=flags[3],
            live_room=flags[4],
            live_hand=flags[5],
            native_play_phase=flags[6],
        )
    return cases


def text_vectors() -> list[tuple[str | None, str | None, str | None]]:
    return [
        (None, None, None),
        ("", "", None),
        ("[rainbow freq=0.3 sat=0.8 val=1]Chaos[/rainbow]", "Chaos", None),
        ("[rainbow val=1 freq=-.3 sat=+0.8]7[/rainbow]", "7", None),
        ("[b]A [rainbow freq=0.3]B[/rainbow] C[/b]", "A B C", None),
        (
            "[rainbow freq=0.3]2[img]res://ui/energy.png[/img]3[img]res://ui/energy.png[/img][/rainbow]",
            "2[energy.png]3[energy.png]",
            None,
        ),
        (
            "[img]res://one/gold.png[/img] 12 [img]res://two/block.png[/img]",
            "[gold.png] 12 [block.png]",
            None,
        ),
        ("[gold.png][gold.png] 3", "[gold.png][gold.png] 3", None),
        ("[counter: 2/3]", "[counter: 2/3]", None),
        ("[unknown_style freq=0.3]fact", "[unknown_style freq=0.3]fact", None),
        ("[rainbow future=2]fact", "[rainbow future=2]fact", None),
        ("[rainbow freq=NaN]fact", "[rainbow freq=NaN]fact", None),
        ("[rainbow freq=0.3", "[rainbow freq=0.3", None),
        ("[rainbow freq=0.3 sat=0.8 val=1]", "", None),
        ("one\ntwo  17", "one two  17", None),
        ("[img]res://ui/energy.png", None, "System.InvalidOperationException"),
        ("[{color}]dynamic[/{color}]", "[{color}]dynamic[/{color}]", None),
        ("[rainbow freq=0.3]0 1 12.5[/rainbow]", "0 1 12.5", None),
    ]


def corpus(folder: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []

    def visit(value: Any, key: str) -> None:
        if isinstance(value, str):
            result.append((key, value))
        elif isinstance(value, dict):
            for name, child in sorted(value.items()):
                visit(child, f"{key}/{name}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{key}/{index}")

    for path in sorted(folder.glob("*.json")):
        visit(json.loads(path.read_text()), path.name)
    return result


def run(root: Path, recipe: Path) -> dict[str, Any]:
    started = time.monotonic()
    ctx = load(root, recipe)
    cfg = ctx["config"]
    require(cfg["stage"] == "saved_source_checks", "Only source/saved controls here")
    output = root / cfg["workspace"]
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "active.json", {"config_id": manifest_identifier(cfg)})
    host_report = _hashed(root / ctx["connector"].document["local_build"]["build_report"])
    host = Path(host_report["artifact"]).parent.parent
    candidate = ctx["native"]["candidate"]
    before = Path(
        json.loads(verified(root, cfg["parent_build_report"]).read_text())["build"]["repaired"][0][
            "artifact"
        ]
    )
    content = corpus(candidate / "localization_eng")
    require(len(content) == 6902, "Frozen English localization inventory changed")
    native_frames = [
        r["frame"]
        for r in records(root / SAVED / "player-3-natural-604/native/shared-public.jsonl.gz")
        if r["kind"] == "policy_input"
    ]
    official_frames = [
        r["frame"]
        for r in records(root / SAVED / "player-3-natural-604/official/live-public.jsonl.gz")
        if r["kind"] == "policy_input"
    ]
    native_input, official_input = (
        native_frames[45]["public_input"],
        official_frames[45]["public_input"],
    )
    require(
        difference_paths(native_input, official_input)
        == ["/context/interaction/content/context/body"],
        "Saved first difference changed",
    )
    saved_body = native_input["context"]["interaction"]["content"]["context"]["body"]
    official_body = official_input["context"]["interaction"]["content"]["context"]["body"]
    rows = list(records(root / SAVED / "player-2-natural-603/official/live-public.jsonl.gz"))
    rejected = rows[-1]
    require(
        rejected["kind"] == "receipt"
        and rejected["receipt"]["delivery"] == "not_delivered"
        and rejected["receipt"]["reason_code"] == "stale_snapshot",
        "Preserve the actual rejected receipt",
    )
    old_snapshot = next(
        r["snapshot"]
        for r in reversed(rows[:-1])
        if r["kind"] == "observed"
        and r["snapshot"]["snapshot_id"] == rejected["before_snapshot_id"]
    )
    successor = rejected["receipt"]["successor"]
    require(
        old_snapshot["interaction"]["content"]["context"]["kind"] == "unknown"
        and successor["interaction"]["content"]["context"]["kind"] == "combat",
        "Saved tutorial entry evidence changed",
    )
    require(
        old_snapshot["bound_actions"] == successor["bound_actions"]
        and old_snapshot["interaction"]["content"]["surface"]
        == successor["interaction"]["content"]["surface"],
        "Saved modal/action changed",
    )
    player = successor["interaction"]["content"]["context"]["player"]
    require(player["hand"] == [] and player["energy"] == 0, "Expected saved initial hand/energy")
    fan_before = next(
        r
        for r in old_snapshot["persistent"]["content"]["player"]["relics"]
        if r["definition_id"] == "ORNAMENTAL_FAN"
    )
    fan_after = next(
        r
        for r in successor["persistent"]["content"]["player"]["relics"]
        if r["definition_id"] == "ORNAMENTAL_FAN"
    )
    require(
        "counter" not in fan_before and fan_after["counter"] == 2,
        "Do not rewrite absent/visible counter facts",
    )
    vectors = text_vectors()
    entries = entry_vectors()
    spec = {
        "native_assemblies": [str(before), ctx["native"]["build"]["artifact"]],
        "host_assembly": host_report["artifact"],
        "game_data": cfg["game_data"],
        "text_cases": [v for _, v in content] + [v[0] for v in vectors] + [saved_body],
        "entry_cases": entries,
    }
    atomic_json(output / "probe-input.json", spec)
    environment = {**os.environ, "DOTNET_ROLL_FORWARD": "Major"}

    def command(args: list[str], name: str, stdin: str | None = None) -> str:
        completed = subprocess.run(
            args, cwd=root, env=environment, input=stdin, text=True, capture_output=True, timeout=45
        )
        (output / f"{name}.stdout.log").write_text(completed.stdout)
        (output / f"{name}.stderr.log").write_text(completed.stderr)
        completed.check_returncode()
        return completed.stdout

    command(
        [
            "dotnet",
            "test",
            str(host / "tests/STS2Connector.Host.Tests/STS2Connector.Host.Tests.csproj"),
            "--nologo",
            f"-p:STS2GameDataDir={cfg['game_data']}",
            "-p:UseSharedCompilation=false",
            "--logger",
            "trx;LogFileName=source-saved.trx",
            "--results-directory",
            str(output / "host-tests"),
        ],
        "host-tests",
    )
    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    counters = ET.parse(output / "host-tests/source-saved.trx").find(".//t:Counters", ns)
    require(
        counters is not None
        and counters.attrib["failed"] == "0"
        and counters.attrib["passed"] == "221",
        "All 221 Host tests must pass",
    )
    command(
        [
            "dotnet",
            "build",
            "backend-patches/tutorial-entry-text-v1/Probe.csproj",
            "--nologo",
            "-p:UseSharedCompilation=false",
            "-o",
            str(output / "probe"),
        ],
        "probe-build",
    )
    actual = json.loads(
        command(["dotnet", str(output / "probe/Probe.dll")], "probe", json.dumps(spec))
    )
    atomic_json(output / "probe-output.json", actual)
    for index, expected in enumerate([before, Path(ctx["native"]["build"]["artifact"])]):
        require(actual["identities"][index]["path"] == str(expected), "Probe assembly path changed")
    require(
        actual["identities"][1]["mvid"] == ctx["native"]["build"]["artifact_mvid"]
        and actual["identities"][2]["mvid"] == host_report["fresh_builds"][0]["module_version_id"],
        "Probe must execute reproduced assemblies",
    )
    old_text, new_text = actual["text_results"]
    changed = []
    for index, (key, value) in enumerate(content):
        if old_text[index] != new_text[index]:
            require(
                "[rainbow freq=0.3 sat=0.8 val=1]" in value, "Unexpected content rendering change"
            )
            require(
                new_text[index]
                == {
                    "value": actual["official_text_results"][index].replace("\n", " "),
                    "error": None,
                },
                "Affected rendering must match official helper",
            )
            changed.append(key)
    require(len(changed) == 4, "Exactly the four known parameterized strings must change")
    for index, (_, expected_value, error) in enumerate(vectors, start=len(content)):
        require(
            new_text[index] == {"value": expected_value, "error": error},
            f"Text regression failed: {index}",
        )
    require(
        old_text[-1]["value"] == saved_body
        and new_text[-1] == {"value": official_body, "error": None},
        "Saved Aroma rendering must match exactly",
    )
    repaired = copy.deepcopy(native_input)
    repaired["context"]["interaction"]["content"]["context"]["body"] = new_text[-1]["value"]
    require(
        not difference_paths(repaired, official_input),
        "Diagnostic repaired input must match full saved public input",
    )
    for entry_expected, result in zip(entries, actual["entry_results"], strict=True):
        readiness = (
            "settling" if entry_expected["expected_pending"] else entry_expected["readiness"]
        )
        require(
            result["key"] == entry_expected["key"]
            and result["pending"] is entry_expected["expected_pending"]
            and result["readiness"] == readiness
            and result["authority"] is (readiness == "ready"),
            "Entry readiness/authority regression failed",
        )
    check_sources(root, ctx["sources"])
    protected = json.loads(verified(root, cfg["protection"]).read_text())
    check_sources(root, protected)
    report = {
        "schema_version": "native-entry-text-source-saved-result-v1",
        "status": "entry_text_source_saved_qualified",
        "config_id": manifest_identifier(cfg),
        "environment_id": ctx["environment"]["manifest_id"],
        "host_tests_passed": 221,
        "compiled_entry_vectors": len(entries),
        "localization_strings_checked": len(content),
        "changed_localization_keys": changed,
        "unchanged_localization_strings": len(content) - len(changed),
        "text_edge_vectors": len(vectors),
        "saved_repaired_input_matches": True,
        "saved_tutorial_receipt": {"delivery": "not_delivered", "reason_code": "stale_snapshot"},
        "ornamental_fan_absence_and_visible_two_preserved": True,
        "historical_failed_pairs_relabelled_as_pass": False,
        "native_phase_vectors_are_separate_source_diagnostics": True,
        "live_readiness_and_endings_still_require_fresh_owner_panel": True,
        "new_games": 0,
        "optimizer_updates": 0,
        "training_allowed": False,
        "automatic_follow_up": False,
        "protected_prior_files_exact": len(protected),
        "source_delta": cfg["source_delta"],
        "sources": ctx["sources"],
        "evidence": {
            str(p.relative_to(root)): _sha_file(p)
            for p in output.rglob("*")
            if p.is_file() and p.name != "active.json"
        },
        "wall_seconds": time.monotonic() - started,
    }
    report["report_id"] = manifest_identifier(report)
    atomic_json(output / "report.json", report)
    (output / "active.json").rename(output / "complete.json")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()
    report = run(Path.cwd(), args.recipe.resolve())
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"sources", "evidence", "source_delta"}},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
