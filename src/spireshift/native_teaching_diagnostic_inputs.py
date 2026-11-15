"""Read only complete sealed teaching results, never sessions or an active source lock."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_experience_inputs import migrate
from spireshift.native_structured_state import load
from spireshift.native_teaching_data import BANK, CONTRACT, VARIANTS
from spireshift.native_teaching_inputs import validate
from spireshift.native_teaching_plan import schedule
from spireshift.training_objective import load_training_score_spec

SOURCES = (
    "native_teaching_diagnostic_inputs.py",
    "native_teaching_diagnostic_history.py",
    "native_teaching_diagnostic_metrics.py",
    "native_teaching_diagnostic_report.py",
)
ENTRIES = ("diagnose-native-teaching-v1.py", "diagnose-native-teaching-v1.sh")
MAIN = "configs/native-teaching/sts2-v0.111.0-a8-comparison-v1.json"
HISTORY = "configs/native-experience/sts2-v0.111.0-a8-comparison-v1.json"
LIMITS = {
    "wall_seconds": 240,
    "cpu_seconds": 240,
    "resident_memory_bytes": 1000000000,
    "storage_bytes": 100000000,
}


def local(root: Path, name: str) -> Path:
    path = root / name
    if (
        Path(name).is_absolute()
        or ".." in Path(name).parts
        or path.is_symlink()
        or path.resolve() != root.resolve() / name
    ):
        raise ValueError("Diagnostic paths must be distinct local references without aliases")
    return path


def complete_report(root: Path, source: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Check the final marker first. Never fall back to a partial session/chunk scan."""
    name = source["workspace"] + "/report.json"
    path = local(root, name)
    if not path.is_file():
        raise ValueError("Diagnose only completed results; leave the running experiment alone")
    report = identified(path)
    if (
        report.get("schema_version") != "native-plan-teaching-comparison-v1"
        or report.get("status") != "native_teaching_complete"
        or report.get("config_id") != manifest_identifier(source)
        or report.get("recipe_stage") != source["stage"]
        or report.get("completed_units") != report.get("planned_units")
        or report.get("all_finals_frozen_before_any_evaluation") is not True
        or report.get("heldout_used_for_fitting_or_selection") is not False
        or report.get("original_weights_and_all_Adam_unchanged") is not True
        or report.get("critic_and_credit_predictor_unchanged") is not True
        or report.get("student_inputs_public_only") is not True
    ):
        raise ValueError("Require the exact complete, frozen teaching comparison")
    return report, name


