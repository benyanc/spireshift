"""Isolated actual-engine workers. Frozen inputs are shared; mutable profiles are private.

One Node control process and one native process per worker. A failed/uncertain worker
is stopped and explicitly retired; its workspace and marker are never reused.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _stop_child
from spireshift.engine_native import DATA_RELATIVE, _private_path, _sandbox
from spireshift.engine_qualification import GAME_RELATIVE, EngineQualificationConfig, _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.full_run_experience import atomic_json

WORKER_SCRIPT = "engine-native-worker-v4.mjs"
ISOLATION_ID = "actual-engine-process-profile-reset-v1"
LIVENESS_POLICY: dict[str, Any] = {
    "id": "public_exploration_bounded_v1",
    "maximum_consecutive_identical_observations": 8,
    "maximum_visits_per_public_state": 64,
    "forced_actions": False,
}


class _EpisodeLiveness:
    """Bound actual no-ops and menu cycles without masking optional actions."""

    def __init__(self) -> None:
        self.visits: dict[str, int] = {}
        self.previous: str | None = None
        self.consecutive = 0

    def observe(self, key: str) -> None:
        self.visits[key] = self.visits.get(key, 0) + 1
        self.consecutive = self.consecutive + 1 if key == self.previous else 1
        self.previous = key
        if self.consecutive > LIVENESS_POLICY["maximum_consecutive_identical_observations"]:
            raise ValueError("Consecutive unchanged public observation cap")
        if self.visits[key] > LIVENESS_POLICY["maximum_visits_per_public_state"]:
            raise ValueError("Repeated public-state exploration cap")


def worker_helpers(root: Path, script: str = WORKER_SCRIPT) -> dict[str, str]:
    return {
        name: _sha_file(root / "scripts" / name)
        for name in sorted(_script_closure(root / "scripts", {script}))
    }


class EngineWorker:
    def __init__(
        self,
        qualification: EngineQualificationConfig,
        inputs: dict[str, Any],
        workspace: Path,
        node: Path,
        helpers: dict[str, str],
        *,
        script: str = WORKER_SCRIPT,
        projection_cache: Path | None = None,
    ) -> None:
        self.root, self.workspace, self.inputs = qualification.root, workspace, inputs
        _private_path(self.root, str(workspace.relative_to(self.root)))
        if script not in {
            WORKER_SCRIPT,
            "engine-mechanics-worker-v1.mjs",
            "engine-mechanics-worker-v2.mjs",
        }:
            raise ValueError("Unqualified worker entry point")
        if projection_cache is not None and script not in {
            "engine-mechanics-worker-v1.mjs",
            "engine-mechanics-worker-v2.mjs",
        }:
            raise ValueError("Shared projection is diagnostic-only")
        if helpers != worker_helpers(self.root, script):
            raise ValueError("Native worker helper inventory changed")
        # mkdir itself is exclusive: no automatic reuse/clearing of an interrupted marker.
        workspace.mkdir(parents=True, exist_ok=False)
        self.marker = workspace / "active.json"
        atomic_json(self.marker, {"isolation_id": ISOLATION_ID, "owner_process": os.getpid()})
        source = workspace / "source-at-launch"
        source.mkdir()
        for name in helpers:
            (source / name).write_bytes((self.root / "scripts" / name).read_bytes())
        atomic_json(source / "helpers.json", helpers)
        profile = workspace / "private-profile"
        profile.mkdir()
        candidate, runtime = inputs["candidate"], inputs["runtime"]
        archive, localization = inputs["archive"], inputs["localization"]
        user_data = Path.home() / "Library/Application Support"
        denied = [
            user_data / "SlayTheSpire2",
            user_data / "Godot/app_userdata/SlayTheSpire2",
            user_data / "Steam",
            archive.parent,
            candidate,
            runtime,
            localization,
        ]
        (workspace / "profile-isolation.sb").write_text(
            _sandbox(denied)
            + "(deny file-read* file-write* (require-all "
            + f"(subpath {json.dumps(str(workspace.parent))}) "
            + f"(require-not (subpath {json.dumps(str(workspace))}))))\n"
        )
        (profile / "tmp").mkdir()
        headless = next(x for x in qualification.document["sources"] if x["name"] == "headless")
        spec = {
            "projection_cache": str(projection_cache) if projection_cache is not None else None,
            "coverage_diagnostic": script
            in {"engine-mechanics-worker-v1.mjs", "engine-mechanics-worker-v2.mjs"},
            "headless_root": str(_private_path(self.root, headless["path"])),
            "attempt": str(workspace),
            "profile": str(profile),
            "candidate": str(candidate),
            "artifact": str(candidate / "src/Sts2Headless/bin/Release/net9.0/Sts2Headless.dll"),
            "game_data": str(archive / GAME_RELATIVE / DATA_RELATIVE),
            "dotnet": str(runtime / "dotnet"),
            "expected": inputs["build"],
            "projection": inputs["projection"],
            "content_policy": inputs["recipe"]["content_policy"],
            "environment_fingerprint": manifest_identifier(
                {"input_config_id": inputs["recipe"]["input_config_id"], "isolation": ISOLATION_ID}
            ),
        }
        environment = dict(os.environ)
        environment.update(
            DOTNET_ROLL_FORWARD="LatestPatch", STS2_NATIVE_LOCALIZATION=str(localization)
        )
        for name in ("SteamAppId", "SteamGameId", "STS2_HEADLESS_QUIET"):
            environment.pop(name, None)
        self.stderr = (workspace / "stderr.log").open("wb")
        self.child = subprocess.Popen(
            [str(node), str(self.root / "scripts" / script)],
            cwd=self.root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            env=environment,
            start_new_session=True,
        )
        self.buffer = bytearray()
        self.sequence = 0
        self.closed = False
        self.last_cpu_seconds = 0.0
        try:
            self.identity = self.request("initialize", spec=spec, timeout=25)
            atomic_json(workspace / "identity.json", self.identity)
        except BaseException:
            self.stop()
            raise

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if self.closed or self.child.stdin is None or self.child.stdout is None:
            raise ValueError("Native worker is closed")
        self.sequence += 1
        payload = {"request_id": self.sequence, "command": command, **values}
        self.child.stdin.write((json.dumps(payload) + "\n").encode())
        self.child.stdin.flush()
        deadline = time.monotonic() + timeout
        while b"\n" not in self.buffer:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([self.child.stdout], [], [], max(0, left))[0]:
                raise TimeoutError("Native worker response cap; action will not be retried")
            chunk = os.read(self.child.stdout.fileno(), 65536)
            if not chunk:
                raise ValueError("Native worker exited before its response")
            self.buffer.extend(chunk)
            if len(self.buffer) > 16_000_000:
                raise ValueError("Native worker response exceeded its memory bound")
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        response = json.loads(line)
        if response.get("request_id") != self.sequence or response.get("ok") is not True:
            raise ValueError(f"Native worker failed: {response.get('error', 'response mismatch')}")
        value = dict(response["value"])
        if "usage" in value:
            usage = value["usage"]
            cpu = usage["native_cpu_seconds"] + usage["node_cpu_seconds"]
            if not isinstance(cpu, (int, float)) or cpu < self.last_cpu_seconds:
                raise ValueError("Native worker CPU counters regressed")
            self.last_cpu_seconds = cpu
        return value

    def cpu_seconds(self) -> float:
        return self.last_cpu_seconds

    def episode(
        self,
        seed: str,
        *,
        maximum_decisions: int,
        wall_seconds: float,
        cpu_seconds: float,
        chooser: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        started, thread_started, child_started = (
            time.monotonic(),
            time.thread_time(),
            self.cpu_seconds(),
        )
        decisions: list[dict[str, Any]] = []
        maximum_floor = maximum_act = 0
        families: dict[str, int] = {}
        liveness = _EpisodeLiveness()
        result: dict[str, Any] = {
            "schema_version": "actual-engine-episode-v1",
            "seed": seed,
            "status": "incomplete",
            "victory": False,
            "privileged_fixture": False,
            "recovered": False,
            "decisions": decisions,
            "liveness_policy": dict(LIVENESS_POLICY),
        }
        used = 0.0
        try:
            current = self.request("mount", seed=seed, timeout=min(25, wall_seconds))
            result["private_start_identity"] = current["private_start_identity"]
            result["reset"] = current["reset"]
            result["native_process_id"] = current["native_process_id"]
            while True:
                elapsed = time.monotonic() - started
                used = self.cpu_seconds() - child_started + time.thread_time() - thread_started
                facts = current["facts"]
                maximum_floor = max(maximum_floor, facts["floor"])
                maximum_act = max(maximum_act, facts["act"])
                kind = current["model_input"]["context"]["interaction"]["kind"]
                families[kind] = families.get(kind, 0) + 1
                if elapsed > wall_seconds or used > cpu_seconds:
                    raise TimeoutError("Whole-episode wall/CPU cap")
                if facts["terminal"]:
                    result.update(self.request("ending", timeout=min(15, wall_seconds - elapsed)))
                    result.update(status="terminal", victory=facts["victory"])
                    result["terminal_public_key"] = current["public_key"]
                    break
                if len(decisions) >= maximum_decisions:
                    raise ValueError("Whole-episode decision cap")
                key = current["public_key"]
                liveness.observe(key)
                inference_started = time.thread_time()
                choice = (
                    chooser(current["model_input"])
                    if chooser is not None
                    else {"action_index": current["default_action_index"]}
                )
                inference_cpu = time.thread_time() - inference_started
                action = choice.get("action_index")
                if type(action) is not int or not 0 <= action < len(
                    current["model_input"]["candidates"]
                ):
                    raise ValueError("Player returned an unadvertised action")
                decisions.append(
                    {
                        "public_input": current["model_input"],
                        "public_key": key,
                        "choice": choice,
                        "inference_cpu_seconds": inference_cpu,
                    }
                )
                elapsed = time.monotonic() - started
                used = self.cpu_seconds() - child_started + time.thread_time() - thread_started
                if elapsed >= wall_seconds or used > cpu_seconds:
                    raise TimeoutError("Whole-episode cap before action delivery")
                current = self.request(
                    "step",
                    snapshot_id=current["snapshot"]["snapshot_id"],
                    action_index=action,
                    timeout=min(20, wall_seconds - elapsed),
                )
        except (ValueError, TimeoutError, OSError) as error:
            result.update(status="failed", error=str(error))
            # The caller must retire this worker. An unknown state/delivery is not training data.
            self.stop()
        result.update(
            maximum_floor=maximum_floor,
            maximum_act=maximum_act,
            completed_acts=3 if result["victory"] else max(0, maximum_act - 1),
            families=families,
            wall_seconds=time.monotonic() - started,
            cpu_seconds=self.cpu_seconds() - child_started + time.thread_time() - thread_started,
            inference_cpu_seconds=sum(d["inference_cpu_seconds"] for d in decisions),
            game_apps_created=0,
        )
        return result

    def close(self) -> dict[str, Any]:
        try:
            result = self.request("close", timeout=15)
            self.child.wait(timeout=5)
            if result.get("clean_exit") is not True or self.child.returncode != 0:
                raise ValueError("Native worker did not close cleanly")
            atomic_json(self.workspace / "closed.json", result)
            self.marker.unlink()
            return result
        finally:
            self.stop()

    def retire(self, reason: str) -> dict[str, Any]:
        """Prove shutdown before a caller starts a fresh worker for a different seed."""
        self.stop()
        native = json.loads((self.workspace / "native-process-stop.json").read_text())
        native_pid = self.identity["runtime_identity"]["process_id"]
        for pid in (self.child.pid, native_pid):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            raise ValueError("Failed worker process still exists; no successor worker allowed")
        if native["process_id"] != native_pid or self.child.poll() is None:
            raise ValueError("Failed worker shutdown identity differs")
        result = {
            "schema_version": "actual-engine-worker-retirement-v1",
            "controller_process_id": self.child.pid,
            "native_process_id": native_pid,
            "controller_process_stopped": True,
            "native_process_stopped": True,
            "reason": reason,
            "workspace_reusable": False,
            "failed_seed_retried": False,
        }
        atomic_json(self.workspace / "retired.json", result)
        return result

    def stop(self) -> None:
        if not self.closed:
            try:
                # EOF lets the Node finally block stop its separately owned native child.
                if self.child.stdin is not None and not self.child.stdin.closed:
                    self.child.stdin.close()
                try:
                    self.child.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    _stop_child(self.child)
            finally:
                self.stderr.close()
                self.closed = True
