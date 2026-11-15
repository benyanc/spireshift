// Named privileged shop fixture and finite SDK purchases/removal; no full run or training.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactCombatSurface, projectExactCombatReads } from "./engine-combat-surface.mjs";
import { prepareShopSave, shopFacts, shopActionKey, chooseShopAction, shopPlans, verifyShopEffects } from "./engine-shop-bridge-contract.mjs";

async function main(spec) {
  const gates = {}, result = { status: "shop_bridge_projection_incomplete", gates,
    privileged_scenarios: true, full_run_attempts: 0, optimizer_steps: 0, training_allowed: false,
    setup_actions: 2, journey: [] };
  const check = (name, ok) => { gates[name] = ok === true; if (!ok) throw new Error(`Shop bridge gate failed: ${name}`); };
  let child;
  try {
    const prepared = await preparePlayerProjection(spec); result.projection_identity = prepared.identity;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15000, diagnosticLimit: 10000 }); child = started.process;
    const raw = async (payload) => {
      if (payload.cmd === "start_run") payload = { ...payload, content_policy: "native_all_unlocked" };
      const response = await child.request(payload, 15000);
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`);
      return response;
    };
    const identity = await raw({ cmd: "runtime_identity" }); result.runtime_identity = identity;
    check("native_identity_bound", identity.process_id === child.pid && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256 && identity.managed_runtime_version === spec.managed_runtime_version);
    const makeSession = () => new prepared.module.ManagedPlayerEnvironmentSession({ process: { request: raw }, character: "Ironclad", ascension: 8,
      runtimeInstanceId: `shop-bridge-${child.pid}`, environmentFingerprint: spec.environment_fingerprint,
      surfaceProjector: projectExactCombatSurface, readProjector: projectExactCombatReads, validateSdk: true });
    let session = makeSession();
    await session.mount({ seed: spec.seed });
    const run = await raw({ cmd: "run_identity" });
    check("native_A8_seed_bound", run.ascension === 8 && run.seed === spec.seed && run.active === true);
    check("native_potion_pricing_hook_installed", (await raw({ cmd: "runtime_identity" })).native_potion_pricing_hook === true);
    check("native_fixture_setup", (await raw({ cmd: "set_player", gold: 1000, deck: ["STRIKE_IRONCLAD"],
      ...(spec.shop_bridge.scenario === "courier-restock-removal" ? { obtain_relics: ["THE_COURIER"] } : {}) })).type === "ok");
    const originalPath = path.join(spec.attempt, "private-before-fixture.save");
    check("native_save_export", (await raw({ cmd: "write_continue_save", path: originalPath, preserve_current_room: true })).success === true);
    const file = path.join(spec.attempt, "native-checkpoint.save");
    writeFileSync(file, JSON.stringify(prepareShopSave(JSON.parse(readFileSync(originalPath, "utf8")))));
    // Resume in a fresh process using the native saved-run lifecycle, as the shipped Host does.
    await raw({ cmd: "quit" });
    result.exporter_exit = await child.exit;
    check("fixture_exporter_natural_exit", result.exporter_exit.code === 0 && result.exporter_exit.signal === null);
    result.fixture_exporter_identity = identity;
    const resumed = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15000, diagnosticLimit: 10000 }); child = resumed.process;
    const resumedIdentity = await raw({ cmd: "runtime_identity" }); result.runtime_identity = resumedIdentity;
    check("native_resume_identity_bound", resumedIdentity.process_id === child.pid
      && resumedIdentity.host_assembly_sha256 === identity.host_assembly_sha256
      && resumedIdentity.host_module_mvid === identity.host_module_mvid
      && resumedIdentity.sts2_assembly_sha256 === identity.sts2_assembly_sha256
      && resumedIdentity.godot_stub_assembly_sha256 === identity.godot_stub_assembly_sha256
      && resumedIdentity.managed_runtime_version === identity.managed_runtime_version);
    session = makeSession();
    const loaded = await raw({ cmd: "load_save", path: file, lang: "en" });
    check("native_serialized_fixture_loaded", loaded.type === "decision");
    let snapshot = await session.acceptNativeObservation(loaded);
    check("native_fixture_shop_offered", snapshot.interaction.kind === "shop_inventory"
      && snapshot.persistent.content.run.floor === 1 && snapshot.persistent.content.player.gold === 1000);
    result.checkpoint = { path: file, sha256: hashFile(file), ascension: 8, seed: spec.seed,
      content_policy: "serialized_native_privileged_shop_fixture", public_setup_actions: 0,
      fixture_mutations: ["native_player_setup", "initial_saved_map_point_shop", "clear_prefinished_room_and_history"] };
    writeFileSync(path.join(spec.attempt, "private-starting-snapshot.json"), JSON.stringify(snapshot));
    const plan = shopPlans[spec.shop_bridge.scenario];
    for (let i = 0; i <= plan.length; i++) {
      const descriptor = snapshot.reads.find((row) => row.kind === "run_deck");
      const deckRead = session.read({ readId: descriptor?.read_id, expectedSnapshotId: snapshot.snapshot_id });
      const row = { facts: shopFacts(snapshot, deckRead), action: null };
      result.journey.push(row);
      appendFileSync(path.join(spec.attempt, "private-shop-snapshots.jsonl"), `${JSON.stringify({ snapshot, deckRead })}\n`);
      if (i === plan.length) break;
      const action = chooseShopAction(snapshot, plan[i]); row.action = shopActionKey(snapshot, action);
      const receipt = await session.submit({ requestId: `shop-${i}`, expectedSnapshotId: snapshot.snapshot_id,
        boundActionId: action.bound_action_id, timeoutMs: 15000 });
      check(`action_${i + 1}_delivered`, receipt.delivery === "delivered"); snapshot = receipt.successor;
    }
    check("shop_purchase_removal_and_exit_effects", verifyShopEffects(spec.shop_bridge.scenario, result.journey));
    result.public_actions_delivered = plan.length;
    await raw({ cmd: "quit" }); result.exit = await child.exit;
    check("natural_exit", result.exit.code === 0 && result.exit.signal === null);
    result.status = "shop_bridge_public_projection_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) { result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics)); }
    writeFileSync(path.join(spec.attempt, "shop_bridge-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
  if (result.status !== "shop_bridge_public_projection_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
