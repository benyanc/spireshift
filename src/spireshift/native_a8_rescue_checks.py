"""Saved decision regressions and a short, disjoint native prefix control."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_rescue_curriculum import ARMS, first_change
from spireshift.native_a8_rescue_game import TRACE, Progress, decisions, play
from spireshift.native_a8_rescue_inputs import CONTROL, CONTROL_DELIVERIES, freeze
from spireshift.native_a8_rescue_policy import discard, intervention, subject
from spireshift.native_compatibility_contract import verified
from spireshift.native_win4_game import write
from spireshift.native_win_teacher import card_stats, number


def saved_checks(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    diagnosis, panel = ctx["diagnosis"], ctx["paired_panel"]
    audit = identified(verified(root, diagnosis["audit"]))
    if audit["source_panel_id"] != panel["report_id"] or audit["status"] != diagnosis["status"]:
        raise ValueError("Saved diagnosis does not bind the paired Act 1 evidence")
    checks: dict[str, dict[int, tuple[str, dict[str, Any]]]] = defaultdict(dict)
    for reason, anchors in (
        ("hp_spend", diagnosis["lethal_hp_spend_cases"]),
        ("potion", diagnosis["fitted_purchase_discard_cases"]),
    ):
        for anchor in anchors:
            checks[anchor["key"]][anchor["line"]] = (reason, anchor)
    for cell in audit["cells"]:
        if cell["arm"] == "fitted":
            for anchor in cell["resources"]:
                if (
                    anchor["kind"] == "camp"
                    and anchor["label"] == "Smith"
                    and anchor["hp"] * 2 <= anchor["max_hp"]
                ):
                    checks[cell["key"]][anchor["line"]] = ("rest", anchor)
    clear_key = "world-07-p2-fitted"
    counts: Counter[str] = Counter()
    tested = []
    verified_act2 = False
    for key in sorted(set(checks) | {clear_key}):
        cell_dir = root / "artifacts/native-a8-paired/study-v1/chunks" / key
        seal = identified(cell_dir / "done.json")
        if seal["report_id"] != panel["seals"][key]:
            raise ValueError("The saved Act 1 control has the wrong episode seal")
        name = str((cell_dir / TRACE).relative_to(root))
        trace = verified(root, {"path": name, "sha256": seal["sources"][name]})
        progress = Progress() if key == clear_key else None
        with closing(decisions(trace)) as rows:
            for line, frame, chosen in rows:
                if progress is not None and progress.observe(frame) == "act1_clear":
                    verified_act2, progress = True, None
                if chosen is None:
                    continue
                index = chosen["choice"]["action_index"]
                domain = chosen["receipt"]["delivery_domain"]
                if progress is not None:
                    progress.delivered(frame, index, domain)
                if line not in checks[key]:
                    continue
                reason, anchor = checks[key].pop(line)
                public = frame["public_input"]
                menu = public["candidates"]
                hp = public["context"]["persistent"]["player"]["hp"]
                selected, actual = intervention(public, list(range(len(menu))), index)
                replacement = menu[selected]
                if (
                    selected == index
                    or actual != reason
                    or domain != "native"
                    or menu[index]["label"] != anchor["label"]
                    or hp != anchor["hp"]
                    or (
                        reason == "hp_spend"
                        and number(card_stats(subject(replacement)[1]).get("hploss")) >= hp
                    )
                    or (reason == "potion" and discard(replacement))
                    or (reason == "rest" and subject(replacement)[1].get("option_id") != "HEAL")
                ):
                    raise ValueError(f"Teacher failed saved {reason} menu {key}:{line}")
                counts[reason] += 1
                tested.append(
                    {
                        "cell": key,
                        "line": line,
                        "reason": reason,
                        "reference": menu[index]["label"],
                        "teacher": replacement["label"],
                    }
                )
        if checks[key]:
            raise ValueError("Missing saved Act 1 regression anchors")
    if counts != {"hp_spend": 4, "potion": 4, "rest": 12} or not verified_act2:
        raise ValueError(f"Expected all saved Act 1 regressions and the Act 2 transition: {counts}")
    return {
        "decision_regressions": dict(counts),
        "act2_transition_verified": verified_act2,
        "menus": tested,
    }


def control(
    root: Path, ctx: dict[str, Any], cfg: dict[str, Any], deadline: float
) -> dict[str, Any]:
    out = root / cfg["control_workspace"]
    out.mkdir(parents=True, exist_ok=False)
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    before, profile = freeze(root, ctx), _shared_snapshot(shared)
    saved = saved_checks(root, ctx)
    write(out / "saved-regressions.json", saved)
    episodes = {
        arm: play(ctx, CONTROL, arm, out / arm, deadline, choices=CONTROL_DELIVERIES)
        for arm in ARMS
    }
    if len({row["initial_public_input_id"] for row in episodes.values()}) != 1 or any(
        row["outcome"] != "capped"
        or row["cap"] != ["choices"]
        or row["native_terminal"]
        or row["verified_native_deliveries"] != CONTROL_DELIVERIES
        for row in episodes.values()
    ):
        raise ValueError("Short control must be three exact native prefixes on the same start")
    change = first_change(out / "fitted" / TRACE, out / "teacher" / TRACE)
    if change is None:
        raise ValueError("Short control must verify an actual same-menu teacher override")
    if freeze(root, ctx) != before or _shared_snapshot(shared) != profile:
        raise ValueError("Frozen inputs or the shared STS2 profile changed during the control")
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-act1-rescue-short-check-v1",
            "status": "act1_rescue_short_checks_verified",
            "config_id": ctx["config_id"],
            "environment_id": ctx["environment_id"],
            "control_world": CONTROL["seed"],
            "saved": saved,
            "native_prefixes": len(episodes),
            "native_deliveries": sum(
                row["verified_native_deliveries"] for row in episodes.values()
            ),
            "first_change": change,
            "episodes": episodes,
            "frozen_checks": before,
            "shared_profile_unchanged": True,
            "qualification_games": 0,
            "optimizer_updates": 0,
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in sorted(out.rglob("*"))
                if path.is_file() and not path.is_symlink()
            },
        },
    )
