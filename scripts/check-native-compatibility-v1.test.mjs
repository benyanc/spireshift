import test from "node:test";
import assert from "node:assert/strict";
import { projectPair } from "./check-native-compatibility-v1.mjs";

function frame(prefix = "native") {
  const runtime = `${prefix}-runtime`, snapshotId = `${prefix}-snapshot`;
  return {
    snapshot: {
      snapshot_id: snapshotId, session: { runtime_instance_id: runtime },
      persistent: { content: { run: { ascension: 8 }, player: { hp: 20 } } },
      interaction: { kind: "event_option", content: { context: {}, surface: {} } },
      referents: [{ referent_id: `${prefix}-option`, role: "event_option", label: "Reward",
        properties: { entity_id: `${prefix}-option`, index: 0, title: "Reward" } }],
      bound_actions: { actions: [{ bound_action_id: `${prefix}-action`, verb: "activate",
        subject_referent_id: `${prefix}-option`, label: "Reward", arguments: [] }] },
      reads: [{ read_id: `${prefix}-deck`, kind: "run_deck" }]
    },
    deckRead: { kind: "run_deck", read_id: `${prefix}-deck`, expected_snapshot_id: snapshotId,
      observed_snapshot_id: snapshotId, session: { runtime_instance_id: runtime },
      content: { card_count: 0 }, completeness: { status: "complete" },
      information_policy: { includes_hidden_information: false } }
  };
}

test("host-specific temporary handles are removed without changing action semantics", () => {
  const result = projectPair("test", frame(), frame("official"));
  assert.deepEqual(result.native_input, result.official_input);
  assert.deepEqual(result.native_action_keys, result.official_action_keys);
  assert.deepEqual(result.missing_official_reads, []);
});

test("advertised but uncaptured reads stay explicit instead of becoming empty game facts", () => {
  const official = frame("official");
  official.snapshot.reads.push({ read_id: "piles", kind: "combat_piles" });
  const result = projectPair("test", frame(), official);
  assert.deepEqual(result.missing_official_reads, ["combat_piles"]);
});

test("stale, cross-runtime, hidden and partial reads are rejected", () => {
  for (const mutate of [
    read => { read.observed_snapshot_id = "stale"; },
    read => { read.session.runtime_instance_id = "other-process"; },
    read => { read.information_policy.includes_hidden_information = true; },
    read => { read.completeness.status = "partial"; }
  ]) {
    const official = frame("official"); mutate(official.deckRead);
    assert.throws(() => projectPair("test", frame(), official), /Stale, partial/u);
  }
});

test("different decision families cannot be relabeled as a matched observation", () => {
  const official = frame("official"); official.snapshot.interaction.kind = "rest_site";
  assert.throws(() => projectPair("test", frame(), official), /different decision families/u);
});
