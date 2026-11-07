# Event choices compared with the frozen game

The fourth repair removes the unconditional event skip that let a simulator agent avoid mandatory
choices, costs and fights. Genuine Leave options keep their captured indices, including option 3
at Welcome to Wongos. Event handlers reject locked and nonexistent options before changing state.
No policy restriction, weight update, hidden information or reward shaping implements this fix.

The comparison reads enabled options directly from the original v0.107.1 / Steam 23811903 captures:
52 initial screens and 57 settled later event screens. It compares every action-mask slot and
checks that absent or locked choices return rejection without changing the public observation.
The [inventory](fixture-inventory.json) contains filenames and hashes only; proprietary captures
remain private. Dense Vegetation's option-1 capture is explicitly excluded from settled-page
comparison because upstream recorded it mid-transition. Its initial mask and effects are still
checked. Forty-six captures lead to other kinds of screen; this new comparison does not claim
to validate their action sets. Uncaptured events and later-act UI endings remain coverage gaps.

The active [configuration](../../configs/backend-repair/sts2-v0.107.1-event-choices-v3.json) pins
`event-choices-v3.patch`, all fixture bytes, six changed existing source/test files and the new test
class.
The old expectations that included the invented button are updated only in a separate candidate;
earlier source trees and all prior reports remain intact. The initial compile failure and an
intermediate full-suite failure from one obsolete assertion are preserved under distinct versions.

Codex published the final native candidate in 17.641 seconds. All 240 targeted checks passed:
109 captured choice lists, 99 captured outcomes and 32 earlier repair cases. The complete native
suite passed 4,942 tests, with one explicitly skipped performance probe, in 54.545 seconds.
Ten public environment contract checks passed in 0.982 seconds. A fresh public player completed
eight training-seed attempts in 7.687 seconds without crashes or stalls; all eight were terminal
losses. These are compatibility results with zero optimizer steps, not stronger gameplay.

[Evidence](../../docs/evidence/event-choice-repair-v1-evidence.json) pins the configs, patches,
candidate and native identities, runtime, tests, public adapter, fresh player and resource reports.
The candidate remains pending conformance. Its corrected initial choices intentionally differ
from historical trajectories, so the earlier 89/89 prefix audit is retained for its original
candidate and is not relabelled as a new-candidate pass. No old model or population is migrated.

The short build launcher is `scripts/build-event-choices-backend-v1.sh`; repeated calls verify the
saved build instead of rebuilding or training. Its hard cap is four minutes. Codex may run short
jobs; the owner launches and monitors jobs expected to take five minutes or more.

Upstream is [EvanGambit/sts2](https://github.com/evangambit/sts2), MIT licensed. Its license is
retained beside the patches. Game assemblies, extracted game rules and raw captures remain
outside Git under private artifacts.
