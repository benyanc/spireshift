# Test Subject combat loop repair

The v4 collection sealed case 38 and stopped in `fit-039/reference`. Test
Subject's Nemesis hook applied Intangible during the enemy turn. Its color
callback called `Godot.CanvasItem.SetSelfModulate(Color)`, which support build 57
lacked. The native combat loop faulted and End Turn eventually timed out.
The saved audit reconstructs 26 acknowledged decisions and one End Turn with
unknown completion. This prefix is diagnostic evidence.

Support build 58 adds that setter to the existing `SelfModulate` property.
Two independent builds produced matching host and stub assemblies. The exact
JIT exception reproduces against build 57. The same method compiles against
build 58, and the API probe verifies that tint is stored on the selected item.
The game assembly is the frozen v0.111.0 build at revision `41cef1ea`.

The ABI probe resolves 1,045 Godot method references with TypeRef parents.
Unresolved references fall from 607 to 606 when the setter is added. This is
an inventory of static references, including UI methods. Generic TypeSpec
parents and dynamically bound calls are outside its scope. The inventory
supports prioritizing reachable gameplay callbacks under #149.

The fresh native control uses card and potion actions in a prepared A8 boss
fight. It observes all three native forms at 111, 212 and 313 HP, Intangible
applying and expiring in the third form, a completed third-form turn and the
native boss reward owner. All action receipts reconstruct and the worker exits
cleanly. The earlier diagnostic fight also reached rewards. Its verifier
expected Intangible in the second form, so its failed receipt is preserved.
These controls contribute zero labels and zero optimizer updates.

## Collection handoff

The saved audit retains 38 complete cases, 210 seals, 172 episodes and 12,105
native deliveries. There are 20 confirmed lessons and 14 strict goal rescues.
The seven newly sealed cases add two lessons. The Queen case adds a strict
rescue from a prepared boss start with a fresh confirming win.

The v5 recipe derives its plan from v4 and gives `fit-039-replacement-1` a
disjoint seed pool. It imports the 38 complete cases and leaves 30 slots to
collect, including that replacement. The linked denominator is 72 slots,
including the four preserved failures. The ownership and quality criteria are
inherited from v4. Grouped ordered-answer labels still require explicit
support in the future fitting recipe.

Close STS2 and run the continuation.

```bash
bash "/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/continue-win-curriculum-v5.sh"
```

This owner run collects and assesses the remaining curriculum under the
90-minute session cap. Clean seals resume through the same command. Unknown
delivery stops the run and preserves its evidence. The command makes zero
optimizer updates. Official compact delivery and Architect terminal completion
remain separate #149 qualification work.

The collector preflight imports all 210 seals and pauses before launching a
new world. Repository verification passed 2,836 tests, lint, formatting,
strict typing, C# contracts and commit hooks.

See the [verification record](evidence/native-win-curriculum-test-subject-v1.json).
