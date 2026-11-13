// Rebuild comparison facts from saved raw public snapshots and bound deck reads. No processes/games.
import { readFileSync } from "node:fs";
import { bundleFacts, bundleActionPack, choosePack, verifyBundlePreview, verifyBundleAward, firstDifference } from "./engine-bundle-bridge-contract-v3.mjs";
import { completePublicMenu } from "./engine-menu-probe.mjs";
const spec = JSON.parse(readFileSync(0, "utf8"));
const native = JSON.parse(readFileSync(spec.native_report, "utf8"));
const shipped = JSON.parse(readFileSync(spec.shipped_report, "utf8"));
const raw = readFileSync(spec.native_snapshots, "utf8").trim().split("\n").map((line) => JSON.parse(line));
const check = (ok, error) => { if (!ok) throw Error(error); };
check(native.probe.journey.length === 3 && raw.length === 3 && shipped.probe.comparisons.length === 3, "Incomplete raw prefix denominator");
for (let i = 0; i < 3; i++) {
  const facts = bundleFacts(raw[i].snapshot, raw[i].deckRead);
  check(completePublicMenu(raw[i].snapshot, `bundle-bridge-${native.probe.runtime_identity.process_id}`), "Unbound native public snapshot");
  check(!firstDifference(facts, native.probe.journey[i].facts), "Native prefix facts do not reconstruct");
  const actual = shipped.probe.comparisons[i];
  check(completePublicMenu(actual.snapshot, shipped.probe.capabilities.host.runtime_instance_id), "Unbound shipped public snapshot");
  const reconstructed = bundleFacts(actual.snapshot, actual.deckRead);
  check(!firstDifference(reconstructed, actual.facts) && !firstDifference(reconstructed, facts), "Shipped raw facts differ from the native prefix");
}
const selected = native.probe.journey[1].action.cards;
check(raw[1].snapshot.bound_actions.actions.filter((action) => !firstDifference(bundleActionPack(raw[1].snapshot, action), selected)).length === 1, "Selected native pack is ambiguous");
check(shipped.probe.bundle_ui_steps.length === 2, "Missing preview/cancel/reopen evidence");
const runtime = shipped.probe.capabilities.host.runtime_instance_id;
const delivered = (action) => ({ verb: action.verb, bound_action_id: action.bound_action_id,
  subject_referent_id: action.subject_referent_id ?? null, arguments: action.arguments });
let receiptIndex = shipped.probe.menu_actions_requested;
const checkReceipt = (action) => check(!firstDifference(delivered(action),
  delivered(shipped.probe.receipts[receiptIndex++]?.action ?? {})), "Receipt differs from the current public action");
const event = shipped.probe.comparisons[0].snapshot.bound_actions.actions.filter((row) => row.label === "Scroll Boxes");
check(event.length === 1 && native.probe.journey[0].action.title === "Scroll Boxes", "Starting option is not uniquely bound");
checkReceipt(event[0]);
check(!firstDifference(shipped.probe.bundle_ui_steps[0].before, shipped.probe.comparisons[1].snapshot), "Preview has another source snapshot");
for (const step of shipped.probe.bundle_ui_steps) {
  check(completePublicMenu(step.before, runtime) && completePublicMenu(step.preview, runtime), "Unbound preview snapshot");
  const controls = verifyBundlePreview(step.before, step.beforeDeck, step.preview, step.previewDeck, selected);
  checkReceipt(choosePack(step.before, selected));
  if (step.kind === "preview_cancel") {
    check(completePublicMenu(step.after, runtime) && !firstDifference(bundleFacts(step.before, step.beforeDeck), bundleFacts(step.after, step.afterDeck)), "Canceled preview changed facts");
    checkReceipt(controls.cancel);
  } else {
    check(step.kind === "preview_confirm", "Unknown UI step");
    checkReceipt(controls.confirm);
  }
}
check(!firstDifference(shipped.probe.bundle_ui_steps[0].after, shipped.probe.bundle_ui_steps[1].before), "Reopened choice has another source snapshot");
verifyBundleAward(shipped.probe.comparisons[1].facts, shipped.probe.comparisons[2].facts, selected);
const receipts = shipped.probe.receipts;
check(receipts.length === receiptIndex && shipped.probe.menu_actions_requested === 1
  && shipped.probe.public_actions_requested === 5 && receipts.every((row) => row.delivery === "delivered"
    && row.attribution?.runtime_instance_id === runtime && row.request_id)
  && new Set(receipts.map((row) => row.request_id)).size === receipts.length, "Incomplete/unbound delivery receipts");
process.stdout.write(JSON.stringify({ valid: true, observations: 3, effect_decisions: 2,
  public_game_ui_actions: 5, preview_steps: 2, games_launched: 0, training_allowed: false }) + "\n");
