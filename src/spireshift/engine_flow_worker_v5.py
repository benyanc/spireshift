"""Version 12 constructor: exact selection worker isolation, with public combat relic counters.

The historical constructor, worker, helpers and support-code cache stay unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import DATA_RELATIVE, _private_path, _sandbox
from spireshift.engine_projection_cache import prepare_projection_cache
from spireshift.engine_qualification import GAME_RELATIVE, EngineQualificationConfig
from spireshift.engine_worker import ISOLATION_ID, EngineWorker, worker_helpers
from spireshift.full_run_experience import atomic_json

SCRIPT = "engine-native-worker-v19.mjs"
PROTOCOL = "atomic_public_card_choice_v1"


class RelicWorker(EngineWorker):
    def __init__(
        self,
        qualification: EngineQualificationConfig,
        inputs: dict[str, Any],
        workspace: Path,
        node: Path,
        helpers: dict[str, str],
        *,
        script: str = SCRIPT,
        projection_cache: Path | None = None,
    ) -> None:
        self.root, self.workspace, self.inputs = qualification.root, workspace, inputs
        _private_path(self.root, str(workspace.relative_to(self.root)))
        if script != SCRIPT or projection_cache is not None:
            raise ValueError("Use the separately qualified relic-observation worker")
        if helpers != worker_helpers(self.root, script):
            raise ValueError("Native worker helper inventory changed")
        headless = next(x for x in qualification.document["sources"] if x["name"] == "headless")
        shared_projection = prepare_projection_cache(
            self.root, _private_path(self.root, headless["path"]), inputs["projection"]
        )
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
            *([Path(shared_projection["directory"])] if shared_projection is not None else []),
        ]
        (workspace / "profile-isolation.sb").write_text(
            _sandbox(denied)
            + "(deny file-read* file-write* (require-all "
            + f"(subpath {json.dumps(str(workspace.parent))}) "
            + f"(require-not (subpath {json.dumps(str(workspace))}))))\n"
        )
        (profile / "tmp").mkdir()
        spec = {
            "shared_projection": shared_projection,
            "projection_cache": str(projection_cache) if projection_cache is not None else None,
            "coverage_diagnostic": False,
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
                {
                    "input_config_id": inputs["recipe"]["input_config_id"],
                    "isolation": ISOLATION_ID,
                    "selection_protocol": PROTOCOL,
                    "inventory_observation_contract": "public_owned_combat_relic_counters_v1",
                }
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
