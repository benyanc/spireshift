# Interface repairs and checks without additional game collection

The owner requested four confirmed fixes and a way to uncover further interface
gaps without relying on more full games. The four failures are not an exhaustive
list. Source inventories, recorded observations, generated envelopes and injected
faults cover different parts of the problem; none proves every possible sequence
or content interaction.

The completed owner diagnostic remains preserved: eight prefix starts, 771
delivered choices (460 native / 311 official), 778 complete public captures and
four official stops. Its old converter accepted 776 captures. The audit's 11 issue
groups include already-resolved reference/enablement cases; they were not 11
outstanding failures. All official shutdown/archive/profile/app-reset checks pass.

## Four repairs

1. **Normal endings.** The shipped `game_over` context already reports an explicit
   standard win/loss from public `RunHistory.Win`. Continue/return controls belong
   to the result screen. Shared converter v3 retains those controls in the public
   observation, records the explicit ending and prevents policy action delivery
   after termination. Native endings still require their explicit public Boolean.
   Missing or contradictory outcomes reject; HP/floor do not infer victory.
2. **Scoped card views.** Selected in an active transformation menu and unselected
   in a general deck read are compatible facts about different views of the same
   card. Retain them under owned `public_card_views`, alongside source-scoped
   descriptions and legality. `LiveContextReader.BuildCard` explicitly accepts a
   display pile, selected flag and optional combat-legality query. Exact ordered
   tooltip structures may union those view facts; other ordered-array, identity,
   intrinsic-cost or unknown-data conflicts still reject. Physical copies, named
   status amounts and all original action bindings remain distinct.
3. **Fresh reads before a choice.** An explicit SDK HTTP 409 with error code
   `stale_state` discards the entire partially read bundle. Refresh a complete
   observation and obtain every advertised read again, with at most three
   refreshes and a 15-second local deadline inside the existing session cap.
   Policy sampling happens after a complete coherent bundle. Transport failures,
   foreign runtimes, other 409s and inconsistent successful payloads reject.
   Submitted actions and uncertain deliveries are never retried.
4. **Explicit shop navigation.** The shipped room outside the inventory and the
   open inventory are different typed surfaces. Map their explicit flags and exact
   current open/leave controls to the existing navigation contract. Do not default
   a missing native flag to false. Keep purchase/removal/potion choices, raw action
   IDs and exact delivery ownership. Only a verified delivered inspection updates
   public navigation memory, preventing the open/close/reopen loop. Existing
   merchant-potion reinspection remains available.

The rules engine, frozen game DLL, native worker v11 and export build v36 do not
change. New shared manifest **v6** labels the changed observations/adapter and
imports both original complete players with every numerical weight and Adam
moment/counter exact. Input conversion can change behavior despite exact imports.
The previous manifests, failed development pass, original canaries and source
snapshots remain intact. No training, promotion or adaptive controller follows.

## Offline discovery and verification

The active recipe is
`configs/native-compatibility/sts2-v0.111.0-a8-interface-controls-offline-v3.json`.
It runs from the default `scripts/check-interface-controls-v1.sh`, launches no
game and writes to `artifacts/native-interface-controls/offline-v3`.

- Stream all **778** completed captures, including rejected and terminal frames.
  The repaired converter accepts all **778**, preserves every raw action mapping
  and fixes both old conversion failures. Every independent frame is checked;
  later states from divergent games are never treated as matched states.
- Inventory all **24** declared official surface kinds and their typed records.
  Require the source kind set to match the adapter registry. Generate **20**
  artificial policy/terminal envelopes; the other four are startup/tutorial
  presentation families with separate existing handlers. These are structural
  probes, not native effects or complete concrete instances of every SDK record.
- Feed every converted nonterminal capture and each generated envelope through
  both frozen players: **1,586 / 1,586** input probes pass. They use independent
  read-only inference, not new episodes, verified action delivery or strength
  evaluation. Terminal frames never request a policy choice.
- Exercise **38** generated corruption/preservation mutations: stale/hidden/partial
  reads, foreign owners, duplicate actions, incomplete menus, conflicting outcomes,
  selection membership/count inconsistencies, missing/contradictory shop flags,
  meaningful costs/upgrades/counters/status amounts and unfamiliar public facts.
  All pass their declared reject-or-preserve checks. Extra timing tests exercise
  a read bundle becoming stale after a successful first read, refresh exhaustion
  and unrelated failures without any action submission.
- Inventory literal Python consumer accesses, simple aliases, conditional `.get`
  paths and explicit numeric-baseline requirements. This exposes requirements such
  as `inventory_open`, energy and block before gameplay. Keep dynamic lookup and
  control-flow limitations explicit; do not call it complete static verification.
- Preserve source snapshots, all negative development evidence and **1,644**
  pre-existing pinned files/full states, including the offline-layout prototype.
  The active saved pass takes **16.14 seconds / 247.53 MB peak RAM / 6.90 MB output**,
  with zero game launches, optimizer updates or app copies.

The sweep caught a nested-tooltip regression introduced during development and
an incomplete artificial combat envelope. Both were corrected before acceptance;
the failed pass and original source snapshot remain preserved. This is evidence
that regression checks find problems without collecting more games.

## Limits and next work

`source-and-consumer-inventory.json` lists unobserved runtime families and static
limits separately. A generated envelope does not prove an event, relic, potion or
card combination works in the actual engine. Read-only inference acceptance does
not establish a correct action or stronger player. Existing first-state layout
differences remain, so full official/CLI input/effect equivalence is still blocked.

Continue explicit semantic layout mapping from completed records, preserving
unknown facts. Add targeted state/transition fixtures for important uncovered
interfaces instead of repeatedly collecting whole games or requiring every
content combination. Keep provenance/shape changes separate from game-rule
differences. Source/schema changes must invalidate the saved receipts.

Live wiring uses the separate v3 runner/session and the existing shared app with
private profiles. The short four-decision-per-host control passes: eight deliveries, exact app,
profile/archive reset, **41.45 seconds / 1.18 GB / 7.12 MB**, zero app copies or
updates. A saved-only verification independently rebuilds all eight public inputs,
frozen choices and actual receipts in **3.96 seconds** with zero game launches.
Both original full states and all Adam remain exact.
The bounded fresh owner canary is prepared only after that exact control passes;
it is validation, not the primary bug-discovery mechanism. Training/resume and
promotion continue to require the full compatibility gate. No interrupted seed
is replayed or historical manifest relabelled.

See the current handoff in `docs/backlog.md` and portable evidence in
`docs/evidence/native-interface-controls-v1.json` for final checks and live-control
status. Full repository checks pass **2,549 tests**, strict types on **573 files**,
format/lint and the C# protocol in **143.95 seconds**. An explicit combined Node/
prototype run passes **123** tests. The separately versioned
offline-layout prototype remains unintegrated.

The broader validation command is prepared for a later owner-run stage:

```bash
bash scripts/compare-interface-controls-v1.sh
```

It uses two fresh worlds and both original players, reuses completed pairs and
pauses at clean 15-minute boundaries. It has not been started. The current repairs
and offline discovery do not require replaying the old failed command.
