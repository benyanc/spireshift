// Compare six rest actions from an explicitly privileged save fixture. Never a natural full run.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";

import { restActionKey, firstDifference, restFacts, upgradePreviewConfirmation } from "./engine-rest-bridge-contract.mjs";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const started = Date.now(), deadline = started + spec.max_wall_seconds * 1000;
  const result = { checks: {}, menu_actions_requested: 0, public_actions_requested: 0,
    semantic_actions_delivered: 0, upgrade_ui_steps: [],
    shutdown_requested: false, training_allowed: false, comparisons: [], receipts: [], privileged_fixture: true };
  let runtimeId, session;
  const check = (name, ok) => { result.checks[name] = ok === true; if (!ok) throw new Error(`Rest gate failed: ${name}`); };
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
    session = new EnvironmentControllerSession(client, { productId: "spireshift-rest-qualification",
      productName: "SpireShift Rest Action Comparison", productVersion: "1" });
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
      const receipt = (await client.submit({ requestId: `rest-${randomUUID()}`,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id,
        ...await session.credentials() })).data;
      result.receipts.push(receipt);
      if (menu) result.menu_actions_requested++; else result.public_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId)
        throw new Error(`Rest delivery ${receipt.delivery}; no retry`);
      return stable(snapshot.snapshot_id);
    };
    let snapshot = await stable();
    for (let i = 0; i < 8 && snapshot.interaction.kind !== "rest_site"; i++) {
      if (!["main_menu", "singleplayer_menu"].includes(snapshot.interaction.kind)) throw new Error("Unqualified checkpoint entry");
      const continueAction = snapshot.bound_actions.actions.find((item) => /continue|resume/i.test(item.label));
      if (continueAction) check("native_continue_offered", true);
      const action = continueAction ?? snapshot.bound_actions.actions.find((item) => /single ?player|play/i.test(item.label));
      if (!action) throw new Error("No exact checkpoint entry action");
      snapshot = await submit(snapshot, action, true);
    }
    result.starting_snapshot = snapshot;
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true && snapshot.interaction.kind === "rest_site");
    check("complete_public_rest_fixture", completePublicMenu(snapshot, runtimeId));
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
        host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === spec.fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId && snapshot.persistent.content.run.ascension === 8);
    const native = JSON.parse(readFileSync(spec.fixture.rest_report_path, "utf8"));
    const plan = native.probe.journey;
    for (let i = 0; i < plan.length; i++) {
      const descriptor = snapshot.reads.find((row) => row.kind === "run_deck");
      if (!descriptor) throw new Error("No snapshot-bound public deck view");
      const deckRead = (await client.read(descriptor.read_id, snapshot.snapshot_id)).data;
      result.latest_deck_read = deckRead;
      const facts = restFacts(snapshot, deckRead), difference = firstDifference(plan[i].facts, facts);
      result.comparisons.push({ index: i, facts, snapshot, deckRead, matched: difference == null });
      if (difference) { result.first_difference = difference; throw new Error(`Public rest divergence at ${difference.field}`); }
      if (plan[i].action == null) break;
      const matches = snapshot.bound_actions.actions.filter((action) => !firstDifference(restActionKey(snapshot, action), plan[i].action));
      if (matches.length !== 1) throw new Error("Native rest action does not bind uniquely in the shipped menu");
      const before = snapshot;
      snapshot = await submit(snapshot, matches[0]);
      if (matches[0].verb === "select") {
        result.upgrade_preview_snapshot = snapshot;
        const previewRead = snapshot.reads.find((row) => row.kind === "run_deck");
        if (!previewRead) throw new Error("No current preview deck view");
        const previewDeck = (await client.read(previewRead.read_id, snapshot.snapshot_id)).data;
        result.upgrade_preview_deck_read = previewDeck;
        const confirm = upgradePreviewConfirmation(before, deckRead, snapshot, previewDeck, plan[i + 1].facts.player.deck[0]);
        result.upgrade_ui_steps.push({ index: i, before, preview: snapshot, deckRead: previewDeck,
          selected_action: matches[0], confirm_action: confirm, public_game_facts_unchanged: true });
        snapshot = await submit(snapshot, confirm);
      }
      result.semantic_actions_delivered++;
    }
    check("rest_all_snapshots_match", result.comparisons.length === plan.length && result.comparisons.every((row) => row.matched));
    check("rest_all_actions_delivered", result.semantic_actions_delivered === plan.length - 1
      && result.upgrade_ui_steps.length === 1 && result.public_actions_requested === plan.length);
    check("rest_final_map_observed", snapshot.interaction.kind === "map_navigation");
    check("rest_heal_and_upgrade_observed", result.comparisons.at(-1).facts.player.hp > 25
      && result.comparisons.at(-1).facts.player.deck.length === 1 && result.comparisons.at(-1).facts.player.deck[0].is_upgraded === true);
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
