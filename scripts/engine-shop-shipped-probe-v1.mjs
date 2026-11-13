// Scoped shop purchases and removal through current public controls, with a fresh profile.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";

import { shopActionKey, firstDifference, shopFacts, shopPersistentFacts, shopRoomAction, removalUiAction, verifyShopEffects, potionTutorialAction, verifyPotionTutorialEffect } from "./engine-shop-bridge-contract.mjs";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const started = Date.now(), deadline = started + spec.max_wall_seconds * 1000;
  const result = { checks: {}, menu_actions_requested: 0, public_actions_requested: 0,
    semantic_actions_delivered: 0, shop_ui_steps: [], potion_tutorial_steps: [], tutorial_actions_requested: 0,
    shutdown_requested: false, training_allowed: false, comparisons: [], receipts: [], privileged_fixture: true };
  let runtimeId, session;
  const check = (name, ok) => { result.checks[name] = ok === true; if (!ok) throw new Error(`Shop gate failed: ${name}`); };
  try {
    let capabilities;
    while (Date.now() < deadline) {
      process.kill(spec.expected_pid, 0);
      try { capabilities = (await client.capabilities()).data; break; }
      catch { await pause(250); }
    }
    if (!capabilities) throw new Error("No exact shipped Host before the cap");
    runtimeId = capabilities.host.runtime_instance_id; result.capabilities = capabilities;
    check("loaded_identity", validateLoadedIdentity(capabilities, spec));
    const endpoint = new URL(spec.endpoint);
    check("loopback_endpoint", endpoint.hostname === "127.0.0.1" && endpoint.protocol === "http:"
      && endpoint.pathname === "/" && endpoint.port && !endpoint.username && !endpoint.password && !endpoint.search && !endpoint.hash);
    const owned = spawnSync("/usr/sbin/lsof", ["-nP", `-iTCP:${endpoint.port}`, "-sTCP:LISTEN", "-Fp"], { encoding: "utf8", timeout: 2000 });
    check("endpoint_owned_by_child", owned.status === 0
      && JSON.stringify(owned.stdout?.split("\n").filter((row) => /^p\d+$/u.test(row))) === JSON.stringify([`p${spec.expected_pid}`]));
    session = new EnvironmentControllerSession(client, { productId: "spireshift-shop-qualification",
      productName: "SpireShift Shop Action Comparison", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    const stable = async (previous = null) => {
      let candidateId = null, stableSince = 0;
      while (Date.now() < deadline) {
        const current = (await client.observe()).data; result.latest_snapshot = current;
        if (completePublicMenu(current, runtimeId) && current.snapshot_id !== previous) {
          if (candidateId !== current.snapshot_id) { candidateId = current.snapshot_id; stableSince = Date.now(); }
          else if (Date.now() - stableSince >= 600) return current;
        } else { candidateId = null; stableSince = 0; }
        await pause(150);
      }
      throw new Error("No fresh complete decision before the cap");
    };
    const submit = async (snapshot, action, menu = false) => {
      const receipt = (await client.submit({ requestId: `shop-${randomUUID()}`,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id,
        ...await session.credentials() })).data;
      result.receipts.push(receipt);
      if (menu) result.menu_actions_requested++; else result.public_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId)
        throw new Error(`Shop delivery ${receipt.delivery}; no retry`);
      return stable(snapshot.snapshot_id);
    };
    const deck = async (snapshot) => {
      const descriptor = snapshot.reads.find((row) => row.kind === "run_deck");
      if (!descriptor) throw new Error("No snapshot-bound public deck view");
      return (await client.read(descriptor.read_id, snapshot.snapshot_id)).data;
    };
    let snapshot = await stable();
    for (let i = 0; i < 8 && snapshot.interaction.kind !== "shop_room"; i++) {
      if (!["main_menu", "singleplayer_menu"].includes(snapshot.interaction.kind))
        throw new Error("Unqualified shop checkpoint entry/modal; no automatic dismissal");
      const candidates = snapshot.bound_actions.actions.filter((item) => /continue|resume/i.test(item.label));
      if (candidates.length > 1) throw new Error("Ambiguous native Continue control");
      if (candidates.length === 1) check("native_continue_offered", true);
      const action = candidates[0] ?? snapshot.bound_actions.actions.find((item) => /single ?player|play/i.test(item.label));
      if (!action) throw new Error("No exact checkpoint entry action");
      snapshot = await submit(snapshot, action, true);
    }
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true && snapshot.interaction.kind === "shop_room");
    const entry = snapshot, entryDeck = await deck(entry), openAction = shopRoomAction(entry, "open");
    snapshot = await submit(entry, openAction);
    const firstDeck = await deck(snapshot);
    if (snapshot.interaction.kind !== "shop_inventory"
        || firstDifference(shopPersistentFacts(entry, entryDeck), shopPersistentFacts(snapshot, firstDeck)))
      throw new Error("Opening the merchant changed public game facts");
    result.shop_ui_steps.push({ kind: "open_inventory", before: entry, beforeDeck: entryDeck,
      after: snapshot, afterDeck: firstDeck, action: openAction, public_game_facts_unchanged: true });
    result.starting_snapshot = snapshot;
    check("complete_public_shop_fixture", completePublicMenu(snapshot, runtimeId));
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
        host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === spec.fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId && snapshot.persistent.content.run.ascension === 8);
    const native = JSON.parse(readFileSync(spec.fixture.shop_report_path, "utf8"));
    const plan = native.probe.journey;
    for (let i = 0; i < plan.length; i++) {
      const deckRead = await deck(snapshot); result.latest_deck_read = deckRead;
      const facts = shopFacts(snapshot, deckRead), difference = firstDifference(plan[i].facts, facts);
      result.comparisons.push({ index: i, facts, snapshot, deckRead, matched: difference == null });
      if (difference) { result.first_difference = difference; throw new Error(`Public shop divergence at ${difference.field}`); }
      if (plan[i].action == null) break;
      const matches = snapshot.bound_actions.actions.filter((action) => !firstDifference(shopActionKey(snapshot, action), plan[i].action));
      if (matches.length !== 1) throw new Error("Native shop action does not bind uniquely in the current shipped menu");
      const before = snapshot, chosenAction = matches[0];
      snapshot = await submit(before, chosenAction);
      if (snapshot.interaction.kind === "tutorial") {
        const tutorialBefore = snapshot, tutorialDeck = await deck(snapshot);
        const tutorialAction = potionTutorialAction(tutorialBefore);
        snapshot = await submit(tutorialBefore, tutorialAction);
        result.tutorial_actions_requested++;
        const afterDeck = await deck(snapshot);
        verifyPotionTutorialEffect(tutorialBefore, tutorialDeck, snapshot, afterDeck);
        result.potion_tutorial_steps.push({ index: i, before: tutorialBefore, beforeDeck: tutorialDeck,
          after: snapshot, afterDeck, action: tutorialAction, public_game_facts_unchanged: true });
      }
      if (chosenAction.verb === "select") {
        for (const phase of ["preview"]) {
          const currentDeck = await deck(snapshot);
          const action = removalUiAction(before, deckRead, snapshot, currentDeck, chosenAction, phase);
          const current = snapshot;
          snapshot = await submit(current, action);
          result.shop_ui_steps.push({ kind: `removal_${phase}`, index: i, before, beforeDeck: deckRead,
            current, currentDeck, selected_action: chosenAction, action, after: snapshot,
            public_game_facts_unchanged_before_commit: true });
        }
      } else if (plan[i].action.verb === "close") {
        const current = snapshot, currentDeck = await deck(current);
        const proceed = shopRoomAction(current, "proceed");
        if (firstDifference(shopPersistentFacts(before, deckRead), shopPersistentFacts(current, currentDeck)))
          throw new Error("Closing the inventory changed public game facts");
        snapshot = await submit(current, proceed);
        result.shop_ui_steps.push({ kind: "proceed_to_map", index: i, before, beforeDeck: deckRead,
          current, currentDeck, action: proceed, after: snapshot, public_game_facts_unchanged_before_commit: true });
      }
      result.semantic_actions_delivered++;
    }
    check("shop_all_snapshots_match", result.comparisons.length === plan.length && result.comparisons.every((row) => row.matched));
    check("shop_all_actions_delivered", result.semantic_actions_delivered === plan.length - 1
      && result.shop_ui_steps.length === 3 && result.public_actions_requested === plan.length + 3);
    check("shop_fresh_potion_tutorial_delivered", result.potion_tutorial_steps.length === 1
      && result.tutorial_actions_requested === 1 && result.potion_tutorial_steps[0].index ===
        (spec.fixture.scenario === "ordinary-purchases-removal" ? 1 : 2));
    check("shop_final_map_observed", snapshot.interaction.kind === "map_navigation");
    check("shop_purchase_removal_and_exit_effects", verifyShopEffects(spec.fixture.scenario, result.comparisons.map((row, i) => ({ ...row, action: plan[i].action }))));
  } catch (error) { result.error = error.message; }
  finally {
    if (session) await session.close();
    if (runtimeId) {
      try {
        const response = await fetch(`${spec.endpoint}/api/host-control/shutdown`, { method: "POST",
          headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
            host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
        result.shutdown_requested = response.ok && (await response.json()).status === "shutdown_requested";
      } catch (error) { result.shutdown_error = error.message; }
    }
    result.wall_seconds = (Date.now() - started) / 1000;
    writeFileSync(path.join(spec.attempt, "checkpoint-control.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
