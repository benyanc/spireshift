// Replay a privileged serialized pickup fixture through current reward/shop/event controls.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { shopRoomAction, potionTutorialAction, verifyPotionTutorialEffect } from "./engine-shop-bridge-contract.mjs";
import { rewardFacts, rewardActionKey, chooseRewardAction, verifyRewardEffects, firstDifference } from "./engine-reward-bridge-contract-v1.mjs";
import { shopPersistentFacts } from "./engine-shop-bridge-contract.mjs";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500), deadline = Date.now() + spec.max_wall_seconds * 1000;
  const result = { checks: {}, menu_actions_requested: 0, public_actions_requested: 0,
    semantic_actions_delivered: 0, shutdown_requested: false, training_allowed: false,
    comparisons: [], receipts: [], tutorial_steps: [], entry_steps: [] };
  const check = (name, ok) => { result.checks[name] = ok === true; if (!ok) throw Error(`Reward shipped gate failed: ${name}`); };
  let runtimeId, session;
  try {
    let capabilities;
    while (Date.now() < deadline) {
      process.kill(spec.expected_pid, 0);
      try { capabilities = (await client.capabilities()).data; break; } catch { await pause(250); }
    }
    if (!capabilities) throw Error("No exact shipped Host before the cap");
    runtimeId = capabilities.host.runtime_instance_id; result.capabilities = capabilities;
    check("loaded_identity", validateLoadedIdentity(capabilities, spec));
    const endpoint = new URL(spec.endpoint);
    check("loopback_endpoint", endpoint.hostname === "127.0.0.1" && endpoint.protocol === "http:"
      && endpoint.pathname === "/" && endpoint.port && !endpoint.username && !endpoint.password && !endpoint.search && !endpoint.hash);
    const owned = spawnSync("/usr/sbin/lsof", ["-nP", `-iTCP:${endpoint.port}`, "-sTCP:LISTEN", "-Fp"], { encoding: "utf8", timeout: 2000 });
    check("endpoint_owned_by_child", owned.status === 0 && JSON.stringify(owned.stdout?.split("\n").filter((row) => /^p\d+$/u.test(row))) === JSON.stringify([`p${spec.expected_pid}`]));
    session = new EnvironmentControllerSession(client, { productId: "spireshift-reward-qualification", productName: "SpireShift Reward Comparison", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    const stable = async (previous = null) => {
      let id = null, since = 0;
      while (Date.now() < deadline) {
        const current = (await client.observe()).data; result.latest_snapshot = current;
        if (completePublicMenu(current, runtimeId) && current.snapshot_id !== previous) {
          if (id !== current.snapshot_id) { id = current.snapshot_id; since = Date.now(); }
          else if (Date.now() - since >= 600) return current;
        } else { id = null; since = 0; }
        await pause(150);
      }
      throw Error("No fresh complete bundle decision before the cap");
    };
    const submit = async (snapshot, action, menu = false) => {
      const receipt = (await client.submit({ requestId: `reward-${randomUUID()}`, expectedSnapshotId: snapshot.snapshot_id,
        boundActionId: action.bound_action_id, ...await session.credentials() })).data;
      result.receipts.push(receipt); if (menu) result.menu_actions_requested++; else result.public_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId) throw Error("Bundle delivery failed; no retry");
      return stable(snapshot.snapshot_id);
    };
    const deck = async (snapshot) => {
      const descriptor = snapshot.reads.find((row) => row.kind === "run_deck");
      if (!descriptor) throw Error("No public deck descriptor");
      return (await client.read(descriptor.read_id, snapshot.snapshot_id)).data;
    };
    let snapshot = await stable();
    for (let i = 0; i < 8 && ["main_menu", "singleplayer_menu"].includes(snapshot.interaction.kind); i++) {
      const continuations = snapshot.bound_actions.actions.filter((row) => /continue|resume/i.test(row.label));
      if (continuations.length > 1) throw Error("Ambiguous Continue control");
      if (continuations.length === 1) check("native_continue_offered", true);
      const action = continuations[0] ?? snapshot.bound_actions.actions.find((row) => /single ?player|play/i.test(row.label));
      if (!action) throw Error("No checkpoint entry control");
      snapshot = await submit(snapshot, action, true);
    }
    result.starting_snapshot = snapshot;
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true
      && ["event_option", "shop_room", "shop_inventory"].includes(snapshot.interaction.kind));
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
        host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === spec.fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId && snapshot.persistent.content.run.ascension === 8);
    if (snapshot.interaction.kind === "shop_room") {
      const before = snapshot, beforeDeck = await deck(before), action = shopRoomAction(before, "open");
      snapshot = await submit(before, action); const afterDeck = await deck(snapshot);
      if (firstDifference(shopPersistentFacts(before,beforeDeck),shopPersistentFacts(snapshot,afterDeck))) throw Error("Opening inventory changed persistent game facts");
      result.entry_steps.push({kind:"open_inventory",before,beforeDeck,after:snapshot,afterDeck,action});
    }
    check("complete_public_reward_fixture", completePublicMenu(snapshot,runtimeId));
    const native = JSON.parse(readFileSync(spec.fixture.reward_report_path, "utf8")), plan = native.probe.journey;
    for (let i = 0; i < plan.length; i++) {
      if (snapshot.interaction.kind === "tutorial_popup") {
        const before=snapshot, beforeDeck=await deck(before), action=potionTutorialAction(before);
        snapshot=await submit(before,action); const afterDeck=await deck(snapshot);
        verifyPotionTutorialEffect(before,beforeDeck,snapshot,afterDeck);
        result.tutorial_steps.push({index:i,before,beforeDeck,after:snapshot,afterDeck,action});
      }
      const deckRead = await deck(snapshot), facts = rewardFacts(snapshot, deckRead);
      const difference = firstDifference(plan[i].facts, facts);
      result.comparisons.push({ index: i, snapshot, deckRead, facts, matched: difference == null });
      if (difference) { result.first_difference = difference; throw Error(`Reward facts diverged at ${difference.field}`); }
      if (plan[i].action == null) break;
      const action = chooseRewardAction(snapshot,plan[i].action);
      if (firstDifference(rewardActionKey(snapshot,action),plan[i].action)) throw Error("Current reward action differs from frozen public intent");
      snapshot=await submit(snapshot,action); result.semantic_actions_delivered++;
    }
    check("reward_all_snapshots_match", result.comparisons.length===plan.length && result.comparisons.every(row=>row.matched));
    check("reward_all_actions_delivered", result.semantic_actions_delivered===plan.length-1
      && result.public_actions_requested===result.semantic_actions_delivered+result.tutorial_steps.length+result.entry_steps.length);
    check("reward_pickup_capacity_and_skip_effects", verifyRewardEffects(spec.fixture.scenario,
      result.comparisons.map((row,i)=>({facts:row.facts,action:plan[i].action}))));
    check("reward_fresh_tutorials_preserve_facts", spec.fixture.scenario.startsWith("calling-bell")
      ? result.tutorial_steps.length===0 : result.tutorial_steps.length===1);
  } catch (error) { result.error = error.message; }
  finally {
    if (session) await session.close();
    if (runtimeId) try {
      const response = await fetch(`${spec.endpoint}/api/host-control/shutdown`, { method: "POST",
        headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
          host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
      result.shutdown_requested = response.ok && (await response.json()).status === "shutdown_requested";
    } catch (error) { result.shutdown_error = error.message; }
    writeFileSync(path.join(spec.attempt, "checkpoint-control.json"), JSON.stringify(result, null, 2) + "\n");
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
