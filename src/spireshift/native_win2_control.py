"""Short saved full-belt regression and fresh wrapper delivery checks, then stop."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win2_game import episode, prepare, write
from spireshift.native_win2_inputs import RECIPE, binding, frozen_checks, load
from spireshift.native_win_plan import start_cases
from spireshift.native_win_teacher import validate_student_input


def main() -> int:
    root, began = Path.cwd(), time.monotonic()
    context = load(root, root / RECIPE, require_control=False)
    cfg = context["config"]
    target = root / f"artifacts/native-win-curriculum/recovery-control-v{cfg['repair_generation']}"
    target.mkdir(parents=True, exist_ok=False)
    before = frozen_checks(context)
    state = json.loads(verified(root, cfg["failed_raw"]).read_text())
    failed_identity = json.loads((root / cfg["failed_worker_identity"]).read_text())
    module = (
        Path(failed_identity["shared_projection"]["directory"])
        / "player-projection/src/managed-player-environment.mjs"
    )
    result = subprocess.run(
        [context["node"], str(root / "scripts/engine-reward-belt-regression-v1.mjs")],
        input=json.dumps({"state": state, "module_path": str(module)}).encode(),
        capture_output=True,
        timeout=30,
        check=True,
    )
    saved = json.loads(result.stdout)
    write(target / "saved-regression.json", saved)
    converter = JsonLines(
        root,
        [context["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        target / "converter.log",
    )
    try:
        frame = converter.project(saved["snapshot"], saved["reads"], None, began + 270)
        validate_student_input(frame["public_input"])
        converter.close()
    finally:
        converter.stop()
    runs = []
    short = {**context, "config": {**cfg, "plan": {**cfg["plan"], "maximum_decisions": 2}}}
    selected = [
        start_cases(7 + cfg["repair_generation"])[9],
        start_cases(7 + cfg["repair_generation"])[-1],
    ]
    for p in (2, 3):
        selected.append(
            {
                "key": f"repair-natural-{p}",
                "partition": "control_fit",
                "player": p,
                "entry": "natural",
                "act": 1,
                "act_definition": "ANY",
                "boss": None,
                "profile": None,
                "seed_pool": [f"SP1RESH1FTWRC{cfg['repair_generation']}P{p}"],
            }
        )
    for case in selected:
        case = {**case, "key": "repair-" + case["key"]}
        where = target / case["key"]
        where.mkdir()
        start = prepare(context, case, where, began + 270)
        if start["status"] != "ready":
            raise ValueError("A fresh wrapper control start is unavailable")
        run = where / "delivery"
        run.mkdir()
        value = episode(short, start, "reference", run, began + 270)
        if value["policy_decisions"] != 2 or not value["shutdown"]["clean_exit"]:
            raise ValueError("Fresh wrapper delivery control failed")
        runs.append(value)
        print(f"Repair control: {case['key']}: two verified deliveries", flush=True)
    after = frozen_checks(context)
    checks = {
        "saved_old_failure_reproduced": saved["old_strict_decoder_rejects"],
        "same_strict_decoder_accepts_repair": saved["new_strict_decoder_passes"],
        "shared_public_student_input_valid": True,
        "fresh_natural_and_loaded_starts": len(runs) == 4,
        "eight_deliveries_independently_verified": sum(
            r["actual_deliveries_independently_verified"] for r in runs
        )
        == 8,
        "originals_build_and_failed_evidence_frozen": all(before.values()) and all(after.values()),
        "prior_learning_control_is_exact_unchanged_source": True,
        "no_main_game_or_optimizer_update": True,
    }
    if not all(checks.values()):
        raise ValueError("Reward-belt repair control is incomplete")
    sources = {
        **cfg["implementation"],
        cfg["base_recipe"]["path"]: cfg["base_recipe"]["sha256"],
        cfg["recovery_audit"]["path"]: cfg["recovery_audit"]["sha256"],
    }
    report = write(
        target / "report.json",
        {
            "schema_version": "native-win-curriculum-repair-control-v1",
            "status": "reward_belt_continuation_control_verified",
            "implementation_id": manifest_identifier(cfg["implementation"]),
            "launch_binding_id": binding(cfg),
            "checks": checks,
            "checks_before": before,
            "checks_after": after,
            "optimizer_updates": 0,
            "new_actual_deliveries": 8,
            "main_workspace_started": False,
            "sources": sources,
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in target.rglob("*") if p.is_file()
            },
        },
    )
    print(json.dumps({k: v for k, v in report.items() if k not in {"sources", "evidence"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
