// Replay one finite public prefix through the real game; stop at the first divergence.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { startingOptions } from "./engine-checkpoint-shipped-probe.mjs";
import { actionKey, firstDifference, journeyFacts, tutorialAction, tutorialGameFacts } from "./engine-journey-contract-v2.mjs";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const started = Date.now(), deadline = started + spec.max_wall_seconds * 1000;
  const result = { checks: {}, menu_actions_requested: 0, public_actions_requested: 0,
    shutdown_requested: false, training_allowed: false, comparisons: [], receipts: [], tutorial_steps: [] };
  let runtimeId, session;
  const check = (name, ok) => { result.checks[name] = ok === true; if (!ok) throw new Error(`Journey gate failed: ${name}`); };
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
    session = new EnvironmentControllerSession(client, { productId: "spireshift-journey-qualification",
      productName: "SpireShift First Combat Comparison", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    const stable = async (previous = null) => {
      while (Date.now() < deadline) {
        const current = (await client.observe()).data; result.latest_snapshot = current;
        if (completePublicMenu(current, runtimeId) && current.snapshot_id !== previous) return current;
        await pause(150);
      }
      throw new Error("No fresh complete decision before the cap");
    };
    const submit = async (snapshot, action, menu = false) => {
      const receipt = (await client.submit({ requestId: `journey-${randomUUID()}`,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id,
        ...await session.credentials() })).data;
      result.receipts.push(receipt);
      if (menu) result.menu_actions_requested++; else result.public_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId)
        throw new Error(`Journey delivery ${receipt.delivery}; no retry`);
      return stable(snapshot.snapshot_id);
    };
    let snapshot = await stable();
    for (let i = 0; i < 8 && snapshot.interaction.kind !== "event_option"; i++) {
      if (!["main_menu", "singleplayer_menu"].includes(snapshot.interaction.kind)) throw new Error("Unqualified checkpoint entry");
      const continueAction = snapshot.bound_actions.actions.find((item) => /continue|resume/i.test(item.label));
      if (continueAction) check("native_continue_offered", true);
      const action = continueAction ?? snapshot.bound_actions.actions.find((item) => /single ?player|play/i.test(item.label));
      if (!action) throw new Error("No exact checkpoint entry action");
      snapshot = await submit(snapshot, action, true);
    }
    result.starting_snapshot = snapshot;
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true && snapshot.interaction.kind === "event_option");
    check("complete_public_starting_event", completePublicMenu(snapshot, runtimeId));
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ expected_runtime_instance_id: runtimeId,
        host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === spec.fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId && snapshot.persistent.content.run.ascension === 8);
    const original = JSON.parse(readFileSync(spec.fixture.snapshot_path, "utf8"));
    result.starting_options_comparison = { managed: startingOptions(original), shipped: startingOptions(snapshot) };
    check("same_starting_public_option_titles_and_availability", result.starting_options_comparison.managed != null
      && firstDifference(result.starting_options_comparison.managed, result.starting_options_comparison.shipped) == null);
    const plan = JSON.parse(readFileSync(spec.fixture.journey_report_path, "utf8")).probe.journey;
    for (let i = 0; i < plan.length; i++) {
      // A fresh profile shows the exact three-page combat tutorial. Each native UI
      // step is recorded, bounded and checked for unchanged public game facts.
      for (let page = 0; snapshot.interaction.kind === "tutorial" && page < 3; page++) {
        const before = snapshot;
        const action = tutorialAction(before);
        const underlying = tutorialGameFacts(before);
        const expected = { ...plan[i].facts }; delete expected.actions;
        const beforeDifference = firstDifference(expected, underlying);
        if (beforeDifference) { result.first_divergence = { index: i, tutorial: true, ...beforeDifference }; throw new Error("Tutorial underlying game state differs"); }
        snapshot = await submit(before, action, true);
        const afterDifference = firstDifference(underlying, tutorialGameFacts(snapshot));
        result.tutorial_steps.push({ before, after: snapshot, game_facts_unchanged: afterDifference == null });
        if (afterDifference) { result.first_divergence = { index: i, tutorial: true, ...afterDifference }; throw new Error("Tutorial dismissal changed game facts"); }
      }
      // Save raw public evidence even when a field is missing; an omission is a counted failure.
      result.comparisons.push({ index: i, snapshot, matched: false });
      let facts;
      try { facts = journeyFacts(snapshot); }
      catch (error) { result.first_divergence = { index: i, field: "$public_contract", error: error.message }; throw error; }
      const difference = firstDifference(plan[i].facts, facts);
      result.comparisons[i].facts = facts;
      if (difference) { result.first_divergence = { index: i, ...difference }; throw new Error(`First divergence: ${difference.field}`); }
      result.comparisons[i].matched = true;
      if (plan[i].action == null) break;
      const matches = snapshot.bound_actions.actions.filter((action) => firstDifference(actionKey(snapshot, action), plan[i].action) == null);
      if (matches.length !== 1) throw new Error("Golden public action does not bind uniquely; no dispatch");
      snapshot = await submit(snapshot, matches[0]);
    }
    check("journey_all_snapshots_match", result.comparisons.length === plan.length && result.comparisons.every((row) => row.matched));
    check("journey_all_actions_delivered", result.public_actions_requested === plan.length - 1);
    check("journey_second_turn_observed", snapshot.interaction.kind === "combat_turn" && journeyFacts(snapshot).combat.round === 2);
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
