from __future__ import annotations

import copy
import json
import subprocess
import sys
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest
from test_full_run_public_policy import CATALOG, MenuRun, environment

from spireshift.adapters.evangambit_public_choices import PublicChoiceEnvironment
from spireshift.core.manifest import load_patch_manifest, manifest_identifier
from spireshift.full_run_experience import atomic_json, save_episode
from spireshift.full_run_relational_experience import (
    collect_a8_episode,
    load_a8_episode,
    verified_samples,
)
from spireshift.full_run_relational_math import initialize_critic
from spireshift.full_run_relational_policy import initial_relational_model
from spireshift.full_run_relational_ppo import (
    PPOConfig,
    inspect_ppo,
    load_actor_critic,
    load_ppo_config,
    ppo_protocol,
    run_locked,
    run_ppo,
)

CONFIG = Path("configs/full-run-ppo/sts2-v0.107.1-public-a8-relational-v3.json")


def small_config() -> PPOConfig:
    d = copy.deepcopy(load_ppo_config(CONFIG).document)
    d["network"].update(dimension=128, hidden_units=4)
    d["workers"] = 1
    d["learning"].update(
        maximum_rounds=2,
        minimum_rounds=2,
        confirmation_every=1,
        plateau_confirmations=2,
        epochs=1,
        minibatch_decisions=8,
    )
    p = d["learning"]
    p["rollout_seed_panels"] = [seeds[:2] for seeds in p["rollout_seed_panels"][:2]]
    p["confirmation_train_seeds"] = p["confirmation_train_seeds"][:2]
    p["development_seeds"] = p["development_seeds"][:2]
    d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
    return PPOConfig.from_mapping(d)


class ImmediateExecutor:
    def __init__(self, **kwargs: Any) -> None:
        self.requests: list[dict[str, Any]] = []
        self.fail_next = False

    def __enter__(self) -> ImmediateExecutor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def submit(self, function: Any, request: dict[str, Any]) -> Future[dict[str, Any]]:
        self.requests.append(request)
        result: Future[dict[str, Any]] = Future()
        if self.fail_next:
            self.fail_next = False
            result.set_exception(RuntimeError("Synthetic worker failure"))
            return result
        c = load_ppo_config(Path(request["config_path"]))
        m = load_actor_critic(Path(request["model_path"]))
        env = PublicChoiceEnvironment(
            lambda: MenuRun(),
            load_patch_manifest(Path(c.document["inputs"]["ruleset_manifest"]["path"])),
            environment(MenuRun())._layout,
            backend=MenuRun(),
        )
        case, trace = collect_a8_episode(
            lambda: env,
            c.ruleset,
            m,
            c.score,
            c.splits,
            seed=request["seed"],
            partition=request["partition"],
            behavior=request["behavior"],
            temperature=request["temperature"],
            sampling_seed=request["sampling_seed"],
        )
        save_episode(Path(request["case_path"]), case, trace)
        result.set_result(case)
        return result


@pytest.mark.parametrize("key", ["train", "development", "identity", "schema"])
def test_prior_seed_reuse_or_wrong_inventory_or_old_schema_is_rejected(key: str) -> None:
    d = copy.deepcopy(small_config().document)
    inventory = json.loads(Path(d["prior_seed_inventory"]["path"]).read_text())
    if key == "train":
        d["learning"]["rollout_seed_panels"][0][0] = inventory["train_seeds"][0]
    elif key == "development":
        d["learning"]["development_seeds"][0] = inventory["development_seeds"][0]
    elif key == "identity":
        d["prior_seed_inventory"]["id"] = "sha256:" + "0" * 64
    else:
        d["schema_version"] = "public-a8-ppo-config-v1"
    d["config_id"] = manifest_identifier({k: v for k, v in d.items() if k != "config_id"})
    with pytest.raises(ValueError):
        PPOConfig.from_mapping(d)


