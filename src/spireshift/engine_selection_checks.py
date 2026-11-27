"""Four finite native effect checks for Pael/Kifuda subset selection, no training."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_run import _run_inputs
from spireshift.engine_runtime_gaps import deck, step
from spireshift.engine_selection_worker import DIAGNOSTIC, PROTOCOL, SelectionWorker
from spireshift.engine_worker import worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_reuse import check_sources


def run(q: EngineQualificationConfig, path: Path, node: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    inputs = _run_inputs(q, q.root / cfg["run"]["path"])
    if manifest_identifier(inputs["recipe"]) != cfg["run"]["id"]:
        raise ValueError("Selection check native host recipe changed")
    target = q.root / cfg["workspace"]
    if (target / "report.json").exists():
        saved = identified(target / "report.json")
        check_sources(q.root, saved["sources"])
        return saved
    if _running_games():
        raise ValueError("Close STS2 before the isolated selection checks")
    start = time.monotonic()
    snapshot = _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2")
    cases = []
    sources = {
        str(path.relative_to(q.root)): _sha_file(path),
        "src/spireshift/engine_selection_checks.py": _sha_file(Path(__file__)),
        "src/spireshift/engine_selection_worker.py": _sha_file(
            q.root / "src/spireshift/engine_selection_worker.py"
        ),
    }
    for i, (scenario, n, selected) in enumerate(
        (
            ("pael", 21, [0, 2, 4, 6, 20]),
            ("pael", 21, [20, 19, 18, 17, 16]),
            ("kifuda", 15, [0, 7, 14]),
            ("kifuda", 15, []),
        )
    ):
        if time.monotonic() - start > 120:
            raise TimeoutError("Short selection control reached its cap")
        w = SelectionWorker(
            q,
            inputs,
            target / f"case-{i}",
            node,
            worker_helpers(q.root, DIAGNOSTIC),
            script=DIAGNOSTIC,
        )
        try:
            w.request("mount", seed=f"SP1RESH1FTSELECTCHECK{i + cfg['seed_offset']:03d}")
            o = w.request("selection_fixture", scenario=scenario, cards=n)
            before = deck(o)
            menu = o["model_input"]["candidates"]
            option = next(
                k
                for k, c in enumerate(menu)
                if c["verb"] == "activate" and c["label"].startswith("Claim ")
            )
            o = step(w, o, option)
            if o["model_input"]["context"]["interaction"]["kind"] != "card_selection":
                raise ValueError("Native selection was not exposed")
            for pick in selected:
                menu = o["model_input"]["candidates"]
                k = next(
                    k
                    for k, c in enumerate(menu)
                    if c["verb"] == "select" and c["subject"]["properties"]["index"] == pick
                )
                o = step(w, o, k)
                if deck(o) != before:
                    raise ValueError("Local prefix mutated the native deck")
            k = next(
                k for k, c in enumerate(o["model_input"]["candidates"]) if c["verb"] == "confirm"
            )
            o = step(w, o, k)
            after = deck(o)
            cards = [
                c
                for r in o["model_input"]["context"]["reads"]
                if r["kind"] == "run_deck"
                for c in r["content"]["cards"]
            ]
            enchanted = sum("enchantment" in c for c in cards)
            if (scenario == "pael" and len(after) != n - 5) or (
                scenario == "kifuda" and (len(after) != n or enchanted != len(selected))
            ):
                raise ValueError(
                    "Native selection did not apply the exact removal/enchantment count"
                )
            cases.append(
                {
                    "scenario": scenario,
                    "cards": n,
                    "selected_indices": selected,
                    "before_deck_size": len(before),
                    "after_deck_size": len(after),
                    "enchanted_cards": enchanted,
                    "native_effect_pass": True,
                }
            )
            w.close()
        finally:
            w.stop()
        sources.update(
            {
                str(p.relative_to(q.root)): _sha_file(p)
                for p in w.workspace.rglob("*")
                if p.is_file() and not p.is_symlink()
            }
        )
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = (
        _shared_snapshot(Path.home() / "Library/Application Support/SlayTheSpire2") == snapshot
    )
    if not all(checks.values()):
        raise ValueError("Immutable inputs changed")
    body = {
        "schema_version": "native-selection-effects-v1",
        "config_id": manifest_identifier(cfg),
        "status": "native_large_subset_effects_pass",
        "protocol": PROTOCOL,
        "cases": cases,
        "checks": checks,
        "sources": sources,
        "native_build_report_id": inputs["inputs"]["build_report_id"],
        "privileged_fixture": True,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "wall_seconds": time.monotonic() - start,
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(target / "report.json", result)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("qualification", type=Path)
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path, required=True)
    a = p.parse_args()
    q = load_engine_qualification_config(a.qualification)
    print(
        json.dumps(
            {k: v for k, v in run(q, q.root / a.config, a.node).items() if k != "sources"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
