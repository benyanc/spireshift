// Import an explicit privileged before-Proceed save into the fixed app; no natural run or training.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { naturalTutorialAction } from "./engine-natural-tutorial-v3.mjs";
import { progressionAction, progressionFacts, transitionTarget, verifyProgressionTrace } from "./engine-progression-contract-v3.mjs";

export async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const fixture = spec.fixture;
  if (fixture.comparison_mode !== "progression_v5" || fixture.privileged_fixture !== true)
    throw Error("Explicit privileged progression scope required");
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500);
  const result = { checks: {}, snapshots: [], settling_observations: [], receipts: [], menu_actions_requested: 0,
    shutdown_requested: false, privileged_fixture: true, natural_victories: 0, training_allowed: false };
  const deadline = Date.now() + spec.max_wall_seconds * 1000;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  let runtimeId, session;
  const check = (name, ok) => { result.checks[name] = ok === true; if (ok !== true) throw Error(`Progression gate failed: ${name}`); };
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
    const owned = spawnSync("/usr/sbin/lsof", ["-nP", `-iTCP:${endpoint.port}`, "-sTCP:LISTEN", "-Fp"], { encoding: "utf8", timeout: 2000 });
    check("endpoint_owned_by_child", endpoint.hostname === "127.0.0.1" && endpoint.protocol === "http:"
      && endpoint.pathname === "/" && endpoint.port && !endpoint.username && !endpoint.password && !endpoint.search && !endpoint.hash
      && owned.status === 0 && JSON.stringify(owned.stdout.split("\n").filter(row => /^p\d+$/u.test(row))) === JSON.stringify([`p${spec.expected_pid}`]));
    session = new EnvironmentControllerSession(client, { productId: "spireshift-progression-fixture",
      productName: "SpireShift Privileged Progression Check", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    const stable = async previous => {
      while (Date.now() < deadline) {
        const snapshot = (await client.observe()).data; result.latest_snapshot = snapshot;
        if (completePublicMenu(snapshot, runtimeId) && snapshot.snapshot_id !== previous) return snapshot;
        await pause(150);
      }
      throw Error("No fresh complete public progression screen before the cap");
    };
    let snapshot = await stable(null); result.snapshots.push(snapshot);
    const deliver = async (action, phase) => {
      const receipt = (await client.submit({ requestId: `progression-${randomUUID()}`, expectedSnapshotId: snapshot.snapshot_id,
        boundActionId: action.bound_action_id, ...await session.credentials() })).data;
      result.receipts.push({ before: snapshot, action, receipt, phase, expected_snapshot_id: snapshot.snapshot_id });
      if (phase === "entry") result.menu_actions_requested++;
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtimeId)
        throw Error("Uncertain progression delivery; no resubmission");
      snapshot = await stable(snapshot.snapshot_id);
      if (phase === "proceed") {
        // A delivered UI click queues native work. A freshly disabled reward
        // button is not the completed transition and must not trigger another action.
        const advanced = current => current.interaction.kind === "tutorial" || (fixture.act < 3
          ? transitionTarget(current, runtimeId, fixture.act, fixture.target)
          : current.interaction.kind === "event_option"
            && current.interaction.content.context?.event_id === "THE_ARCHITECT");
        while (!advanced(snapshot) && Date.now() < deadline) {
          result.settling_observations.push(snapshot);
          await pause(150);
          snapshot = await stable(snapshot.snapshot_id);
        }
      }
      result.snapshots.push(snapshot);
    };
    for (let i = 0; !snapshot.persistent?.content?.run && i < 8; i++) {
      const action = progressionAction(snapshot, fixture.act, "entry");
      if (/continue|resume/iu.test(action.label)) check("native_continue_offered", true);
      await deliver(action, "entry");
    }
    const before = progressionFacts(snapshot, runtimeId);
    result.starting_snapshot = snapshot;
    check("native_checkpoint_loaded", result.checks.native_continue_offered === true && before.act === fixture.act);
    check("progression_source_not_terminal", before.ending === null);
    const provenance = await fetch(`${spec.endpoint}/api/host-control/provenance`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ expected_runtime_instance_id: runtimeId, host_control_token: spec.host_control_token }), signal: AbortSignal.timeout(3000) });
    result.native_provenance = await provenance.json();
    check("native_A8_seed_preserved", provenance.ok && result.native_provenance.actual_seed === fixture.seed
      && result.native_provenance.runtime_instance_id === runtimeId);
    let proceeded = false;
    for (let i = 0; i < 24 && !transitionTarget(snapshot, runtimeId, fixture.act, fixture.target); i++) {
      const tutorial = snapshot.interaction.kind === "tutorial";
      const phase = tutorial ? "tutorial" : proceeded ? "architect" : "proceed";
      const action = tutorial ? naturalTutorialAction(snapshot) : progressionAction(snapshot, fixture.act, phase);
      await deliver(action, phase);
      if (phase === "proceed") proceeded = true;
    }
    check("progression_target_observed", proceeded && transitionTarget(snapshot, runtimeId, fixture.act, fixture.target));
    check("progression_all_actions_delivered", result.receipts.every(row => row.receipt.delivery === "delivered"));
    result.target_snapshot = snapshot;
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
    if (!result.error) {
      try { result.saved_trace_checks = verifyProgressionTrace(result, fixture); }
      catch (error) { result.error = error.message; }
    }
    writeFileSync(path.join(spec.attempt, "checkpoint-control.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  if (result.error || !result.shutdown_requested) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
