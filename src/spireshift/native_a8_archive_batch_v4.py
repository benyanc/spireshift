"""Qualify archive worlds after verifying their earlier clean replay stops."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_batch_v2 as runner
from spireshift import native_a8_archive_batch_v3 as v3
from spireshift import native_a8_archive_reward_owners_v4 as owners
from spireshift import native_a8_replay_probe as replay
from spireshift.engine_learning import identified
from spireshift.native_a8_mix_session import admit
from spireshift.native_a8_replay_source import Journal
from spireshift.native_compatibility_contract import local
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records, same

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-qualification-v4.json"
SCHEMA = "native-a8-archive-batch-v4"
REQUIRED = v3.REQUIRED | {
    "src/spireshift/native_a8_archive_batch_v4.py",
    "src/spireshift/native_a8_archive_reward_owners_v4.py",
    "scripts/qualify-a8-archive-batch-v4.sh",
}
legacy_probe = replay.probe


@dataclass(frozen=True)
class Predecessor:
    report_id: str
    trace: Path
    deliveries: int
    final: dict[str, Any]


def load_predecessor(root: Path, ref: dict[str, Any], case: dict[str, Any]) -> Predecessor:
    workspace = local(root, ref["workspace"])
    cfg = json.loads((workspace / "config-at-launch.json").read_text())
    store = ChunkJournal(root, cfg)
    if store.workspace != workspace:
        raise ValueError("The preceding archive workspace differs")
    request = json.loads((store.path(ref["chunk"]) / "active.json").read_text())["request"]
    seal = store.completed(ref["chunk"], request)
    if seal is None or seal["report_id"] != ref["seal_id"]:
        raise ValueError("Require the exact sealed archive attempt")
    (trace,) = (root / name for name in seal["sources"] if name.endswith("/" + replay.TRACE))
    directory = trace.parent
    report = identified(directory / "report.json")
    config = identified(directory / "config.json", "config_id")
    final = identified(directory / "last-frame.json")
    if (
        report["report_id"] != ref["native_report_id"]
        or report["config_id"] != config["config_id"]
        or report["source_sha256"] != case["source"]["sha256"]
        or config["seed"] != case["seed"]
        or config["source"] != f"https://spire-codex.com/runs/{case['run_id']}/replay"
        or report["status"] != "stopped_preserving_evidence"
        or report["clean_shutdown"] is not True
        or report["stop"]["delivery_uncertain"] is not False
        or report["verified_native_deliveries"] != report["acknowledged_before_stop"]
        or report["verified_native_deliveries"] <= 0
        or not all(report["frozen_checks"].values())
    ):
        raise ValueError("An archive continuation requires verified deliveries and a clean stop")
    return Predecessor(report["report_id"], trace, report["verified_native_deliveries"], final)


def preflight(
    root: Path,
    cfg: dict[str, Any],
    screened: dict[str, tuple[Journal | None, dict[str, Any]]],
) -> tuple[dict[str, Predecessor], dict[str, Any]]:
    declared = cfg["clean_stops"]
    candidates = {case["run_id"]: case for case in cfg["cases"] if not case.get("saved")}
    if declared.keys() - candidates.keys():
        raise ValueError("A clean predecessor must belong to a declared replay")
    base = admit(root)
    if cfg["environment_id"] != base.ctx["environment_id"]:
        raise ValueError("The archive must use the verified frozen environment")
    locale = base.ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): value
        for kind in ("potion", "relic", "card")
        for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    priors, results = {}, {}
    for key, ref in declared.items():
        prior = load_predecessor(root, ref, candidates[key])
        journal = screened[key][0]
        if journal is None:
            raise ValueError(f"Archive {key} failed source screening")
        journal = replace(journal, reward_names=names)
        cursor = count = 0
        for row in records(prior.trace):
            index, cursor, domain = replay.next_choice(
                row["frame"], journal, cursor, len(journal.intents)
            )
            replay.equal(
                "reconstructed preceding action",
                (row["choice"]["action_index"], row["receipt"]["delivery_domain"]),
                (index, domain),
            )
            count += 1
        replay.equal("preceding verified deliveries", prior.deliveries, count)
        index, _, domain = replay.next_choice(prior.final, journal, cursor, len(journal.intents))
        if index is None:
            raise ValueError(f"Archive {key} has no verified next choice")
        priors[key] = prior
        results[key] = {
            "verified_prefix": count,
            "prior_report_id": prior.report_id,
            "delivery_domain": domain,
            "next_choice": prior.final["public_input"]["candidates"][index]["label"],
        }
    return priors, results


@contextmanager
def continuation(root: Path, priors: dict[str, Predecessor]) -> Iterator[None]:
    execution = root / batch.AREA / "execution"

    class ContinuationJournal(ChunkJournal):
        def begin(self, key: str, request: dict[str, Any]) -> Path:
            prior = priors.get(request.get("run_id", ""))
            if self.workspace == execution and key.startswith("seed-") and prior is not None:
                if not self.path(key).exists():
                    raise ValueError("The archive seed has no preserved initial attempt")
                return super().begin(
                    f"v4-{key}", {**request, "preceding_native_report": prior.report_id}
                )
            return super().begin(key, request)

    def probe(
        root: Path,
        journal: Journal,
        source: Path,
        *,
        control: bool,
        attempt: int,
    ) -> dict[str, Any]:
        report = legacy_probe(root, journal, source, control=control, attempt=attempt)
        prior = priors.get(replay.SAMPLE)
        if prior is not None:
            if (report["verified_native_deliveries"] or 0) < prior.deliveries:
                raise ValueError("The replay stopped before reconstructing its preceding prefix")
            out = root / replay.AREA / replay.SAMPLE / f"archive-qualification-v{attempt}"
            current = iter(records(out / replay.TRACE))
            for old in records(prior.trace):
                new = next(current)
                replay.equal(
                    "preceding public input",
                    True,
                    same(old["frame"]["public_input"], new["frame"]["public_input"]),
                )
                replay.equal(
                    "preceding action and delivery",
                    (old["choice"]["action_index"], old["receipt"]["delivery_domain"]),
                    (new["choice"]["action_index"], new["receipt"]["delivery_domain"]),
                )
        return report

    with (
        patch.object(batch, "ChunkJournal", ContinuationJournal),
        patch.object(replay, "probe", probe),
    ):
        yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", nargs="?", default=RECIPE)
    parser.add_argument("--run", action="store_true", help="Run the declared archive worlds")
    args = parser.parse_args()
    root = Path.cwd()
    try:
        recipe = local(root, args.recipe)
        with patch.multiple(runner, SCHEMA=SCHEMA, MATCHER=owners.MATCHER, REQUIRED=REQUIRED):
            cfg = runner.load(root, recipe)
        screened = {case["run_id"]: owners.screen(root, case) for case in cfg["cases"]}
        with owners.installed():
            priors, report = preflight(root, cfg, screened)
            if args.run:
                with continuation(root, priors):
                    result = batch.execute(root, recipe, cfg, screened)
                check_sources(root, cfg["replay_implementation"])
            else:
                result = {
                    "status": "archive_qualification_ready",
                    "sources": {key: row for key, (_, row) in screened.items()},
                    "preceding_choices": report,
                    "optimizer_updates": 0,
                }
    except batch.FAILURES as exc:
        result = {
            "status": "stopped_preserving_evidence",
            "error": str(exc),
            "optimizer_updates": 0,
            "training_admission_granted": False,
        }
    print(json.dumps(result))
    return 2 if result["status"] == "stopped_preserving_evidence" else 0


if __name__ == "__main__":
    raise SystemExit(main())
