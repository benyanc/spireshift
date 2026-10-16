"""Bounded random legal prefixes on frozen native inputs; never PPO experience.

This independent supplement does not change the implementation or helpers pinned
by an in-flight mechanics sweep. A successful prefix is not a completed game.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, TextIO

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_coverage import SCRIPT, _read_sealed, _saved_case, _sealed
from spireshift.engine_native import _private_path, _require_native_launch_support, _running_games
from spireshift.engine_qualification import EngineQualificationConfig, _inventory, _sha_file
from spireshift.engine_run import _assert_saved_public, _run_inputs, _verify_saved_observation
from spireshift.engine_worker import EngineWorker, _EpisodeLiveness, worker_helpers
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json

POLICY = "public_uniform_legal_choices_v1"
IMPLEMENTATION = ("engine_sequence_checks.py", "engine_worker.py", "engine_run.py")
SUCCESS = {"bounded_prefix_complete", "terminal_prefix_complete"}


def sequence_implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / "src/spireshift" / name) for name in IMPLEMENTATION}


class PublicRandomChooser:
    """Sample every advertised action, including Skip, from an independent RNG.

    Environment seeds and native/default-policy suggestions are never supplied.
    Sorting semantic candidates makes transport action ordering irrelevant.
    """

    def __init__(self, action_seed: str) -> None:
        self.rng = random.Random(action_seed)

    def choose(self, public: dict[str, Any]) -> int:
        _assert_saved_public(public)
        candidates = public["candidates"]
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Random exploration requires a nonempty current public menu")
        ordered = sorted(range(len(candidates)), key=lambda i: manifest_identifier(candidates[i]))
        return ordered[self.rng.randrange(len(ordered))]


def load_sequence_config(path: Path, q: EngineQualificationConfig) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    cases = cfg.get("cases", [])
    if (
        cfg.get("schema_version") != "native-legal-sequence-config-v1"
        or cfg.get("qualification_config_id") != q.config_id
        or cfg.get("policy") != POLICY
        or cfg.get("training_allowed") is not False
        or cfg.get("fixture_mutations_allowed") is not False
        or cfg.get("implementation_sha256") != sequence_implementation(q.root)
        or cfg.get("helpers_sha256") != worker_helpers(q.root, SCRIPT)
        or type(cfg.get("maximum_decisions")) is not int
        or not 16 <= cfg["maximum_decisions"] <= 512
        or type(cfg.get("case_wall_seconds")) is not int
        or not 5 <= cfg["case_wall_seconds"] <= 45
        or type(cfg.get("maximum_wall_seconds")) is not int
        or not 30 <= cfg["maximum_wall_seconds"] <= 180
        or type(cfg.get("minimum_total_decisions")) is not int
        or cfg["minimum_total_decisions"] < 1
        or cfg.get("required_families") != ["event_option", "map_navigation", "combat_turn"]
        or not isinstance(cases, list)
        or not 2 <= len(cases) <= 32
    ):
        raise ValueError("Expected pinned finite public legal-sequence diagnostics")
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "seed", "action_seed"}
            or not re.fullmatch(r"[a-z0-9-]{1,64}", str(case["case_id"]))
            or not re.fullmatch(r"SP1RESH1FTSEQUENCE[0-9]{3}", str(case["seed"]))
            or not re.fullmatch(r"independent-actions-[0-9]{3}", str(case["action_seed"]))
        ):
            raise ValueError("Sequence cases require distinct native and action RNG identities")
    if len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate sequence case identity")
    groups = Counter((c["seed"], c["action_seed"]) for c in cases)
    if len({c["seed"] for c in cases}) < 2 or not any(n > 1 for n in groups.values()):
        raise ValueError("Sequences require independent game seeds and an exact repeat control")
    _private_path(q.root, cfg["workspace"])
    recipe = json.loads((q.root / cfg["run_config"]).read_text())
    if manifest_identifier(recipe) != cfg["run_config_id"]:
        raise ValueError("Sequence native run recipe changed")
    return dict(cfg)


def _write_trace(stream: TextIO, digest: Any, public: dict[str, Any], choice: int | None) -> None:
    _assert_saved_public(public)
    # Compare public semantics rather than runtime handles or menu serialization order.
    record = {
        "context": public["context"],
        "candidates": sorted(public["candidates"], key=manifest_identifier),
        "chosen": public["candidates"][choice] if choice is not None else None,
    }
    line = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    stream.write(line)
    digest.update(line.encode())


def audit_sequence_trace(path: Path, maximum: int) -> dict[str, Any]:
    digest = hashlib.sha256()
    decisions = 0
    families: Counter[str] = Counter()
    verbs: Counter[str] = Counter()
    finished = False
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            _assert_saved_public(row)
            if finished or set(row) != {"context", "candidates", "chosen"}:
                raise ValueError("Sequence trace continued beyond its final observation")
            candidates = row["candidates"]
            if not isinstance(candidates, list) or candidates != sorted(
                candidates, key=manifest_identifier
            ):
                raise ValueError("Sequence trace lost its canonical public menu")
            families[row["context"]["interaction"]["kind"]] += 1
            if row["chosen"] is None:
                finished = True
            elif row["chosen"] not in candidates:
                raise ValueError("Sequence trace chose an unadvertised action")
            else:
                decisions += 1
                verbs[row["chosen"]["verb"]] += 1
            canonical = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            digest.update((canonical + "\n").encode())
    if not finished or not 1 <= decisions <= maximum:
        raise ValueError("Sequence trace is partial or beyond its declared bound")
    return {
        "decisions": decisions,
        "families": dict(families),
        "verbs": dict(verbs),
        "semantic_trace_id": "sha256:" + digest.hexdigest(),
    }


def walk_sequence(
    worker: EngineWorker, case: dict[str, Any], cfg: dict[str, Any], trace: Path
) -> dict[str, Any]:
    chooser = PublicRandomChooser(case["action_seed"])
    liveness = _EpisodeLiveness()
    digest = hashlib.sha256()
    families: Counter[str] = Counter()
    verbs: Counter[str] = Counter()
    decisions = 0
    maximum_floor = maximum_act = 0
    started = time.monotonic()
    result: dict[str, Any] = {"status": "failed", "terminal": False, "victory": False}
    with gzip.open(trace, "xt", encoding="utf-8") as stream:
        current = worker.request("mount", seed=case["seed"], timeout=25)
        runtime = current["snapshot"]["session"]["runtime_instance_id"]
        while True:
            _verify_saved_observation(current, runtime)
            public, facts = current["model_input"], current["facts"]
            _assert_saved_public(public)
            families[current["snapshot"]["interaction"]["kind"]] += 1
            maximum_floor = max(maximum_floor, facts["floor"])
            maximum_act = max(maximum_act, facts["act"])
            if time.monotonic() - started >= cfg["case_wall_seconds"]:
                raise TimeoutError("Random sequence wall cap; no next action or retry")
            if facts["terminal"]:
                _write_trace(stream, digest, public, None)
                # This panel checks legal prefixes. Independent ending qualification
                # belongs to the separate same-build native lifecycle fixture.
                result.update(
                    status="terminal_prefix_complete", terminal=True, victory=facts["victory"]
                )
                break
            if decisions == cfg["maximum_decisions"]:
                _write_trace(stream, digest, public, None)
                result.update(status="bounded_prefix_complete")
                break
            liveness.observe(current["public_key"])
            choice = chooser.choose(public)
            _write_trace(stream, digest, public, choice)
            verbs[public["candidates"][choice]["verb"]] += 1
            current = worker.request(
                "step",
                snapshot_id=current["snapshot"]["snapshot_id"],
                action_index=choice,
                timeout=min(20, cfg["case_wall_seconds"] - (time.monotonic() - started)),
            )
            decisions += 1
    return {
        **result,
        "decisions": decisions,
        "families": dict(families),
        "verbs": dict(verbs),
        "maximum_floor": maximum_floor,
        "maximum_act": maximum_act,
        "semantic_trace_id": "sha256:" + digest.hexdigest(),
        "wall_seconds": time.monotonic() - started,
        "full_run_attempts": 1,
        "optimizer_steps": 0,
        "training_allowed": False,
    }


def summarize_sequences(cfg: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    families: Counter[str] = Counter()
    verbs: Counter[str] = Counter()
    repeated: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for row in rows:
        families.update(row.get("families", {}))
        verbs.update(row.get("verbs", {}))
        key = row["spec"]["seed"], row["spec"]["action_seed"]
        repeated.setdefault(key, set()).add((row["status"], row.get("semantic_trace_id", "")))
    planned = Counter((c["seed"], c["action_seed"]) for c in cfg["cases"])
    repeats = [k for k, n in planned.items() if n > 1]
    repeated_ok = all(
        sum((r["spec"]["seed"], r["spec"]["action_seed"]) == k for r in rows) == planned[k]
        and len(repeated.get(k, set())) == 1
        and next(iter(repeated[k]))[0] in SUCCESS
        for k in repeats
    )
    failed = [r for r in rows if r["status"] not in SUCCESS]
    decisions = sum(r.get("decisions", 0) for r in rows)
    complete = len(rows) == len(cfg["cases"])
    covered = decisions >= cfg["minimum_total_decisions"] and all(
        families[name] > 0 for name in cfg["required_families"]
    )
    return {
        "status": "legal_sequence_panel_pass"
        if complete and not failed and repeated_ok and covered
        else "legal_sequence_panel_incomplete",
        "planned_cases": len(cfg["cases"]),
        "completed_cases": len(rows),
        "not_attempted_cases": len(cfg["cases"]) - len(rows),
        "failed_cases": len(failed),
        "independent_game_seeds": len({r["spec"]["seed"] for r in rows}),
        "verified_bounded_prefixes": sum(r["status"] == "bounded_prefix_complete" for r in rows),
        "terminal_games_observed": sum(r.get("terminal") is True for r in rows),
        "decisions": decisions,
        "families": dict(families),
        "verbs": dict(verbs),
        "repeat_controls_identical": repeated_ok,
        "minimum_sequence_coverage_met": covered,
        "failures": [{"case_id": r["spec"]["case_id"], "error": r.get("error")} for r in failed],
        "case_reports": [r["report_id"] for r in rows],
        "full_run_attempts": len(rows),
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "training_allowed": False,
        "policy_quality_evaluated": False,
        "all_interactions_proven": False,
        "terminal_outcomes_readiness_eligible": False,
        "claim_scope": "bounded_native_public_uniform_legal_prefixes_and_exact_repeat_only",
    }


def run_legal_sequences(q: EngineQualificationConfig, path: Path, *, node: Path) -> dict[str, Any]:
    cfg = load_sequence_config(path, q)
    inputs = _run_inputs(q, q.root / cfg["run_config"])
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Wait for the active game or sweep to finish before sequence diagnostics")
    workspace = _private_path(q.root, cfg["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    recipe = workspace / "recipe.json"
    if recipe.exists() and json.loads(recipe.read_text()) != cfg:
        raise ValueError("Sequence workspace belongs to another recipe")
    if not recipe.exists():
        atomic_json(recipe, cfg)
    rows = []
    started = time.monotonic()
    for case in cfg["cases"]:
        folder = workspace / "cases" / case["case_id"]
        saved = folder / "result.json"
        if saved.exists():
            rows.append(_saved_case(saved, case, manifest_identifier(cfg)))
            continue
        if time.monotonic() - started >= cfg["maximum_wall_seconds"]:
            break
        folder.mkdir(parents=True, exist_ok=False)
        worker = EngineWorker(
            q,
            inputs,
            folder / "worker",
            node,
            cfg["helpers_sha256"],
            script=SCRIPT,
            projection_cache=workspace / "shared-projection",
        )
        try:
            result = walk_sequence(worker, case, cfg, folder / "public-prefix.jsonl.gz")
            shutdown = worker.close()
        except (ValueError, TimeoutError, OSError, KeyError) as error:
            result = {"status": "failed", "error": str(error)}
            shutdown = worker.retire(str(error))
        finally:
            worker.stop()
        row = _sealed(
            {
                "spec": case,
                "plan_id": manifest_identifier(cfg),
                **result,
                "shutdown": shutdown,
                "evidence_files": _inventory(folder),
            }
        )
        atomic_json(saved, row)
        rows.append(row)
        print(
            f"Legal sequence {len(rows)}/{len(cfg['cases'])}: {case['case_id']} {row['status']}",
            flush=True,
        )
    isolation = immutable_checks(q, inputs)
    if not all(isolation.values()):
        raise ValueError("Sequence diagnostic changed protected shared inputs")
    summary = _sealed(
        {
            "schema_version": "native-legal-sequence-report-v1",
            "config_id": manifest_identifier(cfg),
            "input_config_id": inputs["recipe"]["input_config_id"],
            "host_sha256": inputs["build"]["artifact_sha256"],
            **summarize_sequences(cfg, rows),
            "isolation": isolation,
            "wall_seconds_this_invocation": time.monotonic() - started,
        }
    )
    target = workspace / "summary.json"
    if len(rows) == len(cfg["cases"]):
        if target.exists():
            old = _read_sealed(target)
            if (
                old["case_reports"] != summary["case_reports"]
                or old["config_id"] != summary["config_id"]
            ):
                raise ValueError("Saved random sequence summary changed")
            return old
        atomic_json(target, summary)
    return summary


def verify_legal_sequences(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg = load_sequence_config(path, q)
    inputs = _run_inputs(q, q.root / cfg["run_config"])
    workspace = _private_path(q.root, cfg["workspace"])
    if json.loads((workspace / "recipe.json").read_text()) != cfg:
        raise ValueError("Saved sequence recipe differs")
    saved = _read_sealed(workspace / "summary.json")
    rows = [
        _saved_case(workspace / "cases" / c["case_id"] / "result.json", c, manifest_identifier(cfg))
        for c in cfg["cases"]
    ]
    for row in rows:
        if row["status"] not in SUCCESS:
            raise ValueError("Saved sequence includes a failed prefix")
        shutdown = row["shutdown"]
        if (
            shutdown.get("clean_exit") is not True
            or shutdown.get("exit", {}).get("code") != 0
            or shutdown.get("exit", {}).get("signal") is not None
            or shutdown.get("runtime_errors") != []
        ):
            raise ValueError("Saved sequence lacks a clean native worker shutdown")
        audit = audit_sequence_trace(
            workspace / "cases" / row["spec"]["case_id"] / "public-prefix.jsonl.gz",
            cfg["maximum_decisions"],
        )
        if any(row.get(k) != v for k, v in audit.items()):
            raise ValueError("Sequence summary disagrees with its saved public prefix")
    rebuilt = summarize_sequences(cfg, rows)
    if (
        saved.get("schema_version") != "native-legal-sequence-report-v1"
        or saved["config_id"] != manifest_identifier(cfg)
        or saved["input_config_id"] != inputs["recipe"]["input_config_id"]
        or saved["host_sha256"] != inputs["build"]["artifact_sha256"]
        or any(saved.get(k) != v for k, v in rebuilt.items())
        or set(saved.get("isolation", {}))
        != {"candidate_unchanged", "runtime_unchanged", "sdk_unchanged", "frozen_archive_unchanged"}
        or not all(v is True for v in saved["isolation"].values())
        or rebuilt["status"] != "legal_sequence_panel_pass"
    ):
        raise ValueError(
            "Saved sequence coverage is incomplete, inconsistent or for another engine"
        )
    return {
        "valid": True,
        "report_id": saved["report_id"],
        "games_replayed": 0,
        "checked_cases": len(rows),
        "training_allowed": False,
        "resolved_requirement": "random_legal_action_sequences",
    }
