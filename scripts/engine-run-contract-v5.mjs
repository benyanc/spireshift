import { projectRunSurface as previous } from "./engine-run-contract-v4.mjs";
import { projectExactSelectionShopSurface } from "./engine-selection-shop-surface-v2.mjs";
import { appendPotionControls } from "./engine-potion-surface-v1.mjs";
import { inspectRunInput, publicProgressKey } from "./engine-run-contract-v4.mjs";
import { chooseRunAction, newDiagnosticNavigation, recordDiagnosticNavigation } from "./engine-run-policy-v6.mjs";
import { recordRunProgress } from "./engine-run-diagnostics-v1.mjs";
export { inspectRunInput, checkNativeEnding, publicProgressKey } from "./engine-run-contract-v4.mjs";

export function projectRunSurface(state, ctx, helpers) {
  // Existing reward-full-belt controls are replaced by the same exact global belt controls.
  const menu = { ...ctx, action(value) {
    if (state.decision !== "combat_play" && value.raw?.action === "discard_potion") return;
    ctx.action(value);
  } };
  let result;
  if (state.decision === "merchant_approach") {
    const complete = typeof state.room_ref === "string" && !!state.room_ref
      && typeof state.merchant_ref === "string" && !!state.merchant_ref && state.inventory_open === false;
    if (complete) {
      ctx.action({ verb: "activate", label: "Open inventory", raw: { cmd: "action", action: "open_shop", args: { room_ref: state.room_ref } } });
      ctx.action({ verb: "close", label: "Leave shop", raw: { cmd: "action", action: "leave_shop", args: { room_ref: state.room_ref } } });
    }
    result = { kind: "shop_inventory", stage: "choosing", prompt: null,
      surface: { kind: "shop_inventory", stage: "choosing", inventory_open: false, cards: [], relics: [], potions: [], card_removal: null },
      context: { kind: "shop", run: state.context, player: helpers.withoutDeck(state.player) },
      complete, missing: complete ? [] : ["native_merchant_approach_binding"],
      visibleInformation: "current_native_merchant_approach", interactionDiscovery: "version_bound_merchant_open_close_and_target" };
  } else if (["shop", "card_select"].includes(state.decision)) result = projectExactSelectionShopSurface(state, menu, helpers);
  else result = previous(state, menu, helpers);
  return appendPotionControls(state, ctx, helpers, result);
}

export async function driveRun(session, options) {
  const { seed, runtimeId, maxDecisions, maxRepeatedStates, wholeRunBudget, onRecord = () => {} } = options;
  const result = { status: "incomplete", decisions: 0, maximum_floor: 0, maximum_act: 0,
    decision_families: {}, policy_cpu_seconds: 0, victory: false, terminal: false };
  const seen = new Map();
  const agentStarted = process.cpuUsage();
  const navigation = newDiagnosticNavigation();
  let snapshot = await session.mount({ seed });
  for (;;) {
    const reads = snapshot.reads.map(row => session.read({ readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id }));
    // Record even an unsupported observation before rejecting it.
    const record = { index: result.decisions, snapshot, reads, action: null, receipt: null };
    onRecord(record, "observation");
    recordRunProgress(result, snapshot);
    let facts;
    try { facts = inspectRunInput(snapshot, reads, runtimeId); }
    catch (error) { result.status = "unsupported"; result.error = error.message; return result; }
    recordRunProgress(result, snapshot, true);
    result.maximum_floor = Math.max(result.maximum_floor, facts.floor);
    result.maximum_act = Math.max(result.maximum_act, facts.act);
    result.decision_families[snapshot.interaction.kind] = (result.decision_families[snapshot.interaction.kind] ?? 0) + 1;
    const agentUsed = process.cpuUsage(agentStarted);
    result.agent_cpu_seconds = (agentUsed.user + agentUsed.system) / 1e6;
    if (result.agent_cpu_seconds > wholeRunBudget) return { ...result, status: "compute_cap" };
    if (facts.terminal) return { ...result, status: "candidate_terminal", terminal: true, victory: facts.victory };
    if (result.decisions >= maxDecisions) return { ...result, status: "decision_cap" };
    const key = publicProgressKey(snapshot, reads), count = (seen.get(key) ?? 0) + 1;
    seen.set(key, count);
    if (count > maxRepeatedStates) return { ...result, status: "liveness_failure" };
    const started = process.cpuUsage();
    const action = chooseRunAction(snapshot, undefined, navigation);
    const used = process.cpuUsage(started);
    result.policy_cpu_seconds += (used.user + used.system) / 1e6;
    const choiceUsed = process.cpuUsage(agentStarted);
    result.agent_cpu_seconds = (choiceUsed.user + choiceUsed.system) / 1e6;
    if (result.agent_cpu_seconds > wholeRunBudget) return { ...result, status: "compute_cap" };
    record.action = action;
    onRecord(record, "action");
    const receipt = await session.submit({ requestId: `native-run-${result.decisions}`,
      expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id, timeoutMs: 15000 });
    recordDiagnosticNavigation(navigation, snapshot, action, receipt);
    record.receipt = receipt;
    onRecord(record, "receipt");
    result.decisions++;
    if (receipt.delivery !== "delivered" || !receipt.successor) {
      return { ...result, status: "delivery_failure", error: receipt.reason_code ?? receipt.delivery };
    }
    snapshot = receipt.successor;
  }
}
