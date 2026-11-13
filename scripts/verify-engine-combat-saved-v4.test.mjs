// Optional local evidence regression: set SPIRESHIFT_COMBAT_CASE to a completed private case.
// This reads saved records and mutates memory only; no games, writes or network calls.
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { verifyCombatEvidence } from "./verify-engine-combat-saved-v4.mjs";
const casePath=process.env.SPIRESHIFT_COMBAT_CASE;
const json=file=>JSON.parse(readFileSync(file,"utf8"));
const source=casePath?(()=>{
  const native=json(path.join(casePath,"native-report.json")),shipped=json(path.join(casePath,"shipped-report.json"));
  const snapshots=readFileSync(path.join(path.dirname(native.report_path),"private-combat-snapshots.jsonl"),"utf8").trim().split("\n").map(JSON.parse);
  return {native,snapshots,shipped,scenario:json(path.join(casePath,"comparison.json")).scenario};
})():null;
const verify=d=>verifyCombatEvidence(d.native,d.snapshots,d.shipped,d.scenario);
const combat=d=>d.shipped.probe.comparisons.find(row=>row.snapshot.interaction.kind==="combat_turn");
test("completed evidence reconstructs without replay",{skip:!source},()=>assert.equal(verify(source).valid,true));
for(const [name,mutate] of [
  ["current cost",d=>combat(d).snapshot.interaction.content.context.player.hand[0].cost="99"],
  ["current effect description",d=>combat(d).snapshot.interaction.content.context.player.hand[0].description="Deal 999 damage."],
  ["status ownership",d=>d.shipped.probe.comparisons.at(-1).snapshot.interaction.content.context.player.statuses=[]],
  ["relic counter",d=>combat(d).snapshot.persistent.content.player.relics.find(r=>r.definition_id==="PEN_NIB").counter=99],
  ["snapshot denominator",d=>d.snapshots.pop()],
  ["missing public effects",d=>d.shipped.probe.comparisons.pop()],
  ["stale deck read",d=>combat(d).deckRead.observed_snapshot_id="old"],
  ["native successor",d=>d.native.probe.receipts[0].successor.snapshot_id="other"],
  ["unoffered action",d=>d.shipped.probe.deliveries[0].receipt.action.bound_action_id="not-offered"],
  ["failed delivery",d=>d.shipped.probe.receipts[0].delivery="rejected"],
  ["duplicate receipt",d=>d.native.probe.receipts[1].request_id=d.native.probe.receipts[0].request_id],
  ["another runtime",d=>combat(d).snapshot.session.runtime_instance_id="other"],
  ["unseen reshuffle",d=>d.shipped.probe.shuffle_steps=[]],
  ["reshuffle after draw",d=>d.shipped.probe.shuffle_steps[0].before.interaction.content.context.is_play_phase=true],
  ["changed seed provenance",d=>d.shipped.probe.native_provenance.actual_seed="OTHERSEED"],
]) test(`saved audit rejects changed ${name}`,{skip:!source},()=>{const data=structuredClone(source);mutate(data);assert.throws(()=>verify(data));});
