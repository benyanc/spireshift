"""Extract verified normal-start Act 1 clears from training-only native runs."""

from __future__ import annotations

import fcntl
import gzip
import json
import time
from collections import Counter, defaultdict
from collections.abc import Generator, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift import native_a8_head_grid_resume as grid
from spireshift import native_a8_head_study as heads
from spireshift import native_a8_later_merchant_resume as later
from spireshift import native_a8_later_training as original
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_own_experience import FrameChoice, groups
from spireshift.native_a8_own_policy import CONTRACT
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_rescue_game import public_state, receipt
from spireshift.native_a8_reward_exit import check_delivery
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

AREA = "artifacts/native-a8-act1-success-replay"
STATUS = "normal_start_act1_training_bank_verified"


def reference(root: Path, path: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha_file(path)}


@contextmanager
def completed_study(root: Path) -> Iterator[tuple[later.Study, dict[str, Any]]]:
    recipe = json.loads((root / later.RECIPE).read_text())
    if recipe["implementation"] != later.implementation(root):
        raise ValueError("Require the frozen merchant-map worker and continuation sources")
    with later.admitted(root, recipe) as (study, control):
        store = study.store(False)
        with (store.workspace / "session.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            report = identified(store.workspace / "report.json")
            if (
                report["status"] != original.COMPLETE
                or report["config_id"] != store.config_id
                or report["control_id"] != control
                or report["stop"] is not None
                or report["frozen_checks"] != study.recovery.original.source.study.frozen_checks
                or json.loads((store.workspace / "config-at-launch.json").read_text()) != recipe
            ):
                raise ValueError("Require the completed shared-head later-act comparison")
            yield study, report


@dataclass(frozen=True)
class Source:
    store: ChunkJournal
    key: str
    seal: dict[str, Any]

    @property
    def game(self) -> dict[str, Any]:
        value: dict[str, Any] = self.seal["result"]
        return value

    @property
    def seed(self) -> str:
        return str(self.game["task"]["seed"])

    @property
    def order(self) -> tuple[bool, int, str]:
        task = self.game["task"]
        return task["arm"] != "shared", int(task["player"]), self.key


def candidate_sources(study: later.Study) -> dict[str, list[Source]]:
    head_worlds = heads.world_schedule()
    allowed_heads = set(head_worlds["train"]) - {grid.EXCLUDED} | {grid.REPLACEMENT}
    later_worlds = {w["seed"] for batch in study.worlds["training"] for w in batch if w["act"] == 1}
    out: dict[str, list[Source]] = defaultdict(list)
    previous = study.preceding.store(False)
    stores = (
        (study.recovery.history, allowed_heads),
        (ChunkJournal(study.recovery.root, study.recovery.cfg), allowed_heads),
        (study.preceding.history, later_worlds),
        (ChunkJournal(previous.root, previous.recipe), later_worlds),
        (ChunkJournal(study.recovery.root, study.resume), later_worlds),
    )
    for store, allowed in stores:
        for path in sorted((store.workspace / "chunks").glob("*/done.json")):
            header = json.loads(path.read_text())
            row = header["result"]
            task = row.get("task", {})
            if (
                task.get("partition") == "train"
                and task.get("start_act", 1) == 1
                and task.get("seed") in allowed
                and row["outcome"] in {"win", "loss"}
                and row["completed_acts"] >= 1
            ):
                key = str(task["key"])
                if path != store.path(key) / "done.json":
                    raise ValueError("Training game key differs from its sealed path")
                out[task["seed"]].append(Source(store, key, identified(path)))
    return out


def verify_game(source: Source, whole_run_budget: float) -> Path:
    target = source.store.path(source.key)
    start, episode = (identified(target / name) for name in ("start.json", "report.json"))
    game = source.game
    task, ending = game["task"], episode["native_ending"]
    request = json.loads((target / "active.json").read_text())["request"]
    identity = ending["private_final_identity"]
    won = game["outcome"] == "win"
    if (
        source.store.completed(source.key, request) != source.seal
        or set(request) != {"task", "behavior_state_id", "model_id"}
        or request["task"] != task
        or request["model_id"] != game["model_id"]
        or start["scenario"] != task
        or start["seed"] != source.seed
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or start["evaluation_eligible"] is not False
        or episode["start_id"] != start["report_id"]
        or episode["report_id"] != game["episode_report_id"]
        or episode["status"] != "complete"
        or episode["model_id"] != game["model_id"]
        or episode["native_terminal"] is not True
        or episode["full_run_win"] is not won
        or episode["actual_deliveries_independently_verified"] != game["native_decisions"]
        or episode["local_answer_factors"] != game["local_answer_factors"]
        or episode["initial_public_input_id"] != game["initial_public_input_id"]
        or episode["student_inputs_public_only"] is not True
        or game["policy_contract"] != CONTRACT
        or ending["native_ending_evidence_agrees"] is not True
        or ending["usage"]["native_cpu_seconds"] != game["native_cpu_seconds"]
        or not 0 <= game["native_cpu_seconds"] <= whole_run_budget
        or identity["seed"] != source.seed
        or identity["ascension"] != 8
        or identity["started_with_neow"] is not True
        or identity["native_abandoned"] is not False
        or identity["native_victory_room"] is not won
        or not (identity["native_game_over"] or identity["native_player_dead"])
        or episode["shutdown"]["clean_exit"] is not True
        or episode["shutdown"]["runtime_errors"]
    ):
        raise ValueError(f"Training source has no sealed normal-start terminal proof: {source.key}")
    return target


def verify_native_exit(
    path: Path,
    index: int,
    seed: str,
    floor: int,
    hp: int,
) -> None:
    """Use the actual boss Proceed and its native Act 2 response."""
    started = 0
    actions = 0
    before: dict[str, Any] = {}
    for row in records(path):
        request, state = row["request"], row["response"]
        if request["cmd"] == "start_run":
            if started or request.get("seed") != seed or state["context"]["act"] != 1:
                raise ValueError("Expected a single native Neow start")
            started += 1
        elif request["cmd"] in {"load_save", "reset_run"}:
            raise ValueError("A saved or reset run cannot supply a normal opening")
        elif request["cmd"] == "action":
            if not started:
                raise ValueError("Native action occurred before starting the world")
            if actions == index:
                room = before.get("room_ref")
                if (
                    row.get("transport") is not None
                    or before.get("decision") not in {"reward_set", "combat_rewards_complete"}
                    or before.get("is_boss") is not True
                    or not room
                    or request != {"cmd": "action", "action": "proceed", "args": {"room_ref": room}}
                    or before["context"]["act"] != 1
                    or before["context"]["total_floor"] != floor
                    or state.get("decision") != "map_select"
                    or state["context"]["act"] != 2
                    or state["player"]["hp"] != hp
                ):
                    raise ValueError("Act 2 entry must follow the current native boss reward exit")
                return
            actions += 1
        if state.get("type") == "decision":
            before = state
    raise ValueError("Missing the exact native Act 2 transition")


def export_prefix(source: Source, output: Path, budget: float, deadline: float) -> dict[str, Any]:
    directory = verify_game(source, budget)
    worker = directory / "worker"
    index = native = 0
    boss: str | None = None
    last: tuple[dict[str, Any], dict[str, Any]] | None = None
    families: Counter[str] = Counter()
    entry: dict[str, Any] | None = None
    with (
        closing(
            cast(Generator[list[FrameChoice]], groups(directory, source.game["model_id"]))
        ) as answers,
        closing(
            cast(Generator[dict[str, Any]], records(worker / "public-receipts.jsonl.gz"))
        ) as receipts,
        closing(
            cast(Generator[dict[str, Any]], records(worker / "answer-plan-deliveries.jsonl.gz"))
        ) as domains,
        gzip.open(output, "xt", encoding="utf-8", compresslevel=3) as stream,
    ):
        for group in answers:
            if time.monotonic() >= deadline:
                raise TimeoutError("Saved Act 1 source audit reached its time limit")
            frame = group[0][0]
            run, player, owner = public_state(frame)
            if index == 0 and (
                run["act"] != 1
                or run["floor"] > 1
                or run["ascension"] != 8
                or player["character_definition_id"] != "IRONCLAD"
                or manifest_identifier(frame["public_input"])
                != source.game["initial_public_input_id"]
            ):
                raise ValueError("The normal-start public observation differs from its seal")
            if run["act"] == 2:
                if last is None or boss is None or frame["terminal"] or player["hp"] <= 0:
                    raise ValueError("Act 2 requires a living native success")
                before, choice = last
                prior, _, interaction = public_state(before)
                accepted = receipt(before, choice, "native", frame["observation"]["snapshot_id"])
                if (
                    prior["act"] != 1
                    or interaction["kind"] != "reward_claim"
                    or owner["kind"] != "map_navigation"
                    or frame["observation"]["runtime_instance_id"]
                    != accepted["runtime_instance_id"]
                ):
                    raise ValueError("The clear must end at the native reward-to-map transition")
                verify_native_exit(
                    worker / "private-transcript.jsonl.gz",
                    index - 1,
                    source.seed,
                    prior["floor"],
                    player["hp"],
                )
                entry = {
                    "seed": source.seed,
                    "key": source.key,
                    "seal_id": source.seal["report_id"],
                    "source": reference(source.store.root, directory / "done.json"),
                    "act1_boss": boss,
                    "entry_hp": player["hp"],
                    "native_answers": native,
                    "local_factors": index - native,
                    "choice_bearing_answers": sum(families.values()),
                    "label_families": dict(families),
                }
                break
            if run["act"] != 1 or frame["terminal"]:
                raise ValueError("A later observation cannot become an Act 1 label")
            if owner["content"].get("context", {}).get("encounter_type") == "boss":
                (current,) = run["bosses"]
                boss = current["definition_id"]
            factors = []
            family = owner["kind"]
            for frame, choice in group:
                if (public_state(frame)[0]["act"], public_state(frame)[2]["kind"]) != (1, family):
                    raise ValueError("A composed answer must stay in its current Act 1 owner")
                actual, domain = next(receipts), next(domains)
                accepted = receipt(
                    frame, choice, domain["delivery_domain"], actual["successor_snapshot_id"]
                )
                check_delivery(actual, domain, accepted, index)
                if (
                    choice["public_input_id"] != manifest_identifier(frame["public_input"])
                    or choice["bound_action_id"] != accepted["bound_action_id"]
                ):
                    raise ValueError("The native receipt differs from the sampled public choice")
                index += 1
                factors.append(
                    {"public_input": frame["public_input"], "action_index": choice["action_index"]}
                )
                last = frame, choice
            native += 1
            if any(len(factor["public_input"]["candidates"]) > 1 for factor in factors):
                stream.write(json.dumps({"act": 1, "family": family, "factors": factors}) + "\n")
                families[family] += 1
    if entry is None:
        raise ValueError("The saved normal start did not reach Act 2")
    return {**entry, "labels": reference(source.store.root, output)}


def partitions(rows: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    bosses: dict[str, list[str]] = defaultdict(list)
    for seed, row in rows.items():
        bosses[row["act1_boss"]].append(seed)
    if len(bosses) != 6 or any(len(seeds) < 4 for seeds in bosses.values()):
        raise ValueError("Require repeated normal-start clears across all six Act 1 bosses")
    held = {
        seed for seeds in bosses.values() for seed in sorted(seeds, key=manifest_identifier)[:2]
    }
    return {"fit": sorted(rows.keys() - held), "fit_holdout": sorted(held)}


def build(root: Path, deadline: float, output: str = f"{AREA}/bank-v1") -> dict[str, Any]:
    with completed_study(root) as (study, completed):
        sources = candidate_sources(study)
        work = _private_path(root, output)
        work.mkdir(parents=True, exist_ok=False)
        score = study.ctx["score"]
        rows = {
            seed: export_prefix(
                min(choices, key=lambda source: source.order),
                work / f"world-{number:02d}.jsonl.gz",
                score.evaluation_objective.whole_run_budget,
                deadline,
            )
            for number, (seed, choices) in enumerate(sorted(sources.items()), 1)
        }
        scope = partitions(rows)
        study.unchanged(_shared_snapshot(Path.home() / SHARED_PROFILE))
        return write(
            work / "report.json",
            {
                "schema_version": "native-a8-act1-success-replay-bank-v1",
                "status": STATUS,
                "source_result_id": completed["report_id"],
                "environment_id": study.cfg["environment_id"],
                "objective": study.cfg["objective"],
                "starting_states": {str(p): study.parents[p][1] for p in PLAYERS},
                "eligible_source_games": sum(map(len, sources.values())),
                "worlds": rows,
                "partitions": scope,
                "counts_by_boss": dict(Counter(row["act1_boss"] for row in rows.values())),
                "optimizer_updates": 0,
                "game_launches": 0,
                "frozen_checks": completed["frozen_checks"],
            },
        )
