"""Matched single-change and lineage-preserving three-change native proposals."""

from __future__ import annotations

from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_natural_data import improves, mutations, select
from spireshift.native_turn_teacher_policy import round_number

CONTRACT = "natural_earlier_coordinated_teacher_comparison_v1"
ARMS = ("single_change", "coordinated")
ENTRIES = ("early", "later")
LIMITS = {"maximum_actions": 192, "maximum_rounds": 12, "prefix_decisions": 512}


def proposal(parent: dict[str, Any], edit: dict[str, int]) -> dict[str, Any]:
    i, action = edit["decision"], edit["action"]
    inherited = parent.get("edits", [])
    if (
        not 0 <= i < len(parent["steps"])
        or inherited
        and i <= inherited[-1]["decision"]
        or not 0 <= action < len(parent["steps"][i]["public_input"]["candidates"])
        or action == parent["steps"][i]["action_index"]
    ):
        raise ValueError("Each coordinated edit must change a later advertised choice")
    forced = [
        {"public_input_id": s["public_input_id"], "action_index": s["action_index"]}
        for s in parent["steps"][: i + 1]
    ]
    forced[-1]["action_index"] = action
    body = {
        "parent_fight_id": parent["fight_id"],
        "forced": forced,
        "edits": [*inherited, {**edit, "public_input_id": forced[-1]["public_input_id"]}],
    }
    return {**body, "plan_id": manifest_identifier(body)}


def extensions(parent: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """Keep an immediate continuation and a later-round alternative when available.

    Candidate outcomes do not choose positions. The parent's observed trace binds
    the new menu after all earlier changes; nested selections remain eligible.
    """
    edits = parent.get("edits", [])
    after = edits[-1]["decision"] if edits else -1
    options: list[dict[str, Any]] = []
    rounds: list[int] = []
    current_round = 0
    for i, step in enumerate(parent["steps"]):
        public = step["public_input"]
        if public["context"]["interaction"]["kind"] == "combat_turn":
            current_round = round_number(public)
            if current_round not in rounds:
                rounds.append(current_round)
        if len(rounds) > 3:
            break
        if i <= after or len(public["candidates"]) < 2:
            continue
        alternatives = sorted(
            (j for j in range(len(public["candidates"])) if j != step["action_index"]),
            key=lambda j: (-step["log_probabilities"][j], j),
        )
        options.extend(
            {"decision": i, "action": j, "round": current_round} for j in alternatives[:2]
        )
    if not options:
        return []
    chosen = [options[0]]
    later = next((o for o in options if o["round"] > chosen[0]["round"]), None)
    if later is not None and count > 1:
        chosen.append(later)
    chosen.extend(o for o in options if o not in chosen)
    return [
        proposal(parent, {"decision": o["decision"], "action": o["action"]}) for o in chosen[:count]
    ]


def expand_parent(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [r for r in rows if r["status"] == "complete"]
    # Preserve each first-change lineage, even when every intermediate plan loses.
    # This ranks local native endings, not full-run utility or a learned value.
    return (
        max(eligible, key=lambda r: (r["outcome"] == "win", r["resources"]["hp"], -r["candidate"]))
        if eligible
        else None
    )


def candidates(
    arm: str, slot: int, width: int, reference: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Exactly width + 2*width + width slots; no replacement of exhausted lineages."""
    if arm not in ARMS or not 0 <= slot < width * 4:
        raise ValueError("Preserve the declared matched candidate slots")
    if arm == "single_change" or slot < width:
        choices = mutations(reference, width * 4 if arm == "single_change" else width)
        return proposal(reference, choices[slot]) if slot < len(choices) else None
    by_candidate = {r["candidate"]: r for r in rows}
    if slot < width * 3:
        lineage, ordinal = divmod(slot - width, 2)
        parent = by_candidate.get(lineage + 1)
        choices = extensions(parent, 2) if parent and parent["status"] == "complete" else []
        return choices[ordinal] if ordinal < len(choices) else None
    lineage = slot - width * 3
    children = [
        by_candidate[n]
        for n in (width + lineage * 2 + 1, width + lineage * 2 + 2)
        if n in by_candidate
    ]
    parent = expand_parent(children)
    choices = extensions(parent, 1) if parent else []
    return choices[0] if choices else None


def later_root(early: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any] | None:
    """The late start fixes exactly the original greedy player's first turn."""
    for i, step in enumerate(reference["steps"]):
        p = step["public_input"]
        c = p["context"]["interaction"]
        content = c.get("content", {}).get("context", {})
        if (
            c["kind"] == "combat_turn"
            and content.get("is_play_phase") is True
            and content.get("round", 0) >= 2
        ):
            prefix = early["prefix"] + [
                {"public_input_id": s["public_input_id"], "action_index": s["action_index"]}
                for s in reference["steps"][:i]
            ]
            if len(prefix) > LIMITS["prefix_decisions"]:
                return None
            body = {k: v for k, v in early.items() if k != "root_id"}
            body.update(
                entry="later",
                prefix=prefix,
                public_input=p,
                public_input_id=step["public_input_id"],
                early_reference_id=reference["fight_id"],
                reference_offset=i,
            )
            return {**body, "root_id": manifest_identifier(body)}
    return None


def cell(reference: dict[str, Any], rows: list[dict[str, Any]], verified: bool) -> dict[str, Any]:
    chosen = select([reference, *rows])
    selected = next(r for r in [reference, *rows] if r["candidate"] == chosen)
    return {
        "verified": verified,
        "reference_outcome": reference["outcome"],
        "selected_outcome": selected["outcome"],
        "reference_hp": reference["resources"]["hp"],
        "selected_hp": selected["resources"]["hp"],
        "selected_candidate": chosen,
        "selected_fight_id": selected["fight_id"],
        "reference_fight_id": reference["fight_id"],
        "strict_local_improvement": verified and improves(selected, reference),
        "selected_edits": len(selected.get("edits", [])),
        "maximum_executed_edits": max((r.get("executed_edits", 0) for r in rows), default=0),
        "maximum_edited_rounds": max((len(r.get("edited_rounds", [])) for r in rows), default=0),
        "candidate_paths": len(rows),
        "selected_choices": selected["choice_decisions"],
        "selected_rounds": selected["public_rounds"],
        "proposal_cpu_seconds": sum(r["cpu_seconds"] for r in rows),
    }
