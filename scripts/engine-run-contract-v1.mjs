// A diagnostic policy over public SDK observations. No raw engine requests reach the policy.
import { createHash } from "node:crypto";
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { projectExactCombatSurface } from "./engine-combat-surface-v2.mjs";
import { projectExactBundleSurface } from "./engine-bundle-surface-v1.mjs";

const forbidden = new Set(["native_ref", "room_ref", "option_ref", "selection_ref", "raw_request",
  "seed", "rng", "draw_order", "act_sequence", "privileged_act_sequence",
  "native_game_over", "native_victory_room", "native_player_dead"]);
const kinds = new Set(["event_option", "map_navigation", "combat_turn", "rest_site",
  "shop_inventory", "card_selection", "card_bundle_selection", "reward_claim", "card_reward_selection",
  "reward_completion", "treasure_chest", "treasure_relic_selection", "treasure_completion", "game_over",
  "native_generated_card_choice"]);

export function assertPublicBoundary(value) {
  if (Array.isArray(value)) { for (const item of value) assertPublicBoundary(item); return; }
  if (value == null || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value)) {
    if (forbidden.has(key)) throw Error(`Private engine field reached public input: ${key}`);
    assertPublicBoundary(item);
  }
}

export function projectRunSurface(state, ctx, helpers) {
  if (state.decision === "generated_card_choice") {
    const missing = [];
    if (typeof state.can_skip !== "boolean" || typeof state.selection_ref !== "string"
        || !state.selection_ref || !Array.isArray(state.cards) || !state.cards.length || state.cards.length > 3
        || state.cards.some((row, index) => row.index !== index)) missing.push("native_generated_choice_binding");
    const cards = (state.cards ?? []).map((card, index) => {
      const item = ctx.referent({ role: "card", occurrence: index, label: card.name,
        properties: { index, ...helpers.cardProperties(card) } });
      if (!missing.length) ctx.action({ verb: "select", subject: item, label: `Select ${card.name}`,
        raw: { cmd: "action", action: "select_cards", args: { selection_ref: state.selection_ref, indices: String(index) } } });
      return item.properties;
    });
    if (!missing.length && state.can_skip) ctx.action({ verb: "skip", label: "Skip card choice",
      raw: { cmd: "action", action: "skip_select", args: { selection_ref: state.selection_ref } } });
    return { kind: "native_generated_card_choice", stage: "choosing", prompt: null,
      surface: { kind: "native_generated_card_choice", stage: "choosing", cards, can_skip: state.can_skip },
      context: { kind: "selection", run: state.context, player: helpers.withoutDeck(state.player) },
      complete: missing.length === 0, missing,
      visibleInformation: "native_canSkip_and_current_generated_card_options_pending_shipped_comparison",
      interactionDiscovery: "native_FromChooseACardScreen_parameter_and_exact_pending_selection" };
  }
  if (state.decision === "bundle_select") return projectExactBundleSurface(state, ctx, helpers);
  const result = projectExactCombatSurface(state, ctx, helpers);
  if (state.decision === "game_over" && typeof state.victory !== "boolean") {
    result.complete = false;
    result.missing = [...(result.missing ?? []), "explicit_native_terminal_outcome"];
  }
  return result;
}

export function inspectRunInput(snapshot, reads, runtimeId) {
  assertPublicBoundary({ snapshot, reads });
  if (snapshot?.session?.runtime_instance_id !== runtimeId
      || snapshot?.information_policy?.includes_hidden_information !== false
      || snapshot?.completeness?.status !== "complete") {
    throw Error(`Incomplete public state: ${(snapshot?.completeness?.missing ?? []).join(", ")}`);
  }
  if (!kinds.has(snapshot.interaction.kind)) throw Error(`Unsupported decision family: ${snapshot.interaction.kind}`);
  for (const read of reads) {
    if (read.expected_snapshot_id !== snapshot.snapshot_id || read.observed_snapshot_id !== snapshot.snapshot_id
        || read.completeness?.status !== "complete" || read.information_policy?.includes_hidden_information !== false)
      throw Error("Incomplete or stale public read");
  }
  const run = snapshot.persistent?.content?.run;
  if (run?.ascension !== 8 || !Number.isSafeInteger(run.floor) || run.floor < 0
      || !Number.isSafeInteger(run.act) || run.act < 1)
    throw Error("Public run identity is not fixed A8");
  if (snapshot.interaction.kind === "game_over") {
    if (snapshot.status !== "observed" || typeof snapshot.interaction.content.surface.victory !== "boolean"
        || snapshot.bound_actions.status !== "complete" || snapshot.bound_actions.total_count !== 0
        || snapshot.bound_actions.actions.length !== 0) throw Error("Unclassified terminal observation");
    return { terminal: true, victory: snapshot.interaction.content.surface.victory, floor: run.floor, act: run.act };
  }
  if (!completePublicMenu(snapshot, runtimeId)) throw Error("Incomplete current legal menu");
  return { terminal: false, victory: false, floor: run.floor, act: run.act };
}

