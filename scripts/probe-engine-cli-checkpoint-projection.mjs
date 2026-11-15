// Native A8 save bridge for a separately isolated shipped-host comparison, never training.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactCombatSurface, projectExactCombatReads } from "./engine-combat-surface.mjs";

async function main(spec) {
  const gates = {};
  let child, result = { status: "checkpoint_projection_incomplete", gates, privileged_scenarios: true,
    full_run_attempts: 0, optimizer_steps: 0, training_allowed: false };
  const check = (name, ok) => { gates[name] = ok === true; if (!gates[name]) throw new Error(`Checkpoint gate failed: ${name}`); };
  try {
    const prepared = await preparePlayerProjection(spec); result.projection_identity = prepared.identity;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15_000, diagnosticLimit: 10000 }); child = started.process;
    let latest;
    const raw = async (payload, timeout = 15_000) => { if (payload.cmd === "start_run" || payload.cmd === "reset_run")
        payload = { ...payload, content_policy: spec.content_policy };
      const response = await child.request(payload, timeout);
      if (response.type === "decision") latest = response;
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`); return response; };
    const identity = await raw({ cmd: "runtime_identity" }); result.runtime_identity = identity;
    check("native_identity_bound", identity.process_id === child.pid && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.managed_runtime_version === spec.managed_runtime_version);
    const session = new prepared.module.ManagedPlayerEnvironmentSession({ process: { request: raw }, character: "Ironclad", ascension: 8,
      runtimeInstanceId: `checkpoint-${child.pid}`, environmentFingerprint: spec.environment_fingerprint,
      surfaceProjector: projectExactCombatSurface, readProjector: projectExactCombatReads, validateSdk: true });
    let snapshot = await session.mount({ seed: spec.seed });
    const run = await raw({ cmd: "run_identity" });
    check("native_Ironclad_A8_seed_bound", run.ascension === 8 && run.seed === spec.seed && run.active === true);
    check("native_unlock_policy_bound", run.content_policy === spec.content_policy && run.started_with_neow === true
      && run.native_unlock_run_count === 999999999);
    check("native_starting_event_offered", latest.decision === "event_choice"
      && latest.context.total_floor === 1);
    check("complete_public_starting_event", snapshot.completeness.status === "complete" && snapshot.bound_actions.status === "complete");
    const file = path.join(spec.attempt, "native-checkpoint.save");
    const saved = await raw({ cmd: "write_continue_save", path: file, preserve_current_room: true });
    check("native_checkpoint_write_succeeded", saved.success === true && saved.room_type === "EventRoom");
    const body = JSON.parse(readFileSync(file, "utf8"));
    check("serialized_A8_is_preserved", body.ascension === 8);
    result.checkpoint = { path: file, sha256: hashFile(file), ascension: body.ascension,
      seed: spec.seed, content_policy: spec.content_policy, public_setup_actions: 0, provenance: "native_singleplayer_creation_and_game_owned_current_room_save" };
    writeFileSync(path.join(spec.attempt, "private-starting-snapshot.json"), JSON.stringify(snapshot));
    await raw({ cmd: "quit" }); result.exit = await child.exit;
    check("natural_exit", result.exit.code === 0 && result.exit.signal === null);
    result.status = "checkpoint_public_projection_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) { result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics)); }
    writeFileSync(path.join(spec.attempt, "checkpoint-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
  if (result.status !== "checkpoint_public_projection_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
