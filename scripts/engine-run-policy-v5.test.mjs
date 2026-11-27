import test from "node:test";
import assert from "node:assert/strict";
import { chooseRunAction, newDiagnosticNavigation, recordDiagnosticNavigation } from "./engine-run-policy-v5.mjs";

function rewardMenu(cardIds = ["offer-a"], otherRewards = true, floor = 2) {
  const referents = cardIds.map(id => ({ referent_id: id, role: "reward",
    properties: { kind: "card", label: "Add a card to your deck.", enabled: true } }));
  if (otherRewards) referents.push({ referent_id: "gold", role: "reward",
    properties: { kind: "gold", label: "10 Gold", enabled: true } });
  return { interaction: { kind: "reward_claim" }, persistent: { content: { run: { act: 1, floor, ascension: 8 } } },
    referents, bound_actions: { actions: [
      ...referents.map(item => ({ verb: "activate", label: `Claim ${item.properties.label}`,
        subject_referent_id: item.referent_id, bound_action_id: `claim-${item.referent_id}`, arguments: [] })),
      { verb: "activate", label: "Proceed", bound_action_id: "proceed", arguments: [] },
    ] } };
}

function skipMenu(floor = 2) {
  return { interaction: { kind: "card_reward_selection" },
    persistent: { content: { run: { act: 1, floor, ascension: 8 } } },
    referents: [{ referent_id: "skip", role: "option", properties: { label: "Skip" } }],
    bound_actions: { actions: [{ verb: "activate", label: "Skip", subject_referent_id: "skip",
      bound_action_id: "skip", arguments: [] }] } };
}

function decline(navigation, menu, offerIndex = 0) {
  recordDiagnosticNavigation(navigation, menu, menu.bound_actions.actions[offerIndex], { delivery: "delivered" });
  const child = skipMenu(menu.persistent.content.run.floor);
  recordDiagnosticNavigation(navigation, child, child.bound_actions.actions[0], { delivery: "delivered" });
}

test("Skip on a reopened card reward allows collecting other rewards and then proceeding", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu();
  decline(navigation, menu);
  assert.equal(chooseRunAction(menu, undefined, navigation).subject_referent_id, "gold");
  assert.equal(chooseRunAction(rewardMenu(["offer-a"], false), undefined, navigation).bound_action_id, "proceed");
});

test("same-text card reward instances can each be inspected and declined", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu(["offer-a", "offer-b"], false);
  decline(navigation, menu);
  assert.equal(chooseRunAction(menu, undefined, navigation).subject_referent_id, "offer-b");
  decline(navigation, menu, 1);
  assert.equal(chooseRunAction(menu, undefined, navigation).bound_action_id, "proceed");
  assert.equal(navigation.declined_card_rewards.length, 2);
});

test("new floors and new games do not inherit an earlier reward decline", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu(["offer-a"], false);
  decline(navigation, menu);
  assert.equal(chooseRunAction(rewardMenu(["offer-a"], false, 3), undefined, navigation).subject_referent_id, "offer-a");
  assert.equal(chooseRunAction(menu, undefined, newDiagnosticNavigation()).subject_referent_id, "offer-a");
});

test("taking a card and unknown delivery never manufacture a declined offer", () => {
  for (const stage of ["claim", "skip", "take"]) {
    const navigation = newDiagnosticNavigation(), menu = rewardMenu();
    recordDiagnosticNavigation(navigation, menu, menu.bound_actions.actions[0],
      { delivery: stage === "claim" ? "unknown" : "delivered" });
    const child = skipMenu();
    if (stage === "take") {
      child.referents.push({ referent_id: "card", role: "card", properties: { name: "Strike" } });
      child.bound_actions.actions = [{ verb: "select", label: "Take Strike", subject_referent_id: "card", arguments: [] }];
    }
    recordDiagnosticNavigation(navigation, child, child.bound_actions.actions[0],
      { delivery: stage === "skip" ? "unknown" : "delivered" });
    assert.equal(navigation.declined_card_rewards.length, 0);
  }
});

test("a tutorial between opening an offer and Skip preserves its public association", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu();
  recordDiagnosticNavigation(navigation, menu, menu.bound_actions.actions[0], { delivery: "delivered" });
  const child = skipMenu();
  recordDiagnosticNavigation(navigation, { ...child, interaction: { kind: "tutorial" } },
    { verb: "activate", label: "Got it!" }, { delivery: "delivered" });
  recordDiagnosticNavigation(navigation, child, child.bound_actions.actions[0], { delivery: "delivered" });
  assert.equal(chooseRunAction(menu, undefined, navigation).subject_referent_id, "gold");
});

test("an unrelated skip or another room cannot decline an earlier card offer", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu();
  const skip = skipMenu();
  recordDiagnosticNavigation(navigation, skip, skip.bound_actions.actions[0], { delivery: "delivered" });
  assert.equal(navigation.declined_card_rewards.length, 0);
  recordDiagnosticNavigation(navigation, menu, menu.bound_actions.actions[0], { delivery: "delivered" });
  const later = skipMenu(3);
  recordDiagnosticNavigation(navigation, later, later.bound_actions.actions[0], { delivery: "delivered" });
  assert.equal(navigation.declined_card_rewards.length, 0);
});

test("a custom scorer can revisit a declined offer without restrictions", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu(); decline(navigation, menu);
  assert.equal(chooseRunAction(menu, (_, action) => action.subject_referent_id === "offer-a" ? 100 : 0,
    navigation).subject_referent_id, "offer-a");
});

test("mandatory reward menus receive no invented Proceed or Skip", () => {
  const navigation = newDiagnosticNavigation(), menu = rewardMenu(["offer-a"], false); decline(navigation, menu);
  menu.bound_actions.actions.pop();
  assert.equal(chooseRunAction(menu, undefined, navigation).subject_referent_id, "offer-a");
  assert.equal(menu.bound_actions.actions.length, 1);
});

test("renaming public handles consistently does not decide which offer is preferred", () => {
  for (const id of ["offer-a", "entirely-new-runtime-handle"]) {
    const navigation = newDiagnosticNavigation(), menu = rewardMenu([id]); decline(navigation, menu);
    assert.equal(chooseRunAction(menu, undefined, navigation).subject_referent_id, "gold");
  }
});
