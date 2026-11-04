# Card display contexts and rest visible text

Connector31 implements the two text-projection repairs from E2E609/E2E610.
The game remains v0.111.0 / 41cef1ea, assembly SHA-256
`9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4`.
CLI56 / ordinary worker24 / converter16 / layout12 and both original players'
numerical weights and complete Adam states are unchanged. Connector31 source is
`4d0b95d38b0f8e0e0c273a7b4fa5fb7a0a0ad1ca`, environment48 `sha256:4c445e402d31ceea743165d203b03c1b9b6744f1a6a8396a797bb4a412efbc81`.
See [the pinned evidence](evidence/native-card-rendering-repair-v1.json).

## What changed

Every shared card export now requires a display-pile argument; the shared `Hand`
default is gone. Eight caller sites read the actual visible `NCard.DisplayingPile`,
including generated offers, rewards and card selection widgets. Missing widgets
fail closed. The other calls bind the native hand, preview/catalog or declared
public pile context explicitly. The older description helpers also require an
explicit context. This uses the shipped game's description formatter and
existing native widgets, with no card-name exception or game-rule replacement.

| Export context | Compiled call sites | Binding |
| --- | ---: | --- |
| Visible selection/reward widgets | 8 | Actual NCard.DisplayingPile |
| Combat hand | 3 | Hand |
| Preview, bundle, event hover, shop/catalog | 5 | None |
| Public pile read | 1 | Explicit caller-supplied pile |

The shipped generated-choice widget and CLI both use `None`. Its Body Slam
text therefore stays "Deal damage equal to your Block." A card shown in hand
can still have the native combat hint. Damage calculations and conditional
formatting belong to STS2; no suffix is fabricated or stripped by a comparator.
The legacy event hover now also uses native preview context `None`.

One helper now applies the existing CLI visible-text convention to Connector
card and rest descriptions: each LF becomes one space. Every other codepoint
is preserved, including CR, tabs, existing spaces, amounts, ordered facts,
unknown text and repeated glyph tokens. Regal Pillow's bonus remains +15 HP;
healing rules and action completion code are unchanged. Comparison still checks
all public description fields exactly.

## Short verification and its limits

All 265 exact-assembly Host tests pass, including required-context, missing-widget
and text-preservation regressions. Portable SDK/package/protocol/boundary checks
pass. Connector31 produces the same artifact from two fresh source builds.
A compiled source audit inventories all 17 shared card calls; all 158 existing
native delivery methods and their completion behavior remain unchanged.

The frozen native model formatter and compiled production exporter agree on
112 vectors: four cards, base/upgraded, two block states and seven display-pile
contexts. The native Regal Pillow description agrees with the compiled helper.
This is one fresh privileged source world, no policy choices or gameplay actions,
with Godot stubs confined to the probe. It is formatter evidence, not coverage
of all card effects or new official-app Live exercise. The successful source
probe uses the existing private runtime 9.0.7; no runtime or system update occurs.

Saved/source verification takes 73.21 seconds and independently
reconstructs all 781 historical actual deliveries and their receipts. It also
performs 670 current-input diagnostic choices. For player 2, all 88 common-prefix
inputs and choices match through the repaired Body Slam offer. Both diagnostic
players choose Body Slam; the last choice is left uncommitted. The old official
player chose Skip, so its later suffix is not used as a repaired ending. For
player 3, all 247 choices per host, full public inputs and standalone terminal
facts/reads match after the rest-text reprojection. Exactly 668 unchanged prior
choices are acknowledged diagnostically; none is sent to a game.

These are source/saved checks. Historical E2E609/E2E610 reports stay blocked,
with original bytes and identities. All 21,356
protected prior files, the frozen master, idle working app, original weights
and complete Adam states verify exact. The earlier probe, installation and
saved-diagnostic failures are preserved and explained in the evidence. Final
exact repository and owner-preflight receipts are saved separately under the
new preparation workspace after the source freeze.

## One longer owner command

Close STS2 and run from any directory:

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-render-endings-v1.sh"
```

This is prepared and unstarted: two fresh natural pairs E2E611/E2E612, one per
original player, on one fixed working app with fresh isolated profiles. Expect
about 5–15 minutes; outer cap 40 minutes, pair cap 10 minutes. Each host retains
128 gameplay CPU seconds and a 384-choice guard. There are no fixture saves,
forced outcomes, historical retries or automatic follow-ups.

Admission still requires matching playable inputs and menus, complete terminal
facts and public reads, genuine endings, official native Continue/summary proof,
actual shop-task completion proofs and clean resets. A time/choice/compute limit
is incomplete. The result needs assessment before broader admission or the
finite return to fitting-only teaching/interference. No training, promotion,
adaptive controller or playing-strength claim follows automatically.
