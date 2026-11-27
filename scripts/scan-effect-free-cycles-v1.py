"""Saved-only scan for model-owned decisions that return to an identical public state.

A cycle is a run of delivered policy choices that starts and ends at the same
public input (same ``public_input_id``). Identical public inputs mean the
player-visible run, deck, HUD and menu are unchanged, so the steps in between had
no public effect. The scan reads saved journals only; it launches no game and
changes no file outside its output directory.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def game_cycles(path: Path) -> tuple[int, list[tuple[tuple[str, ...], int]]]:
    states: list[tuple[str, str, str]] = []
    pending: dict[str, Any] | None = None
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["kind"] == "policy_input":
                pending = row["frame"]
            elif row["kind"] == "policy_choice" and pending is not None:
                choice = row["choice"]
                if row.get("receipt", {}).get("delivery") != "delivered":
                    pending = None
                    continue
                index = choice["action_index"]
                label = pending["public_input"]["candidates"][index]["label"]
                states.append((choice["public_input_id"], pending["source_family"], label))
                pending = None
    cycles = []
    last: dict[str, int] = {}
    for t, (state, _, _) in enumerate(states):
        if state in last:
            s = last[state]
            signature = tuple(f"{fam}:{lab}" for _, fam, lab in states[s:t])
            cycles.append((signature, t - s))
        last[state] = t
    return len(states), cycles


def generic(label: str) -> str:
    # Merge item-specific labels so signatures group by mechanism.
    for prefix in ("Buy ", "Play ", "Use ", "Discard "):
        if label.split(":", 1)[-1].startswith(prefix):
            fam, lab = label.split(":", 1)
            return f"{fam}:{prefix.strip()} <item>"
    return label


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="artifacts/effect-free-cycles/scan-v1")
    parser.add_argument("roots", nargs="+")
    args = parser.parse_args()
    started = time.monotonic()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    signatures: Counter[tuple[str, ...]] = Counter()
    wasted: Counter[tuple[str, ...]] = Counter()
    families: Counter[str] = Counter()
    examples: dict[tuple[str, ...], str] = {}
    digest = hashlib.sha256()
    for root in args.roots:
        for path in sorted(Path(root).glob("*/shared-public.jsonl.gz")):
            if not (path.parent / "done.json").exists():
                continue  # unsealed or failed attempts are never treated as clean evidence
            digest.update(str(path).encode())
            decisions, cycles = game_cycles(path)
            area = totals[root]
            area["games"] += 1
            area["decisions"] += decisions
            area["games_with_cycles"] += bool(cycles)
            for signature, length in cycles:
                key = tuple(sorted({generic(step) for step in signature}))
                signatures[key] += 1
                wasted[key] += length
                area["cycle_decisions"] += length
                for step in signature:
                    families[step.split(":", 1)[0]] += 1
                examples.setdefault(key, str(path))
    report = {
        "schema_version": "effect-free-cycle-scan-v1",
        "roots": args.roots,
        "scanned_paths_digest": digest.hexdigest(),
        "per_root": {k: dict(v) for k, v in totals.items()},
        "decisions_inside_cycles_by_family": dict(families.most_common()),
        "signatures": [
            {
                "steps": list(k),
                "cycles": signatures[k],
                "decisions": wasted[k],
                "example": examples[k],
            }
            for k, _ in wasted.most_common(40)
        ],
        "games_launched": 0,
        "optimizer_updates": 0,
        "wall_seconds": time.monotonic() - started,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "signatures"}, indent=1))
    for row in report["signatures"][:15]:
        print(row["decisions"], row["cycles"], row["steps"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
