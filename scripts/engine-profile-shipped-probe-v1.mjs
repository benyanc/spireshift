// One declared benchmark profile and private potion inspection save; no gameplay or learning.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { validateLoadedIdentity, completePublicMenu } from "./engine-menu-probe.mjs";
import { profileTextFacts, firstDifference } from "./engine-profile-text-contract-v1.mjs";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export function startingOptions(snapshot) {
  const surface = snapshot?.interaction?.content?.surface;
  if (snapshot?.interaction?.kind !== "event_option" || !Array.isArray(surface?.options)
    || surface.options.length === 0) return null;
  const options = surface.options.map((option) => ({
    title: option?.title ?? option?.label,
    is_locked: typeof option?.is_locked === "boolean" ? option.is_locked
      : typeof option?.enabled === "boolean" ? !option.enabled : null
  }));
  if (options.some((option) => typeof option.title !== "string" || !option.title.trim()
    || typeof option.is_locked !== "boolean")) return null;
  return options;
}

function ownedEndpoint(spec) {
  const url = new URL(spec.endpoint);
  if (url.hostname !== "127.0.0.1" || url.protocol !== "http:" || url.pathname !== "/"
    || !url.port || url.username || url.password || url.search || url.hash) return false;
  const result = spawnSync("/usr/sbin/lsof", ["-nP", `-iTCP:${url.port}`, "-sTCP:LISTEN", "-Fp"],
    { encoding: "utf8", timeout: 2000 });
  const pids = result.stdout?.split("\n").filter((item) => /^p\d+$/u.test(item)) ?? [];
  return result.status === 0 && JSON.stringify(pids) === JSON.stringify([`p${spec.expected_pid}`]);
}

async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const started = Date.now(), deadline = started + spec.max_wall_seconds * 1000;
  const result = { checks: {}, receipts: [], menu_actions_requested: 0, shutdown_requested: false, training_allowed: false };
  let runtimeId, session;
  const check = (name, ok) => {
    result.checks[name] = ok === true;
    if (!result.checks[name]) throw new Error(`Shipped checkpoint gate failed: ${name}`);
  };
  try {
    let capabilities;
    while (Date.now() < deadline) {
      process.kill(spec.expected_pid, 0);
      try { capabilities = (await client.capabilities()).data; break; }
      catch { await pause(250); }
    }
    if (!capabilities) throw new Error("No exact shipped Host before the cap");
    runtimeId = capabilities.host.runtime_instance_id;
    result.capabilities = capabilities;
    check("loaded_identity", validateLoadedIdentity(capabilities, spec));
    check("endpoint_owned_by_child", ownedEndpoint(spec));
    session = new EnvironmentControllerSession(client, {
      productId: "spireshift-native-checkpoint", productName: "SpireShift Checkpoint Qualification", productVersion: "1"
    });
    await session.register(capabilities.host, capabilities.control);
    const stable = async (previous = null) => {
      while (Date.now() < deadline) {
        const current = (await client.observe()).data;
        result.latest_snapshot = current;
        if (completePublicMenu(current, runtimeId) && current.snapshot_id !== previous) return current;
        await pause(150);
      }
      throw new Error("No fresh complete public decision before the checkpoint cap");
    };
    let snapshot = await stable();
    for (let i = 0; i < 8 && snapshot.interaction.kind !== "event_option"; i++) {
      const actions = snapshot.bound_actions.actions;
      let action;
      if (snapshot.interaction.kind === "main_menu") {
        action = actions.find((item) => /continue|resume/i.test(item.label));
        if (action) check("native_continue_offered", true);
        else action = actions.find((item) => /single ?player|play/i.test(item.label));
      } else if (snapshot.interaction.kind === "singleplayer_menu") {
        action = actions.find((item) => /continue|resume/i.test(item.label));
        check("native_continue_offered", action != null);
      } else {
        throw new Error(`Unqualified checkpoint entry interaction: ${snapshot.interaction.kind}`);
      }
      if (!action) throw new Error("No exact native checkpoint entry action");
      const receipt = (await client.submit({ requestId: `checkpoint-entry-${randomUUID()}`,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id,
        ...await session.credentials() })).data;
      result.receipts.push(receipt);
      result.menu_actions_requested++;
      if (receipt.delivery !== "delivered") throw new Error(`Checkpoint entry delivery ${receipt.delivery}; no retry`);
      snapshot = await stable(snapshot.snapshot_id);
    }
    result.starting_snapshot = snapshot;
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true
      && snapshot.interaction.kind === "event_option");
    check("complete_public_starting_event", completePublicMenu(snapshot, runtimeId));
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ expected_runtime_instance_id: runtimeId, host_control_token: spec.host_control_token }),
      signal: AbortSignal.timeout(3000)
    });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok
      && result.native_provenance.runtime_instance_id === runtimeId
      && result.native_provenance.actual_seed === spec.fixture.seed
      && snapshot.persistent?.content?.run?.ascension === 8);
    const original = JSON.parse(readFileSync(spec.fixture.snapshot_path, "utf8"));
    result.starting_options_comparison = { managed: startingOptions(original), shipped: startingOptions(snapshot) };
    check("same_starting_public_option_titles_and_availability", result.starting_options_comparison.managed != null
      && JSON.stringify(result.starting_options_comparison.managed) === JSON.stringify(result.starting_options_comparison.shipped));
    const read = snapshot.reads.find(row => row.kind === "run_deck");
    if (!read) throw Error("No complete public deck read for profile inspection");
    result.deck_read = (await client.read(read.read_id, snapshot.snapshot_id)).data;
    result.facts = profileTextFacts(snapshot, result.deck_read);
    const canonical = JSON.parse(readFileSync(spec.fixture.canonical_path, "utf8"));
    result.first_difference = firstDifference(canonical.facts, result.facts);
    check("same_public_profile_descriptions", result.first_difference == null);
    check("native_current_act_preserved", result.facts.run.act_definition_id === canonical.facts.run.act_definition_id);
  } catch (error) { result.error = error.message; }
  finally {
    if (session) await session.close();
    if (runtimeId) {
      try {
        const shutdown = await fetch(`${spec.endpoint}/api/host-control/shutdown`, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_runtime_instance_id: runtimeId, host_control_token: spec.host_control_token }),
          signal: AbortSignal.timeout(3000)
        });
        result.shutdown_requested = shutdown.ok && (await shutdown.json()).status === "shutdown_requested";
      } catch (error) { result.shutdown_error = error.message; }
    }
    result.wall_seconds = (Date.now() - started) / 1000;
    writeFileSync(path.join(spec.attempt, "checkpoint-control.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString();
  await main(JSON.parse(input));
}
