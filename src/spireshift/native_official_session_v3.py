"""One bounded official-game checkpoint prefix, using the existing locked shared app."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import (
    _available_port,
    _copy_disposable_game_file,
    _enable_mod_settings,
    _settings_template,
    _stop_child,
    connector_sandbox,
)
from spireshift.engine_native import (
    EXE_RELATIVE,
    _no_symlinks,
    _profile_override,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_qualification import (
    ARCHIVE_RECORD,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.engine_working_app import lease_working_app, preflight_working_app
from spireshift.full_run_experience import atomic_json
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shared_transport import JsonLines


def finish_client(client: JsonLines, child: subprocess.Popen[bytes], deadline: float) -> str | None:
    """A blocked SDK client can still request a proven clean game shutdown."""
    error = None
    try:
        client.close()
    except ValueError as failure:
        error = str(failure)
    # Do not skip this wait merely because the client rejected an input/choice.
    # The existing child-exit, inventory and lease-reset checks still must pass.
    child.wait(timeout=max(0.1, deadline - time.monotonic()))
    return error


def official_prefix(
    context: dict[str, Any],
    case: dict[str, Any],
    attempt: Path,
    policy: LivePolicy,
    deadline: float,
) -> dict[str, Any]:
    q, config, native = (context[k] for k in ("qualification", "connector", "native"))
    if _running_games():
        raise ValueError("Close the game before a live checkpoint prefix")
    preflight_working_app(context["working_app"])
    attempt.mkdir(parents=True, exist_ok=False)
    atomic_json(attempt / "in-progress.json", {"seed": case["seed"], "training_allowed": False})
    archive = native["archive"]
    archive_record = json.loads((archive / ARCHIVE_RECORD).read_text())
    template, _ = _settings_template(config)
    user_data = Path.home() / "Library/Application Support"
    shared = user_data / "SlayTheSpire2"
    before = _shared_snapshot(shared)
    with lease_working_app(
        context["working_app"], archive, attempt, copy_file=_copy_disposable_game_file
    ) as lease:
        game = lease.game
        if _inventory(game) != archive_record["inventory"]:
            raise ValueError("Shared official app differs from its frozen baseline")
        executable = game / EXE_RELATIVE
        executable.chmod(stat.S_IMODE(executable.stat().st_mode) | 0o111)
        suffix = manifest_identifier({"attempt": str(attempt)})[7:23]
        name = f"SpireShift/engine-profiles/live-{suffix}"
        profile = user_data / name
        _no_symlinks(profile)
        profile.mkdir(parents=True, exist_ok=False)
        settings = profile / "default/1/settings.save"
        settings.parent.mkdir(parents=True)
        shutil.copy2(template, settings)
        consent = _enable_mod_settings(settings, config.native.document["settings_schema"])
        saves = profile / "default/1/modded/profile1/saves"
        saves.mkdir(parents=True)
        shutil.copy2(context["progress"], saves / "progress.save")
        (executable.parent / "override.cfg").write_text(_profile_override(name))
        installed = subprocess.run(
            [context["config"]["node"], str(q.root / "scripts/engine-menu-probe.mjs"), "--install"],
            input=json.dumps(
                {
                    "toolchain": str(config.private("toolchain")),
                    "game": str(game),
                    "attempt": str(attempt),
                }
            ),
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        atomic_json(attempt / "installation.json", json.loads(installed.stdout))
        host_settings = executable.parent / "mods/STS2_MCP.conf"
        if host_settings.exists():
            raise ValueError("Shared app unexpectedly contains old Host settings")
        host_settings.write_text(
            '{"port":15526,"player_environment_native_page_evidence_enabled":false}'
        )
        expected = _inventory(game)
        port = _available_port()
        sandbox = attempt / "profile-isolation.sb"
        sandbox.write_text(
            connector_sandbox(
                [
                    shared,
                    user_data / "Godot/app_userdata/SlayTheSpire2",
                    archive.parent,
                    user_data / "Steam/steamapps",
                    user_data / "Steam/userdata",
                ],
                port,
            )
        )
        subprocess.run(
            ["/usr/bin/sandbox-exec", "-f", str(sandbox), "/usr/bin/true"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        token = secrets.token_hex(32)
        environment = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("STS2_CONNECTOR_") and k not in {"SteamAppId", "SteamGameId"}
        }
        environment.update(
            STS2_CONNECTOR_PORT=str(port),
            STS2_CONNECTOR_HOST_CONTROL_TOKEN=token,
            STS2_CONNECTOR_EXPERIMENTAL_SOURCE_REVISION=config.document["connector"][
                "source_revision"
            ],
            STS2_CONNECTOR_RUN_SEED=case["seed"],
        )
        command = [
            "/usr/bin/sandbox-exec",
            "-f",
            str(sandbox),
            str(executable),
            "--headless",
            "--verbose",
            "--force-steam=off",
            "--clientId=1",
            "--max-fps",
            "60",
            "--log-file",
            str(attempt / "godot.log"),
        ]
        client = None
        result: dict[str, Any] = {}
        forced = False
        error = None
        maximum_cpu, started_cpu = 0.0, time.thread_time()
        with (attempt / "stdout.log").open("xb") as out, (attempt / "stderr.log").open("xb") as err:
            child = subprocess.Popen(
                command,
                cwd=executable.parent,
                env=environment,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
            try:
                client = JsonLines(
                    q.root,
                    [
                        context["config"]["node"],
                        str(q.root / "scripts/engine-live-checkpoint-v3.mjs"),
                    ],
                    attempt / "client-stderr.log",
                )
                client.send(
                    {
                        "toolchain": str(config.private("toolchain")),
                        "attempt": str(attempt),
                        "expected_pid": child.pid,
                        "endpoint": f"http://127.0.0.1:{port}",
                        "host_control_token": token,
                        "target": q.target,
                        "connector": config.document["connector"],
                        "max_wall_seconds": max(1, deadline - time.monotonic() - 10),
                        "maximum_decisions": context["config"]["maximum_decisions"],
                    }
                )
                while time.monotonic() < deadline - 5:
                    cpu = time.thread_time() - started_cpu
                    for pid in (child.pid, client.child.pid):
                        try:
                            times = psutil.Process(pid).cpu_times()
                            cpu += times.user + times.system
                        except psutil.NoSuchProcess:
                            pass
                    maximum_cpu = max(maximum_cpu, cpu)
                    if maximum_cpu > 128:
                        raise TimeoutError("Official checkpoint whole-run CPU cap")
                    try:
                        message = client.receive(min(deadline - 5, time.monotonic() + 1))
                    except TimeoutError:
                        continue  # Read the same pending reply; never resubmit an action.
                    if message.get("kind") == "policy_observation":
                        try:
                            choice = policy.choose(message["frame"])
                        except (ValueError, KeyError, TypeError) as rejected:
                            error = f"Checkpoint input rejected: {rejected}"
                            # This is a control cancellation, never a fallback
                            # gameplay action or retry. The SDK client records
                            # the rejection and requests shutdown in its finally.
                            client.send({"command": "abort"})
                        else:
                            client.send({"command": "choose", **choice})
                    elif message.get("kind") == "delivered":
                        policy.acknowledge(message["acknowledgement"])
                    elif message.get("kind") == "complete":
                        result = message["result"]
                        break
                    else:
                        raise ValueError("Unclassified official checkpoint protocol message")
                if not result:
                    raise TimeoutError("Official checkpoint wall cap; preserve unfinished evidence")
                close_error = finish_client(client, child, deadline)
                error = error or close_error
            except (ValueError, OSError, TimeoutError, subprocess.TimeoutExpired) as failure:
                error = str(failure)
            finally:
                forced = child.poll() is None
                if client is not None:
                    client.stop()
                _stop_child(child)
        stdout = (attempt / "stdout.log").read_text(errors="replace")
        checks = {
            "profile_path_logged": f"User Data Directory: {profile}\n" in stdout,
            "Steam_disabled_observed": "Steam initialization skipped" in stdout,
            "personal_profile_unchanged": before == _shared_snapshot(shared),
            "working_app_unchanged": _inventory(game) == expected,
            "frozen_archive_unchanged": verify_game_archive(q, archive)["valid"],
            "settings_template_unchanged": _sha_file(template)
            == config.document["bootstrap_settings_sha256"],
            "natural_shutdown": child.returncode == 0
            and not forced
            and result.get("shutdown_requested") is True,
            "exact_delivery_count": result.get("policy_decisions") == policy.decisions,
        }
        # Even a blocked prefix may release the app only after proven clean shutdown
        # and exact reset. A contaminated app remains locked for explicit inspection.
        if not all(
            checks[k]
            for k in ("working_app_unchanged", "frozen_archive_unchanged", "natural_shutdown")
        ):
            atomic_json(
                attempt / "failure.json", {"error": error or result.get("error"), "checks": checks}
            )
            raise ValueError(
                "Official worker shutdown/integrity unverified; preserve its active lease"
            )
        reset = lease.restore(expected)
        body = {
            "status": "official_prefix_pass"
            if all(checks.values())
            and not error
            and result.get("status") == "official_checkpoint_prefix_complete"
            else "official_prefix_blocked",
            "checks": checks,
            "probe": result,
            "error": error,
            "cpu_seconds": maximum_cpu,
            "working_app": reset,
            "profile": str(profile),
            "settings_consent": consent,
            "optimizer_updates": 0,
            "full_game_evaluation": False,
        }
        body["report_id"] = manifest_identifier(body)
        atomic_json(attempt / "report.json", body)
        (attempt / "in-progress.json").rename(attempt / "complete.json")
        return body
