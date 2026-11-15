"""Materialize, verify and play training-only later-act native saves."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host, native_a8_own_experience, native_win4_game
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.full_run_experience import atomic_json
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_head_policy import HeadChooser, HeadModel, HeadState
from spireshift.native_a8_own_policy import CONTRACT, OwnPolicy
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_compatibility_contract import verified
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines
from spireshift.native_systematic_selectors_v2 import CONVERTER, SelectorBridge
from spireshift.native_win4_plan import AnswerPolicy

SCRIPT = "engine-a8-prepared-start-worker-v1.mjs"
KIND = "native_a8_later_act_start_v1"
PROJECT = Path("mod/SpireShift.HeadlessPreparedStart")
SDK_PROOF = "artifacts/native-entry-text-repair/native-build-v56/report.json"


def build_adapter(root: Path, candidate: Path, out: Path) -> dict[str, Any]:
    toolchain = identified(root / SDK_PROOF)["build"]["toolchain"]
    sdk = toolchain["sdk_version"]
    if subprocess.check_output(["dotnet", "--version"], text=True, timeout=10).strip() != sdk:
        raise ValueError("The pinned compiler SDK changed")
    sdks = subprocess.check_output(["dotnet", "--list-sdks"], text=True, timeout=10)
    directory = next(
        line.split(" [", 1)[1].rstrip("]")
        for line in sdks.splitlines()
        if line.startswith(sdk + " [")
    )
    if _sha_file(Path(directory) / sdk / "Roslyn/bincore/csc.dll") != toolchain["csc_sha256"]:
        raise ValueError("The pinned compiler bytes changed")
    out.mkdir(parents=True, exist_ok=False)
    builds = []
    for label in ("build", "independent-build"):
        with (out / f"{label}.log").open("xb") as log:
            subprocess.run(
                [
                    "dotnet",
                    "build",
                    str(PROJECT / f"{PROJECT.name}.csproj"),
                    "-c",
                    "Release",
                    "--disable-build-servers",
                    "-v:q",
                    "--artifacts-path",
                    str(out / label),
                    f"-p:CandidateDirectory={candidate}",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=root,
                timeout=45,
                check=True,
            )
        (assembly,) = (out / label / "bin").rglob(f"{PROJECT.name}.dll")
        builds.append({"path": str(assembly.relative_to(root)), "sha256": _sha_file(assembly)})
    if builds[0]["sha256"] != builds[1]["sha256"]:
        raise ValueError("The prepared-start hook builds differ")
    return native_win4_game.write(
        out / "report.json",
        {
            "status": "prepared_start_adapter_built",
            "builds": builds,
            "sources": {
                str(p.relative_to(root)): _sha_file(p) for p in (root / PROJECT).glob("*.*")
            },
        },
    )


class PreparedWorker(FeedbackWorker):
    def __init__(self, context: dict[str, Any], target: Path, *, diagnostic: bool = False) -> None:
        self.prepared_adapter = context["prepared_start_adapter"]
        self.diagnostic = diagnostic
        with patch.multiple(native_a8_feedback_host, SCRIPT=SCRIPT, PROJECTION=KIND):
            super().__init__(context, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {
                **values["spec"],
                "prepared_start_adapter": self.prepared_adapter,
                "prepared_diagnostic": self.diagnostic,
            }
        return super().request(command, timeout=timeout, **values)


def complete_history(save: dict[str, Any], case: dict[str, Any], seed: str) -> int:
    """Restore the generated Ancient's identity in a constructed pre-boss prefix."""
    index = case["act"] - 1
    act = save["acts"][index]
    coords, history = save["visited_map_coords"], save["map_point_history"]
    (player,) = save["players"]
    if (
        index not in (1, 2)
        or save["current_act_index"] != index
        or save["ascension"] != 8
        or save["rng"]["seed"] != seed
        or player["character_id"] != "CHARACTER.IRONCLAD"
        or act["id"] != f"ACT.{case['act_definition']}"
        or save["pre_finished_room"] is not None
        or len(history) != index + 1
        or any(history[:index])
    ):
        raise ValueError("Require the exact constructed Ironclad/A8 later-act save")
    if case["entry"] == "act_start":
        if coords or history[index]:
            raise ValueError("An act entry must start before any current-act path")
        return 0
    if case["entry"] != "preboss" or len(coords) < 2 or len(history[index]) != len(coords) - 1:
        raise ValueError("The declared pre-boss start has an invalid native path")
    native_map = act["saved_map"]
    points = {
        (point["coord"]["col"], point["coord"]["row"]): point
        for point in [native_map["start"], *native_map["points"], native_map["boss"]]
    }
    path = [points[coord["col"], coord["row"]] for coord in coords]
    if (
        path[0] != native_map["start"]
        or path[-1]["type"] != "rest_site"
        or any(
            right["coord"] not in left["children"]
            for left, right in zip(path[:-1], path[1:], strict=True)
        )
    ):
        raise ValueError("The constructed history must follow the native map")
    ancient = act["rooms"]["ancient_id"]
    if not isinstance(ancient, str) or not re.fullmatch(r"EVENT\.[A-Z_0-9]+", ancient):
        raise ValueError("Require the native generated Ancient for saved-run scoring")
    repaired = 0
    for point, entry in zip(path[:-1], history[index], strict=True):
        if (
            entry["map_point_type"] != point["type"]
            or [p["player_id"] for p in entry["player_stats"]] != [player["net_id"]]
            or entry["rooms"] != []
        ):
            raise ValueError("A constructed prefix has unexpected history or player ownership")
        if point["type"] == "ancient":
            # This is serialization metadata for the skipped room. No choice or
            # progress outcome is assigned to the constructed prefix.
            entry["rooms"] = [{"room_type": "event", "model_id": ancient, "turns_taken": 0}]
            repaired += 1
    if repaired != 1:
        raise ValueError("A prepared pre-boss prefix must contain one native Ancient")
    return repaired


