// One seeded starting save and the first combat turn, using only complete public controls.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactCombatSurface, projectExactCombatReads } from "./engine-combat-surface.mjs";
import { actionKey, chooseJourneyAction, journeyFacts } from "./engine-journey-contract.mjs";

async function main(spec) {
  const gates = {};
  let child;
  const result = { status: "journey_projection_incomplete", gates, full_run_attempts: 0,
    optimizer_steps: 0, training_allowed: false, journey: [], setup_actions: 0 };
  const check = (name, ok) => { gates[name] = ok === true; if (!ok) throw new Error(`Journey gate failed: ${name}`); };
  try {
    const prepared = await preparePlayerProjection(spec); result.projection_identity = prepared.identity;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15_000, diagnosticLimit: 10000 }); child = started.process;
    const raw = async (payload, timeout = 15_000) => {
      if (["start_run", "reset_run"].includes(payload.cmd)) payload = { ...payload, content_policy: spec.content_policy };
      const response = await child.request(payload, timeout);
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`);
      return response;
    };
    const identity = await raw({ cmd: "runtime_identity" }); result.runtime_identity = identity;
    check("native_identity_bound", identity.process_id === child.pid && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256
      && identity.managed_runtime_version === spec.managed_runtime_version);
    const session = new prepared.module.ManagedPlayerEnvironmentSession({ process: { request: raw }, character: "Ironclad", ascension: 8,
      runtimeInstanceId: `journey-${child.pid}`, environmentFingerprint: spec.environment_fingerprint,
      surfaceProjector: projectExactCombatSurface, readProjector: projectExactCombatReads, validateSdk: true });
    let snapshot = await session.mount({ seed: spec.seed });
    const run = await raw({ cmd: "run_identity" });
    check("native_Ironclad_A8_seed_bound", run.ascension === 8 && run.seed === spec.seed && run.active === true);
    check("native_unlock_policy_bound", run.content_policy === "native_all_unlocked" && run.started_with_neow === true
      && run.native_unlock_run_count === 999999999);
    check("native_starting_event_offered", snapshot.interaction.kind === "event_option" && snapshot.persistent.content.run.floor === 1);
    journeyFacts(snapshot);
    writeFileSync(path.join(spec.attempt, "private-starting-snapshot.json"), JSON.stringify(snapshot));
    const file = path.join(spec.attempt, "native-checkpoint.save");
    const saved = await raw({ cmd: "write_continue_save", path: file, preserve_current_room: true });
    check("native_checkpoint_write_succeeded", saved.success === true && saved.room_type === "EventRoom"
      && JSON.parse(readFileSync(file, "utf8")).ascension === 8);
    result.checkpoint = { path: file, sha256: hashFile(file), ascension: 8, seed: spec.seed,
      content_policy: "native_all_unlocked", public_setup_actions: 0 };
    let plays = 0, ended = false;
    for (let i = 0; i <= spec.journey.max_actions; i++) {
      appendFileSync(path.join(spec.attempt, "private-journey-snapshots.jsonl"), `${JSON.stringify(snapshot)}\n`);
      const row = { facts: journeyFacts(snapshot), action: null };
      result.journey.push(row);
      if (ended) {
        check("fresh_second_combat_turn", snapshot.interaction.kind === "combat_turn" && row.facts.combat.round === 2);
        break;
      }
      if (i === spec.journey.max_actions) throw new Error("Finite journey action cap reached");
      const action = chooseJourneyAction(snapshot, { startingOption: spec.journey.starting_option, plays, started: i > 0 });
      row.action = actionKey(snapshot, action);
      if (action.verb === "play") plays++;
      if (action.verb === "end_turn") ended = true;
      const receipt = await session.submit({ requestId: `journey-${i}`, expectedSnapshotId: snapshot.snapshot_id,
        boundActionId: action.bound_action_id, timeoutMs: 15_000 });
      check(`action_${i + 1}_delivered`, receipt.delivery === "delivered");
      snapshot = receipt.successor;
    }
    check("first_turn_card_and_end_turn_observed", plays > 0 && ended);
    result.public_actions_delivered = result.journey.length - 1;
    await raw({ cmd: "quit" }); result.exit = await child.exit;
    check("natural_exit", result.exit.code === 0 && result.exit.signal === null);
    result.status = "journey_public_projection_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) { result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics)); }
    writeFileSync(path.join(spec.attempt, "journey-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
  if (result.status !== "journey_public_projection_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
