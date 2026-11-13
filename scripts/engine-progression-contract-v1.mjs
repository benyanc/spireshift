// Scoped transition facts. These fixtures never establish playing strength or full state parity.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";
import { shippedEnding } from "./engine-natural-shipped-contract-v1.mjs";
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { naturalTutorialAction } from "./engine-natural-tutorial-v3.mjs";

export function progressionFacts(snapshot, runtimeId) {
  assertPublicBoundary(snapshot);
  const run = snapshot.persistent?.content?.run, player = snapshot.persistent?.content?.player;
  if (snapshot.session?.runtime_instance_id !== runtimeId
      || snapshot.information_policy?.includes_hidden_information !== false
      || snapshot.completeness?.status !== "complete"
      || run?.ascension !== 8 || player?.character_definition_id !== "IRONCLAD"
      || !Number.isSafeInteger(run.act) || run.act < 1 || run.act > 3
      || typeof run.act_definition_id !== "string") throw Error("Incomplete public A8 progression facts");
  return { act: run.act, act_definition_id: run.act_definition_id,
    kind: snapshot.interaction.kind, ending: shippedEnding(snapshot, runtimeId), hp: player.hp,
    event_id: snapshot.interaction.content.context?.event_id ?? null };
}

export function transitionTarget(snapshot, runtimeId, act, target) {
  const facts = progressionFacts(snapshot, runtimeId);
  if (facts.act !== target.act || facts.act_definition_id !== target.act_definition_id) return false;
  return act < 3 ? facts.kind === "map_navigation" && facts.ending === null
    : facts.kind === "game_over" && facts.ending?.victory === true;
}

export function progressionAction(snapshot, sourceAct, phase) {
  const actions = snapshot.bound_actions.actions, kind = snapshot.interaction.kind;
  let choices;
  if (phase === "entry") {
    if (!["main_menu", "singleplayer_menu"].includes(kind)) throw Error(`Unsupported fixture entry: ${kind}`);
    choices = actions.filter(row => /continue|resume/iu.test(row.label));
    if (!choices.length && kind === "main_menu") choices = actions.filter(row => /single ?player|^play$/iu.test(row.label));
  } else if (phase === "proceed") {
    if (!["reward_claim", "reward_completion"].includes(kind)) throw Error(`Unsupported before-Proceed fixture: ${kind}`);
    choices = actions.filter(row => /^proceed$/iu.test(row.label));
  } else if (phase === "architect" && sourceAct === 3) {
    if (kind !== "event_option" || snapshot.interaction.content.context?.event_id !== "THE_ARCHITECT")
      throw Error(`Unsupported Architect fixture: ${kind}`);
    choices = actions;
  }
  if (!choices?.length || (phase !== "architect" && choices.length !== 1))
    throw Error("No unambiguous current progression fixture control");
  return choices[0];
}

export function verifyProgressionTrace(control, fixture) {
  if (control.error || !control.shutdown_requested || !control.capabilities?.host?.runtime_instance_id)
    throw Error("Incomplete shipped progression control");
  const runtime = control.capabilities.host.runtime_instance_id;
  const snapshots = control.snapshots, receipts = control.receipts;
  if (!Array.isArray(snapshots) || !snapshots.length || snapshots.length !== receipts.length + 1)
    throw Error("Incomplete progression observation/delivery chain");
  let proceed = 0, architect = 0;
  for (let i = 0; i < receipts.length; i++) {
    const row = receipts[i], snapshot = snapshots[i];
    if (JSON.stringify(snapshot) !== JSON.stringify(row.before)
        || row.receipt?.delivery !== "delivered" || row.receipt.attribution?.runtime_instance_id !== runtime
        || row.expected_snapshot_id !== snapshot.snapshot_id
        || row.receipt.action?.bound_action_id !== row.action.bound_action_id
        || !completePublicMenu(snapshot, runtime)
        || !snapshot.bound_actions.actions.some(action => JSON.stringify(action) === JSON.stringify(row.action))
        || snapshots[i + 1].snapshot_id === snapshot.snapshot_id)
      throw Error("Unbound, uncertain or repeated progression delivery");
    const expected = row.phase === "tutorial" ? naturalTutorialAction(snapshot)
      : progressionAction(snapshot, fixture.act, row.phase);
    if (JSON.stringify(expected) !== JSON.stringify(row.action)) throw Error("Unexpected progression action");
    if (row.phase === "proceed") {
      proceed++;
      const before = progressionFacts(snapshot, runtime);
      if (before.act !== fixture.act || before.ending !== null) throw Error("Premature or wrong-source transition");
    }
    if (row.phase === "architect") architect++;
  }
  if (proceed !== 1 || (fixture.act === 3 && architect < 1)
      || new Set(receipts.map(row => row.receipt.request_id)).size !== receipts.length
      || !transitionTarget(snapshots.at(-1), runtime, fixture.act, fixture.target))
    throw Error("Missing native act/ending target");
  return { valid: true, observed_snapshots: snapshots.length, delivered_actions: receipts.length,
    proceed_actions: proceed, architect_actions: architect, privileged_fixture: true,
    natural_victories: 0, games_replayed: 0, training_allowed: false };
}
