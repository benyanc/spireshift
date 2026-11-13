// Natural fixed-A8 runs through the pinned managed wrapper; no fixture setup or training.
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactCombatReads } from "./engine-combat-surface-v2.mjs";
import { checkNativeEnding, driveRun, projectRunSurface } from "./engine-run-contract-v1.mjs";

export async function main(spec) {
  let child;
  const result = { schema_version: "engine-native-run-diagnostic-v1", status: "incomplete",
    seed: spec.seed, privileged_fixture: false, optimizer_steps: 0, training_allowed: false,
    full_run_attempts: 0, new_game_app_copies: 0, claim_scope: "natural_A8_managed_public_loop_diagnostic_only" };
  try {
    const prepared = await preparePlayerProjection(spec);
    result.projection_identity = prepared.identity;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15000, diagnosticLimit: 10000 });
    child = started.process;
    const raw = async payload => {
      if (["start_run", "reset_run"].includes(payload.cmd)) payload = { ...payload, content_policy: spec.content_policy };
      const response = await child.request(payload, 15000);
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`);
      return response;
    };
    const identity = await raw({ cmd: "runtime_identity" });
    result.runtime_identity = identity;
    if (identity.process_id !== child.pid || identity.host_assembly_sha256 !== spec.expected.artifact_sha256
        || identity.host_module_mvid !== spec.expected.artifact_mvid
        || identity.sts2_assembly_sha256 !== spec.expected.runtime_sts2_sha256
        || identity.godot_stub_assembly_sha256 !== spec.expected.godot_stub_sha256
        || identity.managed_runtime_version !== spec.managed_runtime_version) throw Error("Native run identity mismatch");
    const session = new prepared.module.ManagedPlayerEnvironmentSession({ process: { request: raw }, character: "Ironclad", ascension: 8,
      runtimeInstanceId: `native-run-${child.pid}`, environmentFingerprint: spec.environment_fingerprint,
      surfaceProjector: projectRunSurface, readProjector: projectExactCombatReads, validateSdk: true });
    // Check private setup identity immediately after the normal mount, before a policy acts.
    const mounted = {
      ...session,
      mount: async args => {
        result.full_run_attempts = 1;
        const snapshot = await session.mount(args);
        const run = await raw({ cmd: "run_identity" });
        result.private_start_identity = run;
        if (run.active !== true || run.seed !== spec.seed || run.ascension !== 8
            || run.content_policy !== spec.content_policy || run.native_unlock_run_count !== 999999999)
          throw Error("Natural run did not start with the frozen A8 benchmark profile");
        return snapshot;
      },
      read: args => session.read(args),
      submit: args => session.submit(args)
    };
    result.run = await driveRun(mounted, { seed: spec.seed, runtimeId: `native-run-${child.pid}`, maxDecisions: spec.max_decisions,
      maxRepeatedStates: spec.max_repeated_states, wholeRunBudget: spec.objective.whole_run_budget,
      onRecord: (record, stage) => appendFileSync(path.join(spec.attempt, "public-run.jsonl"), `${JSON.stringify({ stage, ...record })}\n`) });
    result.private_final_identity = await raw({ cmd: "run_identity" });
    result.native_ending_evidence_agrees = checkNativeEnding(result.run, result.private_final_identity);
    await raw({ cmd: "quit" });
    result.exit = await child.exit;
    if (result.exit.code !== 0 || result.exit.signal !== null) throw Error("Native worker did not exit naturally");
    result.runtime_errors = child.diagnostics.filter(row => /\[ERROR\]|unobserved task exception|missingmethodexception|method not found|unhandled exception/iu.test(row.line));
    if (result.runtime_errors.length) throw Error("Native worker reported a runtime error; preserve the failed attempt");
    result.status = result.run.status;
    // A wrapper ending remains a candidate until same-build terminal semantics are qualified.
    result.terminal_semantics_qualified = false;
  } catch (error) { result.error = error.message; }
  finally {
    if (child) {
      result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics));
    }
    writeFileSync(path.join(spec.attempt, "run-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, run: result.run, error: result.error ?? null }));
  if (result.status !== "candidate_terminal") process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  await main(JSON.parse(input));
}
