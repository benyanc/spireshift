# Exact-final canary result: three pairs match; official CPU guard stops the fourth

The November 4, 2026 owner run preserves **three genuine matching ending pairs,
one CPU-limited incomplete pair and two unattempted pairs**, out of the original
six. The changed-final qualification gate remains closed. The saved-only audit
finds no public-input, legal-menu, choice or delivery divergence in the observed
common prefixes. [Result evidence](evidence/native-varied-final-canary-result-v1.json)
binds the raw reconstruction, exact finals and unchanged frozen inputs.

## The six declared cases

| Initializer / mode | World suffix | Native / official choices | Native / official reported gameplay CPU seconds | Result |
| --- | --- | --- | --- | --- |
| 2 / reference | VTV201 | 136 / 136 | 4.95 / 94.89 | Matching genuine loss, official summary and reset |
| 3 / reference | VTV202 | 98 / 98 | 4.66 / 67.74 | Matching genuine loss, official summary and reset |
| 2 / teacher | VTV203 | 240 / 240 | 6.92 / 122.76 | Matching genuine loss, official summary and reset |
| 3 / teacher | VTV204 | 261 / 239 | 7.69 / 128.18 | Official host stops at its 128-CPU-second guard |
| 2 / teacher with original noncombat actor | VTV205 | — | — | Unattempted |
| 3 / teacher with original noncombat actor | VTV206 | — | — | Unattempted |

Worlds have the full prefix `SP1RESH1FT`. CPU columns are the existing host-level
accounting, including supporting processes; they are not neural-inference times
or a matched-work speed ratio. Official totals include ending presentation for
completed cases. At the genuine ending boundary those three official totals were
94.07, 67.04 and 122.00 seconds. Different worlds and the stopped trajectory cannot
establish a teacher/reference playing-strength comparison. All observed genuine
endings were losses; this is a compatibility panel, not the full-game evaluation.

## Why the session stopped

The fourth official report records `Official gameplay compute guard before a
genuine ending`, **128.184731264 CPU seconds** and **239 actual policy choices**.
The final offered menu is nonterminal combat at act 1, floor 17. No 240th choice
was supplied or delivered. The SDK's secondary `No checkpoint choice supplied`
message follows the coordinator's intentional abort; it is not evidence of a
missing legal action or failed model inference.

The official guard sums the Python coordinator's CPU delta plus the Godot game
and SDK Node process user/system CPU, starting before game launch. The native
host sums its worker, converter and Python delta. The official figure therefore
includes game/connector/UI/bridge activity and startup, not just policy inference.
The saved reports do not retain component-level CPU samples, so the exact
performance bottleneck is still unmeasured. The 60-FPS game launch and the process
accounting are source facts, not proof of which component exhausted the budget.

This is the **per-host 128-second guard**, while the outer session's cap is null.
The owner used **1,432.02 wall / 550.05 CPU seconds**, below the outer 4,200-wall /
7,200-CPU limits, with about 842 MB peak RAM and 46.5 MB retained output. Increasing
the outer allowance would not resolve this particular stop. The 384-choice guard
was not reached.

The native counterpart independently reached a genuine loss after 261 choices
using 7.69 reported gameplay CPU seconds. Its remaining 22 choices and ending
were never executed by the official host and cannot count as an official ending.
The fourth pair remains incomplete, even though its delivered prefix matches.

## Independent saved-only verification

Two bounded audits independently reconstruct **1,448 actual action deliveries**:
735 native and 713 official. They reproject raw observations, restore the exact
frozen policy/mode, reproduce action probabilities, navigation/RNG and choices,
and verify actual acceptance/completion receipts, atomic selections, reward
transitions and all six completed official shop tasks. The three completed case
seals, complete playable inputs/menus, genuine ending facts, persistent state,
all public reads and official summary proofs verify. Their terminal presentation
graph differences remain recorded under the prospectively declared contract.

For VTV204, a separately retained diagnostic verifier keeps those same raw checks,
requires the exact pre-choice CPU-guard failure, verifies all **239 acknowledged
deliveries** and compares **240 offered nonterminal menus** with the native
prefix. It explicitly omits choosing from the last unsubmitted menu and requires
a nonterminal, fully acknowledged prefix. It grants no ending qualification and
does not edit or weaken the frozen complete-run verifier. Across all four cases,
713 delivered choice pairs and 714 offered nonterminal menus match. No divergent
suffix is realigned or replayed. The diagnostic verifier and its small source
diff are retained privately with the audit.

All four attempted native hosts exit cleanly. Every official integrity/shutdown/
profile check passes and the managed app returns to its frozen baseline, with
zero new app copies. The incomplete fourth case's active marker and all raw
evidence remain preserved. Its missing pair seal and the absent global canary
report correctly reject automatic resume. VTV205/206 directories do not exist.

All **29,714 protected prior files**, exact epoch-16 final weights/full Adam,
both original full weights/full Adam, game v0.111.0 / 41cef1ea, CLI56 / Connector31 /
worker24 / converter16 / layout12 / environment48 and execution runtime verify
unchanged. Original Adam stays 5,658/6,045; fitted Adam stays 5,722/6,109. The
barrier remains `sha256:dbcb59804525246e6cd92a2a1273f7094afb735eca8c69dfa9171350f124d189`.
These audits create zero new games and zero optimizer updates.

## Next work

Do not rerun `compare-varied-finals-v1.sh` to try VTV204 again, clear its marker,
raise the 128-second guard, refit a player or count 3/4 attempted pairs as a
completed six-pair panel. The preserved incomplete case intentionally blocks the
old command.

The next proposed implementation is a **separate CPU-accounting and official-runner
performance investigation**, starting with saved/source evidence and retaining
these exact finals, game build and whole-run compute objective. Record policy,
game/UI and bridge costs separately before attributing the excess. Any runtime
optimization needs its own short regressions and new versioned compatibility
attempt, preserving the failed case and all three successes. A changed compute
constraint would require the objective's explicit ADR/test process; this result
does not authorize one.

No new long run is prepared by this assessment. All six required modes still
need their declared qualification before separately selected withheld/fresh
full-game and same-final routing-interference evaluation. No fitting, ordinary
PPO, promotion, scaling, adaptive controller or automatic next experiment follows.

The original [preparation guide](native-varied-final-canaries.md) and its launch
receipt remain historical evidence. This result supersedes its unstarted handoff.
