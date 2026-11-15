# Normal-start A8 demonstration admission

The batch runner prepares whole-world demonstrations for #35 and #134 on the
frozen `v0.111.0+41cef1ea` native host. It screens exact source files before
launching a worker and can re-audit saved victories without opening the game.
The [pilot declaration](../configs/native-curriculum/sts2-v0.111.0-a8-archive-pilot-v1.json)
pins the source digests, execution environment, terminal-victory objective
and separate development and final-test seed sets.

## Intake and verification

- Require a complete, reload-free journal from a standard solo Ironclad/A8
  start, one completed attempt per fight, all three acts, and the final boss
  and Architect Proceed. Reject a known missing selector answer before launch.
- Keep the recorded human pick for deck transforms and enchantments when the
  offer, pick, effect and outcome agree on the physical card and selection
  order. The existing matcher still binds that pick against the current
  native selector and its full menu.
- Reconstruct every binding, receipt and successor against the raw worker
  observations. Require genuine native victory, one clean Neow start and
  clean shutdown. Preserve capped, divergent, interrupted and unattempted
  cases in the batch denominator. A source rejection or partial replay
  supplies no labels.
- Export only public inputs and delivered choice indices. Group the factors
  of an ordered selector as one answer. Seal each world separately with its
  source, receipt and label hashes. The world index supports later fitting
  that weights worlds evenly.

The pilot gate requires three distinct verified winning worlds, at least two
Neow openings, two Act 1 bosses and two final bosses, with delivered decisions
across all three acts. It checks combat, map, event, card reward, reward
claim, shop and rest-site coverage. The gate marks a candidate for a separate
fitting admission. No fitting, promotion, official qualification or evaluation
starts from the batch runner.

## Running a batch

The source files and raw native evidence remain under private `artifacts/`.
Place the exact downloaded journals at the declared paths. Screen a declaration
offline with `uv run --no-sync python -m spireshift.native_a8_archive_batch`.
The [runner](../scripts/qualify-a8-archive-batch-v1.sh) takes an optional path
to a versioned declaration. Close STS2 before running a declaration that
includes fresh native work.

```bash
bash scripts/qualify-a8-archive-batch-v1.sh
```

A repeat of a sealed declaration verifies its saved files. An interrupted
world keeps its active marker. The runner uses one native attempt per fresh
seed and can import a successful prior replay by its sealed report.

## Pilot result

The [sealed pilot report](evidence/native-a8-archive-pilot-v1.json) accounts
for seven distinct worlds. The Queen control supplied 896 re-verified
deliveries across all three acts. Both fresh attempts shut down cleanly and
their prefixes remain diagnostic.

| Source | Result |
| --- | --- |
| [Queen control](https://spire-codex.com/runs/ee2ffb605c67742f/replay) | Reconstructed the saved Neow-to-victory run and indexed 896 public answers. |
| [Crystal Sphere](https://spire-codex.com/runs/3b747e9621031ae1/replay) | The payment branch lacks its grid answer. |
| [Interrupted source](https://spire-codex.com/runs/9dc545337e0fc3eb/replay) | Three unmatched combat starts despite the zero-reload header. |
| [Shop acquisition](https://spire-codex.com/runs/3cb0429d17be9210/replay) | The reader classified a reward-tagged shop card as a card reward. The next source record identifies its exact purchase. The native shop menu was present. |
| [Shop removal](https://spire-codex.com/runs/6739ccb495f9b471/replay) | A recorded empty removal pick precedes purchases without a removal charge. The reader expected a paid removal. |
| [Opening selector](https://spire-codex.com/runs/6f7d841fbdf0bb23/replay) | Native exposed the opening discard selector after room entry. The journal records the three-card answer after its combat-start marker. The reader expected a playable turn before consuming that pick. |
| [Special reward](https://spire-codex.com/runs/28b20eb6e1e88812/replay) | A special-reward completion lacks the linked acquisition required by the reader. |

The fitting gate remains blocked at one of three verified worlds. The pilot
covered the required decision families in the saved Queen run. The next
archive change should associate recorded choices with the actual decision
owner and its lifecycle across shops, rewards and selectors. Use these
saved menus and journals as regressions. The Crystal Sphere answer
requires a source that captures the grid. Follow source and saved checks
with a new cohort of complete journals.

The startup audit initially interpreted a native act-sequence diagnostic
as a prepared start. The corrected audit verifies the exact start request
and the worker's Neow identity. The earlier audit marker is preserved.
All four checkpoint/Adam states, the game archive, runtime, SDK,
localization and shared profile passed the frozen checks. The pilot made
zero optimizer updates.
