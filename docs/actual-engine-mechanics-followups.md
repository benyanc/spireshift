# Short checks after the repaired mechanics sweep

This stage completed on 2026-10-15 after the owner's repaired **1,849/1,849** sweep passed.
All **nine random-action runs** passed with **522 decisions**, zero interface failures or
truncations and an identical repeat trace. The same-build act/ending fixtures passed too.
[Completed evidence](evidence/actual-engine-mechanics-sweep-and-followups-v1.json) binds the
underlying cases, native build, separate saved-only verification and resource measurements.

This stage leaves every Python file, helper, native build, recipe and workspace pinned by
that sweep unchanged. The original failed sweep and the blocked short launch reports remain
preserved; they were not relabelled as successful.

The combined entry point first verifies the saved full sweep, every case hash, the original
denominator, generated plan, native build and absence of failed/incomplete cases. An unfinished
or failed sweep cannot start this stage. An active game also blocks native launches; do not
close or interrupt the owner's current job to bypass that guard.

## Implemented checks

Nine bounded natural sequences use four independent Ironclad/A8 game seeds, two independent
action RNG seeds and one exact repeat. The chooser receives only the current public menu and
samples every advertised action, including Skip and rest/shop choices when offered. It does
not filter for the old heuristic's recommendation or mutate the game with a private fixture.

Each sequence stops at a public terminal observation or 256 delivered actions. The next public
state must still be complete. Wall bounds and existing liveness rules detect stuck games.
Failures and logs are preserved; worker shutdown must be proved before another planned seed
starts. No uncertain action or failed seed is retried. Bounded prefixes and observed terminal
games remain separate counts; these are not playing-strength or readiness measurements.

Compressed canonical public traces record every current menu and chosen action. Saved-only
verification reconstructs action counts, decision families and trace hashes; rejects private,
unadvertised and partial records; checks clean shutdown; and compares the exact repeat. Menu
transport ordering does not change the chosen semantic action.

The lifecycle recipe reuses the existing native progression checker against the same host v32.
Privileged boss fixtures check Act 1→2, Act 2→3 and the final Architect dialogue, native
game-over/victory-room flags and the zero-HP victory edge case. Forced fixtures supply zero
player wins and zero PPO examples. This does not repeat the shipped-app comparison or claim
whole-game parity.

One worker runs at a time, sharing frozen engine/runtime files with fresh mutable profiles and
zero game-app copies. Resource roots come from the pinned recipes. The combined cap is four
minutes, 480 CPU seconds, 4 GB memory and 1.5 GB new evidence. Actual combined wall time was
**33.83 seconds**, CPU time **21.16 seconds**, peak process-tree memory **302.87 MB**, and
retained evidence **7.20 MB**. The nine runs observed nine decision families, including shop
and selection choices; Skip was selected four times. Rest interactions remain covered by the
separate deterministic full-sweep fixture, not claimed as reached by these random runs.

## Validation and remaining work

Offline tests cover deterministic public sampling and Skip, current-snapshot delivery, prefix
bounds, stopping at terminal observations, hidden-input rejection, saved-trace audit, repeat
drift, missing/failed cases, denominators and refusing to unlock from assumed sweep success.

Both initial short launch attempts were blocked before starting a game by the active-game
guard. Their reports and empty sequence preparation remain preserved. The fresh sequence
recipe uses a new workspace and now passes actual native execution plus saved-only audit.
The earlier [implementation-only evidence](evidence/actual-engine-mechanics-followups-v1.json)
remains unchanged; the new completed evidence is linked above.

A successful combined result resolves only bounded-random-sequence and same-build lifecycle
requirements. **Outside-combat potion controls and non-creature targeting remain unfinished.**
Foul Potion changes its target kind outside combat and uses a merchant presentation target;
its successful combat fixture does not qualify that use. No training, model migration,
base-readiness pass or adaptive controller follows automatically.

## Saved verification

This batch is complete. The existing command now verifies the saved full sweep and follow-up
evidence; it plays no games and launches no next experiment:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/check-native-mechanics-followups-v1.sh
```

Saved complete results are verified without playing again. Failed or interrupted workspaces
stay preserved for inspection; re-running does not silently retry them or overwrite reports.
