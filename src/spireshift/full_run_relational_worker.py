"""Disposable v3 episode worker, derived from the frozen v2 isolation contract."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import LegalAction, Observation, Transition
from spireshift.full_run_experience import atomic_json

ISOLATION_ID = "public-a8-relational-disposable-episode-process-v3"
EVIDENCE_FILES = (
    "worker-request.json",
    "worker-started.json",
    "last-public-step.json",
    "worker.log",
    "post-crash-case.json",
    "case.jsonl.gz",
)


class JournalEnvironment:
    """Debug-only last public step, stored separately from learning experience."""

    def __init__(self, environment: EnvironmentAdapter, journal: Path) -> None:
        self.environment, self.journal = environment, journal
        self.patch_id, self.ruleset = environment.patch_id, environment.ruleset
        self.observation: Observation | None = None
        self.steps = 0

    def reset(self, seed: int) -> Observation:
        self.observation = self.environment.reset(seed)
        return self.observation

    def legal_actions(self) -> Any:
        return self.environment.legal_actions()

    def step(self, action: LegalAction) -> Transition:
        if self.observation is None:
            raise ValueError("Journal environment was not reset")
        temporary = self.journal.with_name(f".{self.journal.name}.{os.getpid()}.debug-partial")
        temporary.write_text(
            json.dumps(
                {
                    "claim_scope": "debug_only_last_public_step_never_a_training_input",
                    "worker_pid": os.getpid(),
                    "decision_index": self.steps,
                    "observation": self.observation.as_dict(),
                    "action": action.as_dict(),
                },
                sort_keys=True,
            ),
        )
        os.replace(temporary, self.journal)
        transition = self.environment.step(action)
        self.observation = transition.next_observation
        self.steps += 1
        return transition

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> JournalEnvironment:
        raise ValueError("Policy-only episode journals do not clone games")

    def close(self) -> None:
        close = getattr(self.environment, "close", None)
        if callable(close):
            close()


def execution_evidence(directory: Path) -> dict[str, Any]:
    return {
        name: {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name in EVIDENCE_FILES
        if (path := directory / name).is_file()
    }


def verify_execution_evidence(directory: Path, evidence: dict[str, Any]) -> None:
    for name, ref in evidence.items():
        if (
            name not in EVIDENCE_FILES
            or set(ref) != {"path", "sha256"}
            or ref["path"] != name
            or hashlib.sha256((directory / name).read_bytes()).hexdigest() != ref["sha256"]
        ):
            raise ValueError("Saved worker crash evidence differs")


def run_isolated_episode(request: dict[str, Any]) -> None:
    directory = Path(request["case_path"]).parent
    request_path = directory / "worker-request.json"
    if request_path.exists():
        raise ValueError("A disposable episode must not replay a previous worker request")
    atomic_json(request_path, request)
    # Inherit the resource wrapper's process group so its job-wide cap also stops
    # all disposable children. This child creates no subprocesses of its own.
    with (directory / "worker.log").open("wb") as log:
        try:
            result = subprocess.run(
                [sys.executable, "-m", __name__, str(request_path)],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=request["episode_wall_seconds"],
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Disposable game exceeded its frozen wall-time cap") from exc
    if result.returncode:
        raise RuntimeError(f"Disposable game exited with code {result.returncode}; see worker.log")


def main() -> None:
    from spireshift.full_run_relational_ppo import episode_worker

    request = json.loads(Path(sys.argv[1]).read_text())
    directory = Path(request["case_path"]).parent
    atomic_json(directory / "worker-started.json", {"pid": os.getpid(), "seed": request["seed"]})
    episode_worker(request)


if __name__ == "__main__":
    main()
