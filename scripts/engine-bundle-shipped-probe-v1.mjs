// Replay natural Scroll Boxes pickup and visible preview/cancel/reopen/confirm controls.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { completePublicMenu, validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { startingOptions } from "./engine-checkpoint-shipped-probe.mjs";
import { bundleFacts, packFacts, choosePack, verifyBundlePreview, verifyBundleAward, firstDifference } from "./engine-bundle-bridge-contract-v1.mjs";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function main(spec) {
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(pathToFileURL(
    path.join(spec.toolchain, "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2500), deadline = Date.now() + spec.max_wall_seconds * 1000;
  const result = { checks: {}, menu_actions_requested: 0, public_actions_requested: 0,
    semantic_actions_delivered: 0, shutdown_requested: false, training_allowed: false,
    comparisons: [], receipts: [], bundle_ui_steps: [] };
  const check = (name, ok) => { result.checks[name] = ok === true; if (!ok) throw Error(`Bundle shipped gate failed: ${name}`); };
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
    session = new EnvironmentControllerSession(client, { productId: "spireshift-bundle-qualification", productName: "SpireShift Bundle Comparison", productVersion: "1" });
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
      const receipt = (await client.submit({ requestId: `bundle-${randomUUID()}`, expectedSnapshotId: snapshot.snapshot_id,
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
    for (let i = 0; i < 8 && snapshot.interaction.kind !== "event_option"; i++) {
      if (!["main_menu", "singleplayer_menu"].includes(snapshot.interaction.kind)) throw Error("Unqualified checkpoint entry/modal");
      const continuations = snapshot.bound_actions.actions.filter((row) => /continue|resume/i.test(row.label));
      if (continuations.length > 1) throw Error("Ambiguous Continue control");
      if (continuations.length === 1) check("native_continue_offered", true);
      const action = continuations[0] ?? snapshot.bound_actions.actions.find((row) => /single ?player|play/i.test(row.label));
      if (!action) throw Error("No checkpoint entry control");
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
    check("same_starting_public_option_titles_and_availability", firstDifference(result.starting_options_comparison.managed, result.starting_options_comparison.shipped) == null);
    const native = JSON.parse(readFileSync(spec.fixture.bundle_report_path, "utf8")), plan = native.probe.journey;
    for (let i = 0; i < plan.length; i++) {
      const deckRead = await deck(snapshot), facts = bundleFacts(snapshot, deckRead);
      const difference = firstDifference(plan[i].facts, facts);
      result.comparisons.push({ index: i, snapshot, deckRead, facts, matched: difference == null });
      if (difference) { result.first_difference = difference; throw Error(`Bundle facts diverged at ${difference.field}`); }
      if (plan[i].action == null) break;
      if (plan[i].action.kind === "event") {
        const actions = snapshot.bound_actions.actions.filter((row) => row.label === plan[i].action.title);
        if (actions.length !== 1) throw Error("No unique current Scroll Boxes option");
        snapshot = await submit(snapshot, actions[0]);
      } else if (plan[i].action.kind === "pack") {
        const before = snapshot, beforeDeck = deckRead, expected = plan[i].action.cards;
        let preview = await submit(before, choosePack(before, expected)), previewDeck = await deck(preview);
        let controls = verifyBundlePreview(before, beforeDeck, preview, previewDeck, expected);
        const canceled = await submit(preview, controls.cancel), canceledDeck = await deck(canceled);
        check("bundle_cancel_preserves_choices_and_ownership", firstDifference(bundleFacts(before, beforeDeck), bundleFacts(canceled, canceledDeck)) == null);
        result.bundle_ui_steps.push({ kind: "preview_cancel", before, beforeDeck, preview, previewDeck,
          after: canceled, afterDeck: canceledDeck, expected_pack: expected });
        preview = await submit(canceled, choosePack(canceled, expected)); previewDeck = await deck(preview);
        controls = verifyBundlePreview(canceled, canceledDeck, preview, previewDeck, expected);
        result.bundle_ui_steps.push({ kind: "preview_confirm", before: canceled, beforeDeck: canceledDeck,
          preview, previewDeck, expected_pack: expected });
        snapshot = await submit(preview, controls.confirm);
      } else throw Error("Unknown bundle prefix action");
      result.semantic_actions_delivered++;
    }
    check("bundle_all_snapshots_match", result.comparisons.length === 3 && result.comparisons.every((row) => row.matched));
    check("bundle_all_actions_delivered", result.semantic_actions_delivered === 2 && result.public_actions_requested === 5);
    check("bundle_preview_cancel_confirm_verified", result.bundle_ui_steps.length === 2);
    check("bundle_selected_cards_obtained", verifyBundleAward(result.comparisons[1].facts, result.comparisons[2].facts, plan[1].action.cards));
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
