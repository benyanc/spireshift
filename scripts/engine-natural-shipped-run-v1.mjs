// Start through real menus and Embark. No saved run is imported and no gameplay follows.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { chooseStartupAction, startingFacts, firstDifference } from "./engine-new-run-contract-v1.mjs";
import { chooseRunAction } from "./engine-run-contract-v1.mjs";
import { tutorialAction } from "./engine-journey-tutorial-v4.mjs";
import { shuffleTutorialAction } from "./engine-combat-shuffle-v1.mjs";

export async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const result = { checks: {}, snapshots: [], receipts: [], menu_actions_requested: 0, shutdown_requested: false,
    training_allowed: false, checkpoint_imported: false, optimizer_steps: 0 };
  const deadline = Date.now() + spec.max_wall_seconds * 1000;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  let runtimeId, session;
  const check = (name, ok) => { result.checks[name] = ok === true; if (ok !== true) throw Error(`New-run gate failed: ${name}`); };
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
    check("endpoint_owned_by_child", owned.status === 0 && JSON.stringify(owned.stdout.split("\n").filter(row => /^p\d+$/u.test(row))) === JSON.stringify([`p${spec.expected_pid}`]));
    session = new EnvironmentControllerSession(client, { productId: "spireshift-normal-start-qualification",
      productName: "SpireShift Normal Start Comparison", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    const stable = async previous => {
      while (Date.now() < deadline) {
        const current = (await client.observe()).data;
        result.latest_snapshot = current;
        if ((completePublicMenu(current, runtimeId) || current.interaction.kind === "game_over") && current.snapshot_id !== previous) return current;
        await pause(150);
      }
      throw Error("No fresh complete normal-start menu before cap");
    };
    let snapshot = await stable(null), embarked = false;
    for (let step = 0; snapshot.interaction.kind !== "event_option" && step < 24; step++) {
      result.snapshots.push(snapshot);
      const action = chooseStartupAction(snapshot);
      if (/^embark$/iu.test(action.label)) {
        check("Ironclad_A8_selected", snapshot.interaction.content.surface.ascension === 8);
        embarked = true;
      }
      const receipt = (await client.submit({ requestId: `new-run-${randomUUID()}`, expectedSnapshotId: snapshot.snapshot_id,
        boundActionId: action.bound_action_id, ...await session.credentials() })).data;
      result.receipts.push({ before: snapshot, action, receipt }); result.menu_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId) throw Error("Unknown normal-start delivery; no retry");
      snapshot = await stable(snapshot.snapshot_id);
    }
    check("no_continue_used", result.receipts.every(row => !/continue|resume/iu.test(row.action.label)));
    check("normal_new_run_embarked", embarked && snapshot.interaction.kind === "event_option");
    check("complete_public_starting_event", completePublicMenu(snapshot, runtimeId));
    const descriptor = snapshot.reads.find(row => row.kind === "run_deck");
    if (!descriptor) throw Error("No complete initial deck read");
    const deckRead = (await client.read(descriptor.read_id, snapshot.snapshot_id)).data;
    result.starting_snapshot = snapshot; result.deck_read = deckRead;
    const original = JSON.parse(readFileSync(spec.fixture.native_observation, "utf8"));
    result.facts = startingFacts(snapshot, deckRead); result.expected_facts = startingFacts(original.snapshot, original.reads.find(row => row.kind === "run_deck"));
    result.first_difference = firstDifference(result.expected_facts, result.facts);
    check("same_public_initial_run_facts", result.first_difference == null);
    check("same_starting_public_option_titles_and_availability", firstDifference(result.expected_facts.options, result.facts.options) == null);
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ expected_runtime_instance_id: runtimeId, host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === spec.fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId);
    result.gameplay = { decisions: 0, tutorials: 0, maximum_floor: 1, terminal: false, victory: false, families: {} };
    while (Date.now() < deadline && result.gameplay.decisions < 4096) {
      const kind = snapshot.interaction.kind;
      result.gameplay.maximum_floor = Math.max(result.gameplay.maximum_floor, snapshot.persistent?.content?.run?.floor ?? 0);
      result.gameplay.families[kind] = (result.gameplay.families[kind] ?? 0) + 1;
      if (kind === "game_over") {
        if (typeof snapshot.interaction.content.surface.victory !== "boolean") throw Error("No explicit shipped terminal result");
        result.gameplay.terminal = true; result.gameplay.victory = snapshot.interaction.content.surface.victory;
        result.terminal_snapshot = snapshot; break;
      }
      let action;
      if (kind === "tutorial") {
        const id = snapshot.interaction.content.surface.tutorial_id;
        if (id === "shuffle_ftue") action = shuffleTutorialAction(snapshot);
        else if (id === "combat_rules_ftue") action = tutorialAction(snapshot);
        else if (["rest_site_ftue", "obtain_relic_ftue", "obtain_potion_ftue"].includes(id) && snapshot.bound_actions.actions.length === 1)
          action = snapshot.bound_actions.actions[0];
        else throw Error(`Unsupported natural-run tutorial ${id}`);
        result.gameplay.tutorials++;
      } else action = chooseRunAction(snapshot);
      const receipt = (await client.submit({ requestId: `natural-shipped-${randomUUID()}`, expectedSnapshotId: snapshot.snapshot_id,
        boundActionId: action.bound_action_id, ...await session.credentials() })).data;
      result.receipts.push({ before: snapshot, action, receipt }); result.gameplay.decisions++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId) throw Error("Unknown natural-run delivery; no retry");
      snapshot = await stable(snapshot.snapshot_id);
    }
    check("natural_full_run_observed", result.gameplay.terminal === true);

  } catch (error) { result.error = error.message; }
  finally {
    if (session) await session.close();
    if (runtimeId) {
      try {
        const shutdown = await fetch(`${spec.endpoint}/api/host-control/shutdown`, { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_runtime_instance_id: runtimeId, host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
        result.shutdown_requested = shutdown.ok && (await shutdown.json()).status === "shutdown_requested";
      } catch (error) { result.shutdown_error = error.message; }
    }
    writeFileSync(path.join(spec.attempt, "checkpoint-control.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  if (result.error || !result.shutdown_requested) process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
