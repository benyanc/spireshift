from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_consequence_config as module
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_consequence_data import CONTRACT, TARGETS
from spireshift.native_consequence_math import ARMS, HEAD_SEEDS, SETTINGS


def sealed(root: Path, name: str, body: dict[str, Any], key: str = "manifest_id") -> dict[str, Any]:
    path = root / name
    atomic_json(path, {**body, key: manifest_identifier(body)})
    return {"path": name, "id": manifest_identifier(body)}


def fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any]]:
    monkeypatch.setattr(module, "SOURCES", ("core.py",))
    monkeypatch.setattr(module, "ENTRIES", ("entry.py",))
    for name in ("src/spireshift/core.py", "scripts/entry.py"):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("frozen")
    old = sealed(tmp_path, "old.json", {"seeds": [{"id": 1, "seed": "OLD"}]})
    fresh = sealed(
        tmp_path,
        "control-seeds.json",
        {
            "schema_version": "native-combat-consequence-seeds-v1",
            "environment_id": "env",
            "partition": "control",
            "seeds": [
                {"id": 100 + i, "seed": f"NEW{i}", "numerical_seed": 2 + i} for i in range(2)
            ],
        },
    )
    cfg = {
        **{k: None for k in module.SHARED},
        "schema_version": "native-combat-consequence-config-v1",
        "stage": "short_control",
        "workspace": "artifacts/control",
        "consequence_contract": CONTRACT,
        "targets": list(TARGETS),
        "learning": dict(SETTINGS),
        "arms": list(ARMS),
        "deployment_head_seed": HEAD_SEEDS[0],
        "cv_head_seeds": [HEAD_SEEDS[0]],
        "source_world_split": "leave_one_entire_source_world_out_separately_per_parent_v1",
        "information_scope": "public_student_inputs_privileged_fixed_world_supervised_labels",
        "ordinary_PPO_eligible": False,
        "maximum_decisions": 4096,
        "episode_wall_seconds": 120,
        "implementation_sha256": {"core.py": _sha_file(tmp_path / "src/spireshift/core.py")},
        "entry_sha256": {"entry.py": _sha_file(tmp_path / "scripts/entry.py")},
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        },
        "seed_manifest": fresh,
        "freshness_exclusions": [old],
        "excluded_seed_manifests": [],
    }
    atomic_json(tmp_path / "control.json", cfg)
    teacher = {"freshness_exclusions": [old], "excluded_seed_manifests": [], "seed_manifest": old}
    return cfg, teacher


def test_exact_finite_loss_schedule_code_target_contract_and_ownership_are_admitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, teacher = fixture(tmp_path, monkeypatch)
    assert module.load_config(tmp_path, tmp_path / "control.json") == cfg
    seeds, sources = module.evaluation_seeds(tmp_path, cfg, teacher, "env")
    assert [s["numerical_seed"] for s in seeds] == [2, 3]
    assert set(sources) == {"control-seeds.json", "old.json"}


@pytest.mark.parametrize(
    "fault", ["reward", "code", "epochs", "head_seed", "split", "cap", "targets"]
)
def test_schedule_or_software_changes_cannot_silently_resume_saved_fits(
    fault: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, _ = fixture(tmp_path, monkeypatch)
    if fault == "reward":
        cfg["ordinary_PPO_eligible"] = True
    elif fault == "code":
        (tmp_path / "src/spireshift/core.py").write_text("changed")
    elif fault == "epochs":
        cfg["learning"]["epochs"] = 1000
    elif fault == "head_seed":
        cfg["deployment_head_seed"] = 999
    elif fault == "split":
        cfg["source_world_split"] = "shuffle_individual_branches"
    elif fault == "cap":
        cfg["session_limits"]["wall_seconds"] = 10000
    else:
        cfg["targets"].append("handwritten_HP_reward")
    (tmp_path / "control.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="Freeze"):
        module.load_config(tmp_path, tmp_path / "control.json")


@pytest.mark.parametrize("same", ["id", "seed"])
def test_development_or_control_worlds_cannot_overlap_prior_training(
    same: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, teacher = fixture(tmp_path, monkeypatch)
    values = [{"id": 100 + i, "seed": f"NEW{i}", "numerical_seed": 2 + i} for i in range(2)]
    values[0][same] = 1 if same == "id" else "old"
    cfg["seed_manifest"] = sealed(
        tmp_path,
        "changed.json",
        {
            "schema_version": "native-combat-consequence-seeds-v1",
            "environment_id": "env",
            "partition": "control",
            "seeds": values,
        },
    )
    with pytest.raises(ValueError, match="Reused"):
        module.evaluation_seeds(tmp_path, cfg, teacher, "env")


def test_main_also_excludes_both_other_native_control_worlds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, teacher = fixture(tmp_path, monkeypatch)
    cfg = copy.deepcopy(control)
    cfg.update(
        stage="bounded_learning_comparison",
        control_recipe={"path": "control.json"},
        excluded_seed_manifests=[control["seed_manifest"]],
    )
    fresh = [{"id": 200 + i, "seed": f"DEV{i}"} for i in range(32)]
    cfg["seed_manifest"] = sealed(
        tmp_path,
        "main.json",
        {
            "schema_version": "native-combat-consequence-seeds-v1",
            "environment_id": "env",
            "partition": "development",
            "seeds": fresh,
        },
    )
    assert len(module.evaluation_seeds(tmp_path, cfg, teacher, "env")[0]) == 32
    cfg["excluded_seed_manifests"] = []
    with pytest.raises(ValueError, match="exclude both"):
        module.evaluation_seeds(tmp_path, cfg, teacher, "env")


def test_missing_native_qualification_or_failed_control_does_not_admit_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control, _ = fixture(tmp_path, monkeypatch)
    main = copy.deepcopy(control)
    main.update(
        stage="bounded_learning_comparison",
        control_recipe={"path": "control.json", "sha256": _sha_file(tmp_path / "control.json")},
    )
    main["control_report"] = sealed(
        tmp_path,
        "report.json",
        {
            "status": "offline_units_complete",
            "config_id": manifest_identifier(control),
            "completed_games": 0,
        },
        "report_id",
    )
    with pytest.raises(ValueError, match="native controls"):
        module.qualified_control(tmp_path, main)


def test_whole_game_split_exclusions_cannot_be_silently_shortened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, teacher = fixture(tmp_path, monkeypatch)
    cfg["freshness_exclusions"] = []
    with pytest.raises(ValueError, match="historical"):
        module.evaluation_seeds(tmp_path, cfg, teacher, "env")
