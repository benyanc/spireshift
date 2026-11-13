import assert from "node:assert/strict";
import test from "node:test";
import { completedTransition, completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";

const expected = { connector: { protocol: "1.0.0", version: "1.1.0-rc.1",
  source_revision: "source", artifact_sha256: "dll", artifact_mvid: "mvid" },
target: { version: "v0.111.0", commit: "41cef1ea", runtime_main_assembly_hash: 42 } };
const capabilities = { protocol_version: "1.0.0", host: { host_kind: "headless", version: "1.1.0-rc.1",
  implementation: { source_revision: "source", artifact_sha256: "dll", module_version_id: "mvid" } },
game: { version: "v0.111.0", commit: "41cef1ea", main_assembly_hash: 42,
  compatibility: { observation_allowed: true },
  modset: { status: "exact_player_environment_only", loaded_mod_ids: ["STS2_MCP"] } },
execution_available: true };

function snapshot(id, kind) {
  return { status: "interactive", snapshot_id: id, session: { runtime_instance_id: "owned" },
    information_policy: { includes_hidden_information: false }, completeness: { status: "complete" },
    interaction: { interaction_id: id, kind }, bound_actions: {
      status: "complete", total_count: 1, materialized_count: 1,
      actions: [{ bound_action_id: id, interaction_id: id }] } };
}

test("loaded Host drift or extra Mods cannot authorize an action", () => {
  assert.equal(validateLoadedIdentity(capabilities, expected), true);
  for (const change of [
    (copy) => { copy.host.implementation.artifact_sha256 = "different"; },
    (copy) => { copy.game.main_assembly_hash = 99; },
    (copy) => { copy.host.implementation.source_revision = "other"; },
    (copy) => { copy.game.modset.loaded_mod_ids.push("other"); },
    (copy) => { copy.execution_available = false; }
  ]) {
    const copy = structuredClone(capabilities); change(copy);
    assert.equal(validateLoadedIdentity(copy, expected), false);
  }
});

test("hidden, incomplete, duplicated or different-runtime menus fail closed", () => {
  const initial = snapshot("one", "main_menu");
  assert.equal(completePublicMenu(initial, "owned"), true);
  for (const change of [
    (copy) => { copy.information_policy.includes_hidden_information = true; },
    (copy) => { copy.bound_actions.status = "truncated"; },
    (copy) => { copy.session.runtime_instance_id = "another"; },
    (copy) => { copy.bound_actions.total_count = 2; },
    (copy) => { copy.bound_actions.actions[0].interaction_id = "stale"; },
    (copy) => {
      copy.bound_actions.actions.push(copy.bound_actions.actions[0]);
      copy.bound_actions.total_count = 2; copy.bound_actions.materialized_count = 2;
    }
  ]) {
    const copy = structuredClone(initial); change(copy);
    assert.equal(completePublicMenu(copy, "owned"), false);
  }
});

test("delivery alone or an unrelated successor is not completed menu work", () => {
  const initial = snapshot("one", "main_menu");
  const next = snapshot("two", "character_select");
  const receipt = { delivery: "delivered", attribution: { runtime_instance_id: "owned" } };
  assert.equal(completedTransition(initial, next, receipt, "owned"), true);
  assert.equal(completedTransition(initial, initial, receipt, "owned"), false);
  assert.equal(completedTransition(initial, next, { ...receipt, delivery: "unknown" }, "owned"), false);
  assert.equal(completedTransition(initial, next, { ...receipt,
    attribution: { runtime_instance_id: "another" } }, "owned"), false);
  next.interaction.kind = "main_menu";
  assert.equal(completedTransition(initial, next, receipt, "owned"), false);
});