def receipts(
    root: Path, source: dict[str, Any], bank: dict[str, Any], report: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    journal = ChunkJournal(root, source)  # .completed is read-only; do not acquire its lock.
    done: dict[str, dict[str, Any]] = {}
    tasks = schedule(source, bank)
    for task in tasks:
        request = {"contract": CONTRACT, "task": task, "bank_id": bank["bank_id"]}
        if "state" in task:
            request["predecessor_state_id"] = done[task["state"]]["state_id"]
        if task["kind"] == "freeze":
            request["final_state_ids"] = {k: done[v]["state_id"] for k, v in task["states"].items()}
        if task["kind"] in {"fight", "fresh"}:
            request["frozen_finals_id"] = done["frozen-finals"]["frozen_finals_id"]
        sealed = journal.completed(task["key"], request)
        name = str((journal.path(task["key"]) / "done.json").relative_to(root))
        if sealed is None or report["sources"].get(name) != _sha_file(local(root, name)):
            raise ValueError("A complete result needs every expected sealed work unit")
        if any(report["sources"].get(n) != h for n, h in sealed["sources"].items()):
            raise ValueError("The final report must seal all work-unit evidence")
        result = sealed["result"]
        if result.get("kind") != task["kind"]:
            raise ValueError("The recorded unit is not the scheduled task")
        for k in ("player", "arm", "epoch", "root_id", "partition"):
            if k in task and result.get(k) != task[k]:
                raise ValueError("A diagnostic cell has the wrong player, arm or source root")
        if task["kind"] == "fresh" and result.get("seed_id") != task["seed"]["id"]:
            raise ValueError("A full-game cell has the wrong planned world")
        done[task["key"]] = result
    if len(tasks) != report["planned_units"] or report["natural_fights"] != [
        r for r in done.values() if r["kind"] == "fight"
    ]:
        raise ValueError("Final denominators differ from their completed receipts")
    states = {
        k: r for k, r in done.items() if r["kind"] in {"import", "fit"} and "diagnostics" in r
    }
    if states != report["states"] or done["frozen-finals"] != report["frozen_finals"]:
        raise ValueError("Saved fitting diagnostics or the all-finals barrier changed")
    return done


def prepare(root: Path, recipe: Path) -> dict[str, Any]:
    cfg = json.loads(recipe.read_text())
    control = cfg.get("stage") == "completed_control_diagnosis"
    if (
        cfg.get("schema_version") != "native-teaching-diagnostic-config-v1"
        or cfg.get("stage") not in {"completed_control_diagnosis", "completed_main_diagnosis"}
        or cfg.get("workspace")
        != "artifacts/native-teaching-diagnostics/sts2-v0.111.0-a8-"
        + ("control-v1" if control else "comparison-v1")
        or cfg.get("session_limits") != LIMITS
        or cfg.get("history_chunks") != [f"train-p2-batch128-r01-c{i:02d}" for i in range(2)]
        or cfg.get("maximum_probe_states") != 128
        or cfg.get("per_world_family_cap") != 2
        or cfg.get("implementation_sha256")
        != {n: _sha_file(root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != {n: _sha_file(root / "scripts" / n) for n in ENTRIES}
    ):
        raise ValueError("Freeze the separate finite saved-record diagnostic")
    ref = cfg["source_recipe"]
    expected = "configs/native-teaching/sts2-v0.111.0-a8-control-v1.json" if control else MAIN
    if ref["path"] != expected:
        raise ValueError("Use the declared completed control or completed main, never auto-follow")
    source = json.loads(local(root, ref["path"]).read_text())
    validate(source)
    if manifest_identifier(source) != ref["id"]:
        raise ValueError("The source experiment recipe changed")
    report, name = complete_report(root, source)  # Must pass before bank/chunk access.
    if cfg["source_report_id"] is not None and report["report_id"] != cfg["source_report_id"]:
        raise ValueError("Preserve the exact completed qualification result")
    bank = identified(local(root, BANK), "bank_id")
    if (
        bank["bank_id"] != source["lesson_bank"]["id"]
        or report["bank_id"] != bank["bank_id"]
        or bank["heldout_used_for_fitting"]
        or len(bank["lessons"]) != 2
        or any(r["partition"] != "fit" for r in bank["lessons"])
    ):
        raise ValueError("The report must retain the original two-world fitting bank")
    sources = dict(report["sources"])
    sources.update({name: _sha_file(local(root, name)), ref["path"]: _sha_file(root / ref["path"])})
    if sources.get(BANK) != _sha_file(root / BANK):
        raise ValueError("The completed source does not seal this lesson bank")
    protected = cfg["protected_recipe"]
    if protected["path"] != MAIN or _sha_file(local(root, MAIN)) != protected["sha256"]:
        raise ValueError("The running experiment's frozen recipe changed")
    main = json.loads((root / MAIN).read_text())
    sources[MAIN] = protected["sha256"]
    for section, folder in (
        ("implementation_sha256", "src/spireshift"),
        ("entry_sha256", "scripts"),
        ("helpers_sha256", "scripts"),
    ):
        for n, h in main[section].items():
            if sources.get(f"{folder}/{n}", h) != h:
                raise ValueError("The protected and source implementations disagree")
            sources[f"{folder}/{n}"] = h
    sources.update({f"src/spireshift/{n}": h for n, h in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": h for n, h in cfg["entry_sha256"].items()})
    sources[str(recipe.relative_to(root))] = _sha_file(recipe)
    check_sources(root, sources)
    done = receipts(root, source, bank, report)
    final_task = next(t for t in schedule(source, bank) if t["kind"] == "freeze")
    models: dict[int, dict[str, CachedContextModel]] = {}
    states: dict[int, dict[str, Any]] = {}
    for p in (2, 3):
        models[p], states[p] = {}, {}
        for arm in VARIANTS:
            row = done[final_task["states"][f"p{p}-{arm}"]]
            model, adam, sid = load(local(root, row["state_path"]))
            if (
                sid != row["state_id"]
                or model.model_id != row["model_id"]
                or adam.steps != row["optimizer_steps"]
                or done["frozen-finals"]["final_state_ids"][f"p{p}-{arm}"] != sid
            ):
                raise ValueError("Diagnose only the exact sealed final and full Adam state")
            models[p][arm], states[p][arm] = model, row
        parent = next(x for x in bank["runtime"]["players"] if x["numerical_seed"] == p)
        path = local(root, parent["path"])
        original, original_adam, original_id = load_state(path)
        copied, copied_adam, _ = load(local(root, states[p]["initial"]["state_path"]))
        if (
            _sha_file(path) != parent["sha256"]
            or original_id != parent["state_id"]
            or original.model_id != parent["model_id"]
            or original_adam.steps != parent["optimizer_steps"]
            or migrate(original, bank["runtime"]["environment_manifest"]["id"]).as_dict()
            != copied.as_dict()
            or original_adam.as_dict() != copied_adam.as_dict()
            or any(m.value_weights != copied.value_weights for m in models[p].values())
        ):
            raise ValueError("Preserve numerical parents, every Adam moment and fixed critic")
    score = load_training_score_spec(root / bank["runtime"]["training_spec"]["path"])
    if (
        score.spec_id != report["training_spec_id"]
        or score.evaluation_objective.as_dict() != report["full_run_objective"]
        or score.evaluation_objective.primary != "terminal_victory"
        or score.evaluation_objective.whole_run_budget != 128
    ):
        raise ValueError("Diagnosis never changes the A8 full-run objective or budget")
    return {
        "config": cfg,
        "protected_config": main,
        "source": source,
        "report": report,
        "bank": bank,
        "done": done,
        "models": models,
        "states": states,
        "sources": sources,
        "score": score,
    }