const semantic = (value) => {
  if (Array.isArray(value)) return value.map(semantic);
  if (value == null || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).filter(([key]) => ![
    "entity_id", "player_entity_id", "referent_id", "snapshot_id", "interaction_id", "bound_action_id",
    "observed_at", "read_id", "expected_snapshot_id", "observed_snapshot_id", "session", "sequence"
  ].includes(key)).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, semantic(item)]));
};

export function publicProgressKey(snapshot, reads) {
  return createHash("sha256").update(JSON.stringify(semantic({
    persistent: snapshot.persistent, interaction: snapshot.interaction, referents: snapshot.referents,
    actions: snapshot.bound_actions.actions, reads: reads.map(row => ({ kind: row.kind, content: row.content }))
  }))).digest("hex");
}

export function chooseRunAction(snapshot) {
  // This deliberately simple initializer tests the whole interface; it is not a playing-strength claim.
  const referent = id => snapshot.referents.find(row => row.referent_id === id);
  const kind = snapshot.interaction.kind;
  const player = snapshot.persistent.content.player;
  const rank = action => {
    const item = referent(action.subject_referent_id);
    const props = item?.properties ?? {};
    if (kind === "combat_turn") {
      if (action.verb === "play") return 100 + (Number(props.stats?.damage) || 0) + (Number(props.stats?.block) || 0);
      if (action.verb === "use") return 80;
      if (action.verb === "end_turn") return 10;
      return -10; // Discard remains legal and visible, but this initializer preserves potions.
    }
    if (kind === "rest_site") {
      if (action.verb === "close") return -10;
      const heal = /heal|rest/iu.test(action.label);
      return heal ? (player.hp < player.max_hp * 0.7 ? 100 : 10) : 50;
    }
    if (kind === "shop_inventory") return action.verb === "close" ? -10 : 50;
    if (kind === "card_selection") return action.verb === "confirm" ? (action.arguments.length ? 50 : 10) : -10;
    if (kind === "card_reward_selection") return action.verb === "skip" ? -10 : 50;
    if (action.verb === "cancel" || action.verb === "skip") return -10;
    if (action.verb === "close" || action.verb === "proceed") return 0;
    return 50;
  };
  const actions = snapshot.bound_actions.actions;
  if (!actions.length) throw Error("Diagnostic policy has no legal action");
  // Stable menu order breaks equal scores; IDs and private bindings never influence preferences.
  return actions.reduce((best, action) => rank(action) > rank(best) ? action : best);
}

export function checkNativeEnding(run, identity) {
  if (run.status !== "candidate_terminal") return false;
  if (!["native_game_over", "native_victory_room", "native_player_dead"]
    .every(key => typeof identity?.[key] === "boolean")) throw Error("Missing native ending evidence");
  if (run.victory ? !(identity.native_game_over && identity.native_victory_room)
    : !((identity.native_game_over && !identity.native_victory_room) || identity.native_player_dead))
    throw Error("Wrapper ending disagrees with native game-over/death/victory-room evidence");
  return true;
}

export async function driveRun(session, options) {
  const { seed, runtimeId, maxDecisions, maxRepeatedStates, wholeRunBudget, onRecord = () => {} } = options;
  const result = { status: "incomplete", decisions: 0, maximum_floor: 0, maximum_act: 0,
    decision_families: {}, policy_cpu_seconds: 0, victory: false, terminal: false };
  const seen = new Map();
  const agentStarted = process.cpuUsage();
  let snapshot = await session.mount({ seed });
  for (;;) {
    const reads = snapshot.reads.map(row => session.read({ readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id }));
    // Record even an unsupported observation before rejecting it.
    const record = { index: result.decisions, snapshot, reads, action: null, receipt: null };
    onRecord(record, "observation");
    let facts;
    try { facts = inspectRunInput(snapshot, reads, runtimeId); }
    catch (error) { result.status = "unsupported"; result.error = error.message; return result; }
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
    const action = chooseRunAction(snapshot);
    const used = process.cpuUsage(started);
    result.policy_cpu_seconds += (used.user + used.system) / 1e6;
    const choiceUsed = process.cpuUsage(agentStarted);
    result.agent_cpu_seconds = (choiceUsed.user + choiceUsed.system) / 1e6;
    if (result.agent_cpu_seconds > wholeRunBudget) return { ...result, status: "compute_cap" };
    record.action = action;
    onRecord(record, "action");
    const receipt = await session.submit({ requestId: `native-run-${result.decisions}`,
      expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id, timeoutMs: 15000 });
    record.receipt = receipt;
    onRecord(record, "receipt");
    result.decisions++;
    if (receipt.delivery !== "delivered" || !receipt.successor) {
      return { ...result, status: "delivery_failure", error: receipt.reason_code ?? receipt.delivery };
    }
    snapshot = receipt.successor;
  }
}
