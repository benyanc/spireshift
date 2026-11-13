// Bounded discovery is separate from clean validation and from learning experience.
import { createHash } from "node:crypto";
import { assertPublicBoundary, publicProgressKey } from "./engine-run-contract-v1.mjs";
import { actionSemantics, chooseRunAction } from "./engine-run-policy-v2.mjs";

export function currentBoundMenu(snapshot, runtimeId) {
  const menu = snapshot?.bound_actions, id = snapshot?.interaction?.interaction_id;
  return snapshot?.session?.runtime_instance_id === runtimeId
    && snapshot?.information_policy?.includes_hidden_information === false
    && menu?.status === "complete" && Array.isArray(menu.actions) && menu.actions.length > 0
    && menu.actions.length === menu.total_count && menu.actions.length === menu.materialized_count
    && new Set(menu.actions.map(row => row.bound_action_id)).size === menu.actions.length
    && menu.actions.every(row => typeof row.bound_action_id === "string" && row.bound_action_id
      && row.interaction_id === id && Array.isArray(row.arguments));
}

export function recordRunProgress(gameplay, snapshot, supported = false) {
  const run = snapshot?.persistent?.content?.run;
  if (!run) return;
  if (run.ascension !== 8) throw Error("Run ascension changed or is missing");
  for (const [source, target] of [["floor", "maximum_floor"], ["act", "maximum_act"]]) {
    if (!Number.isSafeInteger(run[source]) || run[source] < (source === "floor" ? 0 : 1)) continue;
    gameplay[target] = Math.max(gameplay[target] ?? 0, run[source]);
    if (supported) gameplay[`last_supported_${source}`] = run[source];
  }
  const player = snapshot.persistent.content.player;
  gameplay.last_observed = { snapshot_id: snapshot.snapshot_id, floor: run.floor, act: run.act,
    hp: player?.hp ?? null, max_hp: player?.max_hp ?? null,
    interaction_kind: snapshot.interaction?.kind, status: snapshot.status };
}

export function newIssueCollection() {
  return { schema_version: "engine-run-issues-v1", issues: [], observations: [], recoveries: [],
    cap: null, clean: true, training_allowed: false };
}

export function recordUnsupported(collection, snapshot, limits) {
  assertPublicBoundary(snapshot);
  const key = publicProgressKey(snapshot, []);
  if (collection.observations.some(row => row.public_state_key === key)) return;
  if (collection.observations.length >= limits.max_issue_observations) {
    collection.cap = { kind: "issue_observation_cap", snapshot };
    throw Error("Diagnostic issue-observation cap");
  }
  collection.clean = false;
  collection.observations.push({ public_state_key: key, snapshot });
  const missing = [...new Set(snapshot.completeness?.missing ?? [])].sort();
  const kind = snapshot.interaction?.kind, context = snapshot.interaction?.content?.context?.kind;
  const reason = snapshot.interaction?.content?.surface?.reason ?? "Incomplete public observation";
  for (const field of missing.length ? missing : ["unsupported_surface"]) {
    const descriptor = { kind, context, field, reason };
    const issueId = `sha256:${createHash("sha256").update(JSON.stringify(descriptor)).digest("hex")}`;
    let issue = collection.issues.find(row => row.issue_id === issueId);
    if (!issue) {
      if (collection.issues.length >= limits.max_unique_issues) {
        collection.cap = { kind: "unique_issue_cap", snapshot };
        throw Error("Diagnostic unique-issue cap");
      }
      issue = { issue_id: issueId, ...descriptor, occurrences: 0, first_snapshot_id: snapshot.snapshot_id,
        first_floor: snapshot.persistent?.content?.run?.floor ?? null };
      collection.issues.push(issue);
    }
    issue.occurrences++;
    issue.last_snapshot_id = snapshot.snapshot_id;
  }
}

export function recoveryAction(snapshot, runtimeId, limits, collection) {
  assertPublicBoundary(snapshot);
  const families = new Set(["card_reward_selection", "native_generated_card_choice", "reward_claim",
    "reward_completion", "shop_inventory", "merchant_room", "rest_site", "card_selection",
    "native_deck_card_selection", "card_bundle_selection", "treasure_completion"]);
  if (limits.mode !== "discovery" || collection.cap || !families.has(snapshot.interaction?.kind)
      || collection.recoveries.length >= limits.max_recoveries
      || !currentBoundMenu(snapshot, runtimeId) || snapshot.persistent?.content?.run?.ascension !== 8)
    return null;
  // A complete current native binding may still exist when descriptive facts are missing.
  // Only game-offered operand-free exit/decline controls are recoverable here. Unknown modals,
  // truncated menus, mandatory selections and arbitrary keypresses get no invented fallback.
  const safe = snapshot.bound_actions.actions.filter(action => !action.arguments.length
    && ["skip_card", "skip_optional", "leave_shop", "proceed", "close", "cancel"]
      .includes(actionSemantics(snapshot, action)));
  if (!safe.length) return null;
  return chooseRunAction({ ...snapshot, bound_actions: { ...snapshot.bound_actions, actions: safe } });
}

export function assertObservationIdentity(snapshot, runtimeId) {
  assertPublicBoundary(snapshot);
  if (snapshot?.session?.runtime_instance_id !== runtimeId
      || snapshot?.information_policy?.includes_hidden_information !== false)
    throw Error("Public runtime identity or information boundary changed");
}

export async function freshRunObservation(options) {
  const { observe, previous, runtimeId, deadline, gameplay, collection, limits,
    pause = ms => new Promise(resolve => setTimeout(resolve, ms)), now = Date.now } = options;
  let unsupportedSince = null;
  while (now() < deadline) {
    const current = await observe();
    assertObservationIdentity(current, runtimeId);
    recordRunProgress(gameplay, current);
    options.onObservation?.(current);
    const complete = current.completeness?.status === "complete";
    if (current.snapshot_id !== previous && complete
        && ((current.status === "interactive" && currentBoundMenu(current, runtimeId))
          || (current.interaction?.kind === "game_over" && ["observed", "interactive"].includes(current.status)))) {
      recordRunProgress(gameplay, current, true);
      return { snapshot: current, recovery: false };
    }
    if (current.status === "visible_unsupported" || current.completeness?.status === "visible_unmapped") {
      unsupportedSince ??= now();
      if (now() - unsupportedSince >= limits.unsupported_grace_ms) {
        recordUnsupported(collection, current, limits);
        const action = current.snapshot_id !== previous ? recoveryAction(current, runtimeId, limits, collection) : null;
        if (action) return { snapshot: current, recovery: true, action };
        const missing = (current.completeness?.missing ?? []).join(", ");
        throw Error(`Unsupported shipped surface: ${current.interaction?.kind}; ${current.interaction?.content?.surface?.reason ?? "unknown owner"}; missing: ${missing}; no verified recovery control`);
      }
    } else unsupportedSince = null;
    await pause(150);
  }
  throw Error("No fresh complete public menu before the run cap");
}
