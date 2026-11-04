"""Sealed phase units; existing unfinished units are never replayed or cleared."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal


class Pause(Exception):
    """Clean boundary between sealed units, with no live worker or pending update."""


def journal(context: dict[str, Any], phase: str) -> ChunkJournal:
    cfg = context["config"]
    return ChunkJournal(
        context["qualification"].root, {**cfg, "workspace": cfg["workspace"] + "/" + phase}
    )


def snapshot(context: dict[str, Any], store: ChunkJournal) -> dict[str, str]:
    root = context["qualification"].root
    result = {}
    for name, digest in context["config"]["implementation"].items():
        destination = store.workspace / "source-at-launch" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if _sha_file(destination) != digest:
                raise ValueError("Preserve a changed study source snapshot")
        else:
            destination.write_bytes((root / name).read_bytes())
        result[str(destination.relative_to(root))] = digest
    return result


def final(context: dict[str, Any], phase: str) -> dict[str, Any] | None:
    root = context["qualification"].root
    p = root / context["config"]["workspace"] / phase / "report.json"
    if not p.exists():
        return None
    value = identified(p)
    if value["config_id"] != context["config_id"]:
        raise ValueError("Saved phase belongs to a different fixed study")
    check_sources(root, value["sources"])
    check_sources(root, value["evidence"])
    return value


def finish(
    context: dict[str, Any], store: ChunkJournal, body: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any]:
    from spireshift.core.manifest import manifest_identifier

    root = context["qualification"].root
    value = {
        **body,
        "config_id": context["config_id"],
        "environment_id": context["environment"]["manifest_id"],
        "guard_receipt_id": context["guard_receipt"]["report_id"],
        "sources": sources,
        "evidence": {
            str(p.relative_to(root)): _sha_file(p)
            for p in store.workspace.rglob("*")
            if p.is_file() and p.name not in {"progress.json", "session.lock"}
        },
        "originals_unchanged": True,
        "game_build_frozen": True,
        "training_allowed": False,
        "promotion_allowed": False,
        "adaptive_controller_allowed": False,
        "automatic_follow_up": False,
    }
    value["report_id"] = manifest_identifier(value)
    atomic_json(store.workspace / "report.json", value)
    return value


def reserve(deadline: float, seconds: float, new: int, maximum: int | None) -> None:
    if deadline - time.monotonic() < seconds or maximum is not None and new >= maximum:
        raise Pause


def admit_result(
    root: Path, sources: dict[str, str], store: ChunkJournal, key: str, receipt: dict[str, Any]
) -> None:
    sources.update(receipt["sources"])
    sources[str((store.path(key) / "done.json").relative_to(root))] = _sha_file(
        store.path(key) / "done.json"
    )
