"""Import only sealed round-56 states; qualify the versioned selection UI separately.

Old raw histories are provenance, not inputs to this continuation. Validate the
consumed report/checkpoint bytes and native admission, rather than repeatedly
rehashing every ancestral game journal at every new session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_selection_worker import PROTOCOL, SCRIPT
from spireshift.engine_worker import worker_helpers
from spireshift.native_context_journal import load_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_exploration_plan import validate
from spireshift.native_rest_exploration import CONTRACT
from spireshift.native_runtime_admission import launch_inputs
from spireshift.native_runtime_continuation import SOURCES as PRIOR_SOURCES

SOURCES = (
    *PRIOR_SOURCES,
    "engine_selection_worker.py",
    "engine_selection_checks.py",
    "engine_selection_audit.py",
    "native_rest_exploration.py",
    "native_exploration_math.py",
    "native_exploration_training.py",
    "native_exploration_collector.py",
    "native_exploration_plan.py",
    "native_exploration_admission.py",
    "native_exploration_execute.py",
    "native_exploration_comparison.py",
)


def load(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != _sha_file(q.root / "scripts/rest-exploration-v1.py")
        or cfg.get("policy_contract") != CONTRACT
        or cfg.get("selection_protocol") != PROTOCOL
        or cfg.get("worker_helpers_sha256") != worker_helpers(q.root, SCRIPT)
        or cfg.get("verifier_sha256")
        != _sha_file(q.root / "scripts/verify-selection-cursor-v1.mjs")
    ):
        raise ValueError(
            "Exploration implementation or public behavior changed; preserve frozen recipes"
        )

    def ref(name: str, identifier: str = "report_id") -> dict[str, Any]:
        r = cfg[name]
        p = q.root / r["path"]
        value = identified(p, identifier)
        if value[identifier] != r["id"]:
            raise ValueError(f"{name} identity changed")
        return value

    source = ref("source_report")
    old = json.loads((q.root / cfg["source_config"]["path"]).read_text())
    parent = json.loads((q.root / cfg["qualified_parent"]["path"]).read_text())
    if (
        source["status"] != "native_runtime_continuation_complete"
        or source["ending"]["milestone"] != 1792
        or source["config_id"] != manifest_identifier(old)
        or cfg["source_config"]["id"] != source["config_id"]
        or not source["original_states_unchanged"]
        or cfg["qualified_parent"]["id"] != manifest_identifier(parent)
    ):
        raise ValueError(
            "Require the completed round-56 continuation and its qualified parent settings"
        )
    # The completed result seals its launch recipe. The original parent settings
    # were reconstructed by load_continuation during preparation, then pinned
    # explicitly here; ancestors' raw histories are not consumed by this learner.
    name = cfg["source_config"]["path"]
    if source["sources"].get(name) != _sha_file(q.root / name):
        raise ValueError("Imported continuation recipe is not in the completed source seal")
    if any(
        old["implementation_sha256"].get(n) != cfg["implementation_sha256"][n]
        for n in PRIOR_SOURCES
    ):
        raise ValueError("Historical qualified implementation was modified")
    expected = []
    sources = {}
    for n in (2, 3):
        done = (
            Path(cfg["source_report"]["path"]).parent
            / "chunks"
            / source["ending"]["states"][str(n)]
            / "done.json"
        )
        if source["sources"].get(str(done)) != _sha_file(q.root / done):
            raise ValueError("Original final-state receipt changed")
        row = identified(q.root / done)["result"]
        p = q.root / row["state_path"]
        if source["sources"].get(row["state_path"]) != _sha_file(p):
            raise ValueError("Original final-state bytes changed")
        m, o, state_id = load_state(p)
        if (
            state_id != row["state_id"]
            or o.steps != source["ending_optimizer_steps"][str(n)]
            or o.steps < 1
        ):
            raise ValueError("Preserve full accumulated Adam state")
        expected.append(
            {
                "numerical_seed": n,
                "path": row["state_path"],
                "sha256": _sha_file(p),
                "model_id": m.model_id,
                "state_id": state_id,
                "optimizer_steps": o.steps,
                "round": 56,
                "scheduled_training_games": 1792,
            }
        )
        sources[str(done)] = _sha_file(q.root / done)
        sources[row["state_path"]] = _sha_file(p)
    if cfg["players"] != expected:
        raise ValueError("Both arms must fork the same current weights and optimizer states")
    effects = ref("selection_effects")
    if (
        effects["status"] != "native_large_subset_effects_pass"
        or effects["protocol"] != PROTOCOL
        or not all(effects["checks"].values())
        or effects["privileged_fixture"] is not True
        or effects["training_allowed"] is not False
        or len(effects["cases"]) != 4
        or not all(c["native_effect_pass"] for c in effects["cases"])
        or [(c["scenario"], len(c["selected_indices"])) for c in effects["cases"]]
        != [("pael", 5), ("pael", 5), ("kifuda", 3), ("kifuda", 0)]
    ):
        raise ValueError("Qualify native Pael removals and Kifuda enchantments/empty confirmation")
    effect_root = (q.root / cfg["selection_effects"]["path"]).parent
    checked_helpers = json.loads((effect_root / "case-0/source-at-launch/helpers.json").read_text())
    if any(checked_helpers.get(n) != sha for n, sha in cfg["worker_helpers_sha256"].items()):
        raise ValueError("Current selection UI differs from its native effect checks")
    check_sources(q.root, effects["sources"])
    sources.update(effects["sources"])
    seeds = ref("seed_manifest", "manifest_id")
    validate(cfg, seeds)
    if seeds["environment_id"] != parent["environment_manifest"]["id"]:
        raise ValueError("Exploration environment changed")
    required = {old["seed_manifest"]["path"], *[r["path"] for r in old["excluded_seed_manifests"]]}
    if not required <= {r["path"] for r in cfg["excluded_seed_manifests"]}:
        raise ValueError("Exclude all prior reserved seeds")
    for item in cfg["excluded_seed_manifests"]:
        prior = identified(q.root / item["path"], "manifest_id")
        if (
            prior["manifest_id"] != item["id"]
            or {r["id"] for r in prior["seeds"]} & {r["id"] for r in seeds["seeds"]}
            or {r["seed"] for r in prior["seeds"]} & {r["seed"] for r in seeds["seeds"]}
        ):
            raise ValueError("Fresh seeds overlap a prior reservation")
        sources[item["path"]] = _sha_file(q.root / item["path"])
    if cfg["stage"] != "short_bridge_control":
        control = ref("control_report")
        cc = json.loads((q.root / control["recipe_path"]).read_text())
        if (
            control["status"] != "native_rest_exploration_control_pass"
            or control["games_recorded"] != 20
            or control["config_id"] != manifest_identifier(cc)
            or cc["stage"] != "short_bridge_control"
            or any(
                cc[k] != cfg[k]
                for k in (
                    "players",
                    "implementation_sha256",
                    "entry_sha256",
                    "qualified_parent",
                    "source_config",
                    "source_report",
                    "selection_effects",
                    "worker_helpers_sha256",
                    "verifier_sha256",
                    "policy_contract",
                    "selection_protocol",
                    "arms",
                )
            )
            or cc["seed_manifest"] not in cfg["excluded_seed_manifests"]
        ):
            raise ValueError("Exact two-player/two-arm continuation control must pass first")
        check_sources(q.root, control["sources"])
        sources.update(control["sources"])
        sources[cfg["control_report"]["path"]] = _sha_file(q.root / cfg["control_report"]["path"])
    sources.update(
        {
            str(path.relative_to(q.root)): _sha_file(path),
            **{f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()},
            **{f"scripts/{n}": sha for n, sha in cfg["worker_helpers_sha256"].items()},
            "scripts/rest-exploration-v1.py": cfg["entry_sha256"],
            "scripts/verify-selection-cursor-v1.mjs": cfg["verifier_sha256"],
        }
    )
    for name in (
        "source_report",
        "source_config",
        "qualified_parent",
        "selection_effects",
        "seed_manifest",
    ):
        r = cfg[name]
        sources[r["path"]] = _sha_file(q.root / r["path"])
    for item in (parent["training_spec"], parent["environment_manifest"]):
        sources[item["path"]] = _sha_file(q.root / item["path"])
    # Parent stays unchanged here. The separate collector receives a copied helper map.
    return cfg, parent, seeds, sources


def inputs(
    q: EngineQualificationConfig, cfg: dict[str, Any], parent: dict[str, Any]
) -> dict[str, Any]:
    old = json.loads((q.root / cfg["source_config"]["path"]).read_text())
    value = launch_inputs(q, old, parent)
    effects = identified(q.root / cfg["selection_effects"]["path"])
    if value["inputs"]["build_report_id"] != effects["native_build_report_id"]:
        raise ValueError("Selection effect checks bind a different native host")
    return value
