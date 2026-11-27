// Export a natural starting checkpoint and a finite Scroll Boxes choice/award prefix.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactBundleSurface } from "./engine-bundle-surface-v1.mjs";
import { projectExactCombatReads } from "./engine-combat-surface.mjs";
import { bundleFacts, bundleActionPack, verifyBundleAward } from "./engine-bundle-bridge-contract-v1.mjs";

async function main(spec) {
  const gates = {}, result = { status: "bundle_bridge_projection_incomplete", gates,
    privileged_scenarios: false, full_run_attempts: 0, optimizer_steps: 0, training_allowed: false, journey: [] };
  const check = (name, ok) => { gates[name] = ok === true; if (!ok) throw Error(`Bundle bridge gate failed: ${name}`); };
  let child;
  try {
    const prepared = await preparePlayerProjection(spec); result.projection_identity = prepared.identity;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15000, diagnosticLimit: 10000 }); child = started.process;
    const raw = async (request) => {
      if (request.cmd === "start_run" || request.cmd === "reset_run") request = { ...request, content_policy: "native_all_unlocked" };
      const response = await child.request(request, 15000);
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), JSON.stringify({ request, response }) + "\n"); return response; };
    const identity = await raw({ cmd: "runtime_identity" }); result.runtime_identity = identity;
    check("native_identity_bound", identity.process_id === child.pid && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256 && identity.managed_runtime_version === spec.managed_runtime_version);
    const session = new prepared.module.ManagedPlayerEnvironmentSession({ process: { request: raw },
      character: "Ironclad", ascension: 8, runtimeInstanceId: `bundle-bridge-${child.pid}`,
      environmentFingerprint: spec.environment_fingerprint, surfaceProjector: projectExactBundleSurface,
      readProjector: projectExactCombatReads, validateSdk: true });
    let snapshot = await session.mount({ seed: spec.seed });
    const run = await raw({ cmd: "run_identity" });
    check("native_A8_seed_preserved", run.active && run.seed === spec.seed && run.ascension === 8 && run.content_policy === "native_all_unlocked");
    check("native_bundle_hook_installed", (await raw({ cmd: "runtime_identity" })).native_bundle_selection_hook === true);
    const file = path.join(spec.attempt, "native-checkpoint.save");
    check("native_checkpoint_write_succeeded", (await raw({ cmd: "write_continue_save", path: file, preserve_current_room: true })).success === true);
    const body = JSON.parse(readFileSync(file, "utf8"));
    check("native_save_A8", body.ascension === 8);
    result.checkpoint = { path: file, sha256: hashFile(file), ascension: body.ascension, seed: spec.seed,
      content_policy: "native_all_unlocked", public_setup_actions: 0, provenance: "native_natural_Neow_before_Scroll_Boxes_choice" };
    writeFileSync(path.join(spec.attempt, "private-starting-snapshot.json"), JSON.stringify(snapshot));
    let actionNumber = 0;
    const readDeck = (s) => session.read({ readId: s.reads.find((row) => row.kind === "run_deck")?.read_id, expectedSnapshotId: s.snapshot_id });
    const capture = (s, action) => { const deckRead = readDeck(s), facts = bundleFacts(s, deckRead);
      result.journey.push({ facts, action });
      appendFileSync(path.join(spec.attempt, "private-bundle-snapshots.jsonl"), JSON.stringify({ snapshot: s, deckRead }) + "\n"); };
    const submit = async (s, action) => { const receipt = await session.submit({ requestId: `bundle-bridge-${++actionNumber}`,
      expectedSnapshotId: s.snapshot_id, boundActionId: action.bound_action_id, timeoutMs: 15000 });
      check(`action_${actionNumber}_delivered`, receipt.delivery === "delivered"); return receipt.successor; };
    const options = snapshot.bound_actions.actions.filter((row) => row.label === "Scroll Boxes");
    check("natural_scroll_boxes_option", options.length === 1);
    capture(snapshot, { kind: "event", title: "Scroll Boxes" });
    snapshot = await submit(snapshot, options[0]);
    const surface = snapshot.interaction.content.surface;
    const selected = surface.bundles[spec.bundle_bridge.index];
    const action = snapshot.bound_actions.actions[spec.bundle_bridge.index];
    check("current_pack_index_bound", selected?.index === spec.bundle_bridge.index && !!action);
    const chosen = bundleActionPack(snapshot, action);
    capture(snapshot, { kind: "pack", cards: chosen });
    const before = result.journey.at(-1).facts;
    snapshot = await submit(snapshot, action); capture(snapshot, null);
    check("chosen_pack_awarded_exactly", verifyBundleAward(before, result.journey.at(-1).facts, chosen));
    check("native_bundle_finished", (await raw({ cmd: "run_identity" })).pending_bundle === false);
    await raw({ cmd: "quit" }); result.exit = await child.exit;
    check("natural_exit", result.exit.code === 0 && result.exit.signal === null);
    result.status = "bundle_bridge_public_projection_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) { result.exit ??= await child.stop({ timeoutMs: 2000 }); writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics)); }
    writeFileSync(path.join(spec.attempt, "bundle_bridge-probe.json"), JSON.stringify(result, null, 2) + "\n");
  }
  console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
  if (result.status !== "bundle_bridge_public_projection_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