def test_saved_v3_sampled_input_verifies_and_rejects_probability_tampering(tmp_path: Path) -> None:
    c = small_config()
    m = initialize_critic(initial_relational_model(c.ruleset, CATALOG, "a" * 64))
    env = PublicChoiceEnvironment(
        lambda: MenuRun(),
        load_patch_manifest(Path(c.document["inputs"]["ruleset_manifest"]["path"])),
        environment(MenuRun())._layout,
        backend=MenuRun(),
    )
    case, trace = collect_a8_episode(
        lambda: env,
        c.ruleset,
        m,
        c.score,
        c.splits,
        seed=c.document["learning"]["rollout_seed_panels"][0][0],
        partition="train",
        behavior="sampled_softmax",
        sampling_seed=7,
    )
    path = tmp_path / "case.json"
    save_episode(path, case, trace)
    checked, saved = load_a8_episode(path, case["binding"])
    assert len(verified_samples(checked, saved, c.ruleset, m, c.score)) == len(trace)
    altered = copy.deepcopy(saved)
    altered[0]["behavior_probability"] += 0.1
    with pytest.raises(ValueError, match="probability"):
        verified_samples(checked, altered, c.ruleset, m, c.score)


def test_training_freezes_before_development_and_explicit_resume_runs_no_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import spireshift.full_run_relational_ppo as module

    config = small_config()
    path = tmp_path / "config.json"
    atomic_json(path, config.document)
    output = tmp_path / "result"
    output.mkdir()
    executor = ImmediateExecutor()
    monkeypatch.setattr(module, "ThreadPoolExecutor", lambda **kwargs: executor)
    monkeypatch.setattr(module, "load_printed_card_catalog", lambda *args: CATALOG)
    report = run_locked(config, path, output, ppo_protocol(config))
    assert report["rounds_completed"] == 2
    assert report["final_test_opened"] is report["checkpoint_promoted"] is False
    assert all(u["optimization"]["optimizer_steps"] > 0 for u in report["updates"])
    first_dev = next(i for i, r in enumerate(executor.requests) if r["partition"] == "development")
    assert all(r["partition"] == "development" for r in executor.requests[first_dev:])
    assert (
        json.loads((output / "train-selection.json").read_text())["selection_uses_development"]
        is False
    )
    before = len(executor.requests)
    assert inspect_ppo(path, output)["report_id"] == report["report_id"]
    assert run_ppo(path, output, resume=True)["report_id"] == report["report_id"]
    assert len(executor.requests) == before
    shown = subprocess.run(
        [
            sys.executable,
            "-m",
            "spireshift.full_run_relational_ppo",
            str(path),
            str(output),
            "--show",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["report_id"] == report["report_id"]
    assert json.loads(shown.stdout)["trace_inputs_reaudited"] is False
    text = capsys.readouterr().out
    assert "Round 1/2 summary" in text and "Best sampled game so far" in text
    with pytest.raises(FileExistsError):
        run_ppo(path, output)


def test_worker_failure_kept_in_denominator_with_unknown_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.full_run_relational_ppo as module

    c = small_config()
    path = tmp_path / "config.json"
    atomic_json(path, c.document)
    root = tmp_path / "result"
    root.mkdir()
    executor = ImmediateExecutor()
    executor.fail_next = True
    monkeypatch.setattr(module, "ThreadPoolExecutor", lambda **kwargs: executor)
    monkeypatch.setattr(module, "load_printed_card_catalog", lambda *args: CATALOG)
    report = run_locked(c, path, root, ppo_protocol(c))
    assert report["interrupted_or_worker_failed_attempts"] == 1
    assert report["all_episode_costs_known"] is False
    assert any((root / r["path"]).name == "failure.json" for r in report["cases"])


def test_short_recipe_panels_disjoint_from_owner_training_and_development() -> None:
    owner = load_ppo_config(CONFIG).document["learning"]
    short = load_ppo_config(
        Path("configs/full-run-ppo/sts2-v0.107.1-public-a8-relational-smoke-v3.json")
    ).document["learning"]
    a = (
        {s for p in owner["rollout_seed_panels"] for s in p}
        | set(owner["confirmation_train_seeds"])
        | set(owner["development_seeds"])
    )
    b = (
        {s for p in short["rollout_seed_panels"] for s in p}
        | set(short["confirmation_train_seeds"])
        | set(short["development_seeds"])
    )
    assert not a & b
