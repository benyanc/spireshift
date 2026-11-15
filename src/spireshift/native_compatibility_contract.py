"""Checkpoint-bound cross-host input checks; never alter a policy or its Adam state."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_neural import validate_public_input
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import load_state
from spireshift.native_structured_model import encode
from spireshift.native_structured_state import load as load_structured
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "official_cli_checkpoint_compatibility_v1"
SCHEMA = "native-checkpoint-compatibility-receipt-v1"
RECORDED_CLAIM = "checkpoint_bound_recorded_public_input_regression_only"
REPLAY_SCOPE = "recorded_public_input_equivalence"
LIVE_SCOPE = "current_host_official_checkpoint_delivery"
ENVIRONMENT_SCOPE = "manifest_matches_verified_execution"
TRAINING_SCOPES = (ENVIRONMENT_SCOPE, REPLAY_SCOPE, LIVE_SCOPE)
TOLERANCE = 1e-12


def local(root: Path, name: str) -> Path:
    relative = Path(name)
    path = root / relative
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or path.is_symlink()
        or path.resolve() != root.resolve() / relative
    ):
        raise ValueError("Compatibility evidence must use local paths without aliases")
    return path


def verified(root: Path, ref: dict[str, Any]) -> Path:
    path = local(root, ref["path"])
    if _sha_file(path) != ref["sha256"]:
        raise ValueError(f"Compatibility input changed: {ref['path']}")
    return path


def checkpoint(
    root: Path, ref: dict[str, Any], environment_id: str, score_id: str
) -> tuple[CachedContextModel, dict[str, Any]]:
    path = verified(root, ref)
    value = identified(path, "state_id")
    if value["schema_version"] == "native-context-model-optimizer-v1":
        model, adam, state_id = load_state(path)
    else:
        model, adam, state_id = load_structured(path)
    if model.actor.environment_id != environment_id or model.feature_spec_id != score_id:
        raise ValueError("Checkpoint observation/score binding differs; no implicit migration")
    if any(
        ref.get(k, actual) != actual
        for k, actual in (
            ("state_id", state_id),
            ("model_id", model.model_id),
            ("optimizer_steps", adam.steps),
        )
    ):
        raise ValueError("Compatibility checkpoint or full optimizer identity changed")
    return model, {
        "path": ref["path"],
        "sha256": ref["sha256"],
        "state_id": state_id,
        "model_id": model.model_id,
        "optimizer_id": manifest_identifier(adam.as_dict()),
        "optimizer_steps": adam.steps,
    }


def difference_paths(a: Any, b: Any, prefix: str = "", limit: int = 12) -> list[str]:
    """Bounded structural witnesses; never flatten away ownership or ordered card lists."""
    if limit < 1 or a == b:
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        result: list[str] = []
        for key in sorted(a.keys() | b.keys()):
            path = f"{prefix}/{key}"
            result.extend(
                [path]
                if key not in a or key not in b
                else difference_paths(a[key], b[key], path, limit - len(result))
            )
            if len(result) >= limit:
                break
        return result
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        result = []
        for i, (left, right) in enumerate(zip(a, b, strict=True)):
            result.extend(difference_paths(left, right, f"{prefix}/{i}", limit - len(result)))
            if len(result) >= limit:
                break
        return result
    return [prefix or "/"] if limit else []


def distribution(
    model: CachedContextModel, public: dict[str, Any], score: TrainingScoreSpec
) -> tuple[tuple[dict[int, float], ...], list[float]]:
    validate_public_input(public)
    if not public["candidates"]:
        raise ValueError("Compatibility policy probes require an actual decision")
    rows, _ = encode(public, model, score)
    logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
    probabilities = [math.exp(v) for v in logs]
    if any(not math.isfinite(p) or p < 0 for p in probabilities) or not math.isclose(
        math.fsum(probabilities), 1.0, abs_tol=TOLERANCE
    ):
        raise ValueError("Invalid compatibility action distribution")
    return rows, probabilities


def compare_inputs(
    model: CachedContextModel, score: TrainingScoreSpec, pair: dict[str, Any]
) -> dict[str, Any]:
    native, official = pair["native_input"], pair["official_input"]
    keys = [pair[f"{host}_action_keys"] for host in ("native", "official")]
    for public, actions in zip((native, official), keys, strict=True):
        if (
            not all(isinstance(k, str) and k for k in actions)
            or len(actions) != len(public["candidates"])
            or len(set(actions)) != len(actions)
        ):
            raise ValueError("Ambiguous or incomplete semantic action mapping")
    nr, np = distribution(model, native, score)
    sr, sp = distribution(model, official, score)
    ni, si = ({k: i for i, k in enumerate(actions)} for actions in keys)
    common = sorted(ni.keys() & si.keys())
    maximum_feature_difference = max(
        (
            abs(nr[ni[k]].get(i, 0.0) - sr[si[k]].get(i, 0.0))
            for k in common
            for i in nr[ni[k]].keys() | sr[si[k]].keys()
        ),
        default=0.0,
    )
    maximum_probability_difference = max((abs(np[ni[k]] - sp[si[k]]) for k in common), default=0.0)
    missing, extra = sorted(ni.keys() - si.keys()), sorted(si.keys() - ni.keys())
    context_equal = native["context"] == official["context"]
    features_equal = bool(common) and maximum_feature_difference <= TOLERANCE
    distributions_equal = (
        bool(common) and not missing and not extra and maximum_probability_difference <= TOLERANCE
    )
    complete_reads = not pair["missing_native_reads"] and not pair["missing_official_reads"]
    return {
        "key": pair["key"],
        "family": pair["family"],
        "native_input_id": manifest_identifier(native),
        "official_input_id": manifest_identifier(official),
        "native_candidates": len(ni),
        "official_candidates": len(si),
        "common_actions": len(common),
        "missing_official_actions": missing,
        "extra_official_actions": extra,
        "missing_native_reads": pair["missing_native_reads"],
        "missing_official_reads": pair["missing_official_reads"],
        "all_advertised_reads_present": complete_reads,
        "context_equal": context_equal,
        "context_difference_paths": difference_paths(native["context"], official["context"]),
        "features_equal_on_common_actions": features_equal,
        "maximum_feature_difference": maximum_feature_difference,
        "distributions_equal": distributions_equal,
        "maximum_probability_difference": maximum_probability_difference,
        "native_greedy_action": keys[0][max(range(len(np)), key=np.__getitem__)],
        "official_greedy_action": keys[1][max(range(len(sp)), key=sp.__getitem__)],
        "passed": complete_reads
        and context_equal
        and not missing
        and not extra
        and features_equal
        and distributions_equal,
    }


def require_receipt(
    root: Path,
    report: dict[str, Any],
    binding: dict[str, Any],
    *,
    required_scopes: tuple[str, ...] = TRAINING_SCOPES,
) -> None:
    """Fail before a command starts; matching mechanics alone never approves a checkpoint."""
    if (
        report.get("schema_version") != SCHEMA
        or report.get("contract") != CONTRACT
        or report.get("binding") != binding
        or report.get("report_id")
        != manifest_identifier({k: v for k, v in report.items() if k != "report_id"})
    ):
        raise ValueError("Compatibility receipt belongs to different inputs or is corrupt")
    sources = report.get("sources", {})
    if not sources or any(_sha_file(local(root, n)) != h for n, h in sources.items()):
        raise ValueError("Compatibility evidence or implementation changed; rerun the gate")
    gates = report.get("gates", {})
    if report.get("claim_scope") != RECORDED_CLAIM:
        raise ValueError("This receipt version cannot certify a different compatibility scope")
    if (
        gates.get(LIVE_SCOPE) is not False
        or report.get("official_checkpoint_action_delivery_exercised") is not False
        or report.get("new_games_launched") != 0
    ):
        raise ValueError("Recorded-input evidence cannot certify live official checkpoint delivery")
    if any(gates.get(scope) is not True for scope in required_scopes):
        pending = ", ".join(s for s in required_scopes if gates.get(s) is not True)
        raise ValueError(f"Compatibility gate blocks new training/promotion: {pending}")
