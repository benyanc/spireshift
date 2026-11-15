"""Enumerate short native paths with exact prefix replay; preserve every failed attempt."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.full_run_experience import atomic_json
from spireshift.native_delayed_data import CONTRACT, ending, key, qualify
from spireshift.native_delayed_worker import DelayedWorker


def collect(
    q: EngineQualificationConfig,
    inputs: dict[str, Any],
    cfg: dict[str, Any],
    task: dict[str, Any],
    target: Path,
    deadline: float,
) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    pending: list[list[int]] = [[]]
    branches = 0
    while pending:
        prefix = pending.pop(0)
        parent_key = key(prefix)
        actions = len(nodes[parent_key]["public_input"]["candidates"]) if nodes else 3
        for action in range(actions):
            if time.monotonic() >= deadline - 20:
                raise TimeoutError("Preserve the unfinished delayed tree; never retry a branch")
            worker = DelayedWorker(
                q, inputs, target / f"edge-{branches:03d}", Path(cfg["node"]), cfg["helpers_sha256"]
            )
            try:
                current = worker.request(
                    "prepare_delayed",
                    family=task["family"],
                    seed=task["seed"]["seed"],
                    variant=task["seed"]["variant"],
                    timeout=35,
                )
                if not nodes:
                    public = current["model_input"]
                    if len(public["candidates"]) != actions:
                        raise ValueError("Delayed root must expose exactly three current actions")
                    nodes["root"] = {
                        "prefix": [],
                        "public_input": public,
                        "public_input_id": manifest_identifier(public),
                        "children": [],
                        "terminal": False,
                        "outcome": 0,
                        "boundary": "continue",
                    }
                for length in range(len(prefix) + 1):
                    visited = nodes[key(prefix[:length])]
                    if visited["public_input"] != current["model_input"]:
                        raise ValueError("Native counterfactual prefix public input did not repeat")
                    if length < len(prefix):
                        current = worker.request(
                            "step",
                            snapshot_id=current["snapshot"]["snapshot_id"],
                            action_index=prefix[length],
                        )
                if current["model_input"] != nodes[parent_key]["public_input"]:
                    raise ValueError("Replayed parent menu changed")
                successor = worker.request(
                    "step",
                    snapshot_id=current["snapshot"]["snapshot_id"],
                    action_index=action,
                )["model_input"]
                path = [*prefix, action]
                terminal, outcome, boundary = ending(
                    task["family"], nodes["root"]["public_input"], successor, len(path)
                )
                name = key(path)
                nodes[name] = {
                    "prefix": path,
                    "public_input": successor,
                    "public_input_id": manifest_identifier(successor),
                    "children": [],
                    "terminal": terminal,
                    "outcome": outcome,
                    "boundary": boundary,
                }
                nodes[parent_key]["children"].append(name)
                if not terminal:
                    pending.append(path)
                worker.close()
            except BaseException:
                worker.retire("Delayed diagnostic failure; preserve without uncertain replay")
                raise
            finally:
                worker.stop()
            branches += 1
            if branches > 39:
                raise ValueError("The fixed delayed tree exceeded its declared native edge cap")
    tree = {"contract": CONTRACT, "family": task["family"], "task": task, "nodes": nodes}
    qualified = qualify(tree)
    atomic_json(target / "tree.json", tree)
    return {
        "kind": "delayed_tree",
        "task": task,
        "tree_path": str((target / "tree.json").relative_to(q.root)),
        "tree_id": manifest_identifier(tree),
        "qualification": qualified,
        "native_branches": branches,
        "privileged_fixture": True,
        "ordinary_PPO_eligible": False,
        "full_run_attempts": 0,
        "game_apps_created": 0,
    }