def materialize(
    context: dict[str, Any],
    case: dict[str, Any],
    target: Path,
    deadline: float,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    root = context["qualification"].root
    if previous is None:
        setup = target / "setup"
        setup.mkdir()
        source = native_win4_game.prepare(context, case, setup, deadline)
    else:
        path = root / previous["source_chunk"]
        seal = identified(path / "done.json")
        source = identified(path / "start.json")
        if (
            seal["report_id"] != previous["seal_id"]
            or seal["sources"][str((path / "start.json").relative_to(root))]
            != _sha_file(path / "start.json")
            or source["seed"] != previous["seed"]
            or source["scenario"] != case
        ):
            raise ValueError("The previously verified start differs from the admitted bank")
    if (
        source["status"] != "ready"
        or source["evaluation_eligible"] is not False
        or source["natural_progress_claimed"] is not False
        or source["enemy_HP_or_energy_or_RNG_edited"] is not False
    ):
        raise ValueError("Require an outcome-blind native prepared start")
    original = verified(root, {"path": source["save_path"], "sha256": source["save_sha256"]})
    save = json.loads(original.read_text())
    repaired = complete_history(save, case, source["seed"])
    path = target / "start.save"
    atomic_json(path, save)
    return native_win4_game.write(
        target / "start.json",
        {
            "status": "ready",
            "kind": KIND,
            "scenario": case,
            "seed": source["seed"],
            "evaluation_eligible": False,
            "source_start_id": source["report_id"],
            "source_save_sha256": source["save_sha256"],
            "native_ancient_records_restored": repaired,
            "save_path": str(path.relative_to(root)),
            "save_sha256": _sha_file(path),
        },
    )


def check_start(frame: dict[str, Any], start: dict[str, Any], save: dict[str, Any]) -> None:
    public = frame["public_input"]["context"]
    player, run = (public["persistent"][key] for key in ("player", "run"))
    (native,) = save["players"]
    (deck,) = [row["content"]["cards"] for row in public["reads"] if row["kind"] == "run_deck"]
    if (
        run["ascension"] != 8
        or run["act"] != start["scenario"]["act"]
        or run["act_definition_id"] != start["scenario"]["act_definition"]
        or run["floor"] != len(save["visited_map_coords"])
        or player["character_definition_id"] != "IRONCLAD"
        or (player["hp"], player["max_hp"], player["gold"], player["max_potion_slots"])
        != (native["current_hp"], native["max_hp"], native["gold"], native["max_potion_slot_count"])
        or Counter((card["definition_id"], card["is_upgraded"]) for card in deck)
        != Counter(
            (card["id"].removeprefix("CARD."), card.get("current_upgrade_level", 0) > 0)
            for card in native["deck"]
        )
        or Counter(r["definition_id"] for r in player["relics"])
        != Counter(r["id"].removeprefix("RELIC.") for r in native["relics"])
        or Counter((p["definition_id"], p["slot"]) for p in player["potions"])
        != Counter((p["id"].removeprefix("POTION."), p["slot_index"]) for p in native["potions"])
        or [row["definition_id"] for row in run["bosses"]]
        != [save["acts"][run["act"] - 1]["rooms"]["boss_id"].removeprefix("ENCOUNTER.")]
        or frame["source_family"]
        != {"act_start": "map_navigation", "preboss": "rest_site"}[start["scenario"]["entry"]]
        or frame["terminal"]
    ):
        raise ValueError("The loaded native A8 inventory or current owner differs from its save")


def prepared_policy(
    context: dict[str, Any], start: dict[str, Any], variant: str, model: HeadModel
) -> AnswerPolicy:
    if (
        variant != KIND
        or start["kind"] != KIND
        or start["evaluation_eligible"] is not False
        or model.arm != "shared"
    ):
        raise ValueError("Only the shared model may play a declared training-only save")
    policy = OwnPolicy(model, context["score"], start["seed"])
    policy.chooser = HeadChooser(model, context["score"], start["seed"])
    return AnswerPolicy(policy)


def progress(path: Path, initial_act: int, initial_floor: int, won: bool) -> dict[str, int]:
    floors = {initial_act: initial_floor}
    for row in records(path):
        if row["kind"] not in {"policy_input", "final_observation"}:
            continue
        run = row["frame"]["public_input"]["context"]["persistent"]["run"]
        act, floor = run["act"], run["floor"]
        if not initial_act <= act <= 3 or act > max(floors) + 1:
            raise ValueError("A prepared game crossed an unobserved act")
        floors[act] = max(floor, floors.get(act, 0))
    return {
        "completed_acts": (4 if won else max(floors)) - initial_act,
        "maximum_floor": sum(floors.values()) - initial_floor,
        "maximum_act": max(floors),
    }


def play(
    context: dict[str, Any],
    task: dict[str, Any],
    start: dict[str, Any],
    target: Path,
    state: HeadState,
    deadline: float,
) -> dict[str, Any]:
    if (
        task["partition"] not in {"train", "control"}
        or task["start_act"] != start["scenario"]["act"]
    ):
        raise ValueError("A saved start can only enter its declared training stratum")
    root = context["qualification"].root
    path = verified(root, {"path": start["save_path"], "sha256": start["save_sha256"]})
    save = json.loads(path.read_text())
    recorded = native_win4_game.write(
        target / "start.json",
        {
            **{key: value for key, value in start.items() if key != "report_id"},
            "setup_id": start["report_id"],
        },
    )
    with patch.multiple(
        native_win4_game,
        worker=PreparedWorker,
        policy=prepared_policy,
        check_start=lambda frame, observed: check_start(frame, observed, save),
        JsonLines=SelectorBridge,
    ):
        episode = native_win4_game.episode(
            context, recorded, KIND, target, deadline, model=state.model
        )
    groups = native_a8_own_experience.groups(target, state.model.model_id)
    native_decisions, local_factors = 0, 0
    for group in groups:
        if any(choice["scoring_head"] != "shared" for _, choice in group):
            raise ValueError("A prepared game used another scoring head")
        native_decisions += 1
        local_factors += len(group) - 1
    if (
        episode["actual_deliveries_independently_verified"] != native_decisions
        or episode["local_answer_factors"] != local_factors
        or episode["full_run_win"] is not False
        or episode["seed"] != task["seed"]
    ):
        raise ValueError("The prepared trajectory has inconsistent delivery or scope")
    ending = episode["native_ending"]
    cpu = ending["usage"]["native_cpu_seconds"] if ending else None
    capped = episode["status"] == "capped" or (
        cpu is not None and cpu > context["score"].evaluation_objective.whole_run_budget
    )
    won = not capped and episode["curriculum_success"]
    if not capped and (
        not ending
        or episode["native_terminal"] is not True
        or ending["native_ending_evidence_agrees"] is not True
        or ending["private_final_identity"]["seed"] != task["seed"]
        or ending["private_final_identity"]["native_game_over"] is not True
        or ending["private_final_identity"]["native_victory_room"] != won
    ):
        raise ValueError("A prepared suffix must have a genuine native terminal outcome")
    return {
        "task": task,
        "setup_id": start["report_id"],
        "policy_contract": CONTRACT,
        "model_id": state.model.model_id,
        "episode_report_id": episode["report_id"],
        "initial_public_input_id": episode["initial_public_input_id"],
        "outcome": "capped" if capped else "win" if won else "loss",
        "prepared_suffix_victory": won,
        "native_cpu_seconds": cpu,
        "native_decisions": native_decisions,
        "local_answer_factors": local_factors,
        **progress(target / TRACE, task["start_act"], len(save["visited_map_coords"]), won),
    }


def crystal_control(
    context: dict[str, Any], start: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    root = context["qualification"].root
    save = verified(root, {"path": start["save_path"], "sha256": start["save_sha256"]})
    worker = PreparedWorker(context, target / "worker", diagnostic=True)
    try:
        worker.request("load", seed=start["seed"], save_json=save.read_text(), timeout=25)
        result = worker.request("crystal_diagnostic")

        def submit(index: int) -> None:
            nonlocal result
            snapshot = result["snapshot"]
            result = worker.request("step", snapshot_id=snapshot["snapshot_id"], action_index=index)
            if result["delivery_domain"] != "native":
                raise ValueError("Crystal Sphere requires an exact native delivery")

        def take(label: str) -> None:
            (index,) = [
                i
                for i, action in enumerate(result["snapshot"]["bound_actions"]["actions"])
                if action["label"] == label
            ]
            submit(index)

        take("Payment Plan")
        with_converter = JsonLines(
            root,
            [context["node"], str(root / "scripts" / CONVERTER)],
            target / "grid-converter.log",
        )
        try:
            frame = with_converter.project(result["snapshot"], result["reads"], None, deadline)
            with_converter.close()
        finally:
            with_converter.stop()
        candidates = frame["public_input"]["candidates"]
        labels = {action["label"] for action in candidates}
        grid = {
            f"{tool} at ({x},{y})"
            for tool in ("Small", "Big")
            for x in range(11)
            for y in range(11)
        }
        if not grid.issubset(labels):
            raise ValueError("A loaded game must expose all native Crystal Sphere bindings")
        for index, (x, y) in enumerate(((2, 2), (5, 2), (8, 2), (2, 5), (5, 5), (8, 5))):
            tool = "Big" if index % 2 else "Small"
            take(f"{tool} at ({x},{y})")
        for _ in range(20):
            snapshot = result["snapshot"]
            if snapshot["interaction"]["kind"] not in {"reward_claim", "card_reward_selection"}:
                break
            submit(result["default_action_index"])
        take("Proceed")
        if result["snapshot"]["interaction"]["kind"] != "map_navigation":
            raise ValueError("The saved-start Crystal Sphere reward must return to the map")
        shutdown = worker.close()
        if shutdown["clean_exit"] is not True:
            raise ValueError("Saved-start grid diagnostic did not shut down cleanly")
    finally:
        worker.stop()
    return {
        "native_grid_bindings": len(grid),
        "other_current_bindings": len(candidates) - len(grid),
        "returned_to_map": True,
        "diagnostic_only": True,
        "clean_exit": True,
    }


def setup_helpers(root: Path) -> set[str]:
    from spireshift.native_win4_worker import SCRIPT as SETUP_SCRIPT

    return {
        f"scripts/{name}"
        for script in (SCRIPT, SETUP_SCRIPT, CONVERTER)
        for name in worker_helpers(root, script)
    }
