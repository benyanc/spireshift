// Version 14: preserve owned public relic counters in combat; legacy v10 stays frozen.
// Only the public model_input is passed to a learner. Private identity stays in debug logs.
import { appendFileSync, existsSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { preparePlayerProjection } from "./engine-player-projection-v3.mjs";
import { atomicSelectionReads as projectExactCombatReads, AtomicSelectionCursor as SelectionCursor } from "./engine-atomic-selection-v1.mjs";
import { inspectRunInput, checkNativeEnding } from "./engine-run-contract-v5.mjs";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { chooseRunAction, newDiagnosticNavigation, recordDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";

import { projectRelicSurface as projectSelectionSurface, INVENTORY_CONTRACT } from "./engine-relic-surface-v4.mjs";

function journal(file, record) {
  // Concatenated gzip members are readable by standard gzip readers. Each record
  // survives interruption; no app payload or uncompressed duplicate trace accumulates.
  appendFileSync(`${file}.gz`, gzipSync(`${JSON.stringify(record)}\n`));
}

export class NativeWorker {
  async initialize(spec) {
    this.cursor = new SelectionCursor();
    this.spec = spec; this.episodes = 0; this.closed = false;
    this.phase = "projection_verify";
    this.prepared = await preparePlayerProjection(spec);
    this.phase = "native_launch";
    const { startJsonLineProcess } = this.prepared.transport;
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, TMPDIR: path.join(spec.profile, "tmp"),
        STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15000, diagnosticLimit: 10000 });
    this.child = started.process;
    this.runtimeId = `native-worker-${this.child.pid}`;
    this.phase = "runtime_identity";
    const identity = await this.raw({ cmd: "runtime_identity" });
    if (identity.process_id !== this.child.pid || identity.host_assembly_sha256 !== spec.expected.artifact_sha256
        || identity.host_module_mvid !== spec.expected.artifact_mvid
        || identity.sts2_assembly_sha256 !== spec.expected.runtime_sts2_sha256
        || identity.godot_stub_assembly_sha256 !== spec.expected.godot_stub_sha256
        || identity.managed_runtime_version !== "9.0.7") throw Error("Native worker identity mismatch");
    const empty = await this.raw({ cmd: "run_identity" });
    if (empty.active || empty.pending_host_operation || empty.action_executor_running)
      throw Error("New native worker already has an active operation");
    this.phase = "ready";
    return { runtime_identity: identity, initial_identity: empty, profile: spec.profile,
      projection_identity: this.prepared.identity.report_id, shared_projection: spec.shared_projection,
      usage: await this.usage(), game_apps_created: 0, inventory_observation_contract: INVENTORY_CONTRACT };
  }
  async raw(payload) {
    const cursor = this.cursor?.handle(payload);
    if (cursor) {
      journal(path.join(this.spec.attempt, "selection-cursor.jsonl"), { request: payload, ...cursor });
      if (cursor.local) {
        journal(path.join(this.spec.attempt, "private-transcript.jsonl"), { request: payload, response: cursor.response, transport: "local_selection_ui" });
        return cursor.response;
      }
      payload = cursor.native;
    }
    if (["start_run", "reset_run"].includes(payload.cmd)) payload = { ...payload,
      character: "Ironclad", ascension: 8, content_policy: this.spec.content_policy };
    const response = await this.child.request(payload, 15000);
    journal(path.join(this.spec.attempt, "private-transcript.jsonl"), { request: payload, response });
    if (response.type === "error") {
      this.nativeError = `Native ${payload.action ?? payload.cmd}: ${response.message}`;
      throw Error(this.nativeError);
    }
    return this.cursor.observe(response);
  }
  async mount(seed) {
    if (this.closed || (this.snapshot && !this.facts.terminal)) throw Error("Worker cannot silently abandon an unfinished episode");
    if (!/^[A-Z0-9]+$/u.test(seed)) throw Error("Use a native canonical seed");
    this.navigation = newDiagnosticNavigation(); this.index = 0;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({ process: { request: p => this.raw(p) },
      character: "Ironclad", ascension: 8, runtimeInstanceId: this.runtimeId,
      environmentFingerprint: this.spec.environment_fingerprint,
      surfaceProjector: projectSelectionSurface, readProjector: projectExactCombatReads, validateSdk: true });
    this.snapshot = await this.session.mount({ seed, reset: this.episodes > 0 });
    const identity = await this.raw({ cmd: "run_identity" });
    if (!identity.active || identity.seed !== seed || identity.ascension !== 8
        || identity.content_policy !== this.spec.content_policy || identity.native_unlock_run_count !== 999999999
        || identity.started_with_neow !== true || identity.native_game_over || identity.native_player_dead)
      throw Error("Native reset/start has the wrong profile, seed or ending state");
    this.episodes++;
    return { ...await this.observe(), private_start_identity: identity, native_process_id: this.child.pid,
      episode: this.episodes, reset: this.episodes > 1 };
  }
  async usage() {
    const native = await this.raw({ cmd: "process_metrics" }), node = process.cpuUsage();
    if (!Number.isFinite(native.cpu_total_ms) || native.cpu_total_ms < 0)
      throw Error("Missing native CPU accounting");
    return { native_cpu_seconds: native.cpu_total_ms / 1000,
      node_cpu_seconds: (node.user + node.system) / 1e6,
      native_resident_bytes: native.working_set_bytes };
  }
  async observe() {
    const snapshot = this.snapshot;
    const reads = snapshot.reads.map(row => this.session.read({ readId: row.read_id,
      expectedSnapshotId: snapshot.snapshot_id }));
    // Inspect first: no unsupported, stale or partial state becomes learning input.
    this.facts = inspectRunInput(snapshot, reads, this.runtimeId);
    const model_input = publicPolicyInput(snapshot, reads, this.navigation);
    const key = createHash("sha256").update(stableJson(model_input)).digest("hex");
    const choice = this.facts.terminal ? null : (this.cursor.active
      ? snapshot.bound_actions.actions.find(a => a.verb === "confirm") ?? snapshot.bound_actions.actions.find(a => a.verb === "select") ?? snapshot.bound_actions.actions[0]
      : chooseRunAction(snapshot, undefined, this.navigation));
    const result = { snapshot, reads, facts: this.facts, model_input, public_key: key,
      default_action_index: choice == null ? null : snapshot.bound_actions.actions.indexOf(choice), index: this.index };
    journal(path.join(this.spec.attempt, "public-observations.jsonl"), { episode: this.episodes, ...result });
    return { ...result, usage: await this.usage() };
  }
  async step(request) {
    const snapshot = this.snapshot;
    if (this.closed || this.facts.terminal || request.snapshot_id !== snapshot.snapshot_id
        || !Number.isSafeInteger(request.action_index) || request.action_index < 0
        || request.action_index >= snapshot.bound_actions.actions.length)
      throw Error("Stale or unadvertised worker action");
    const action = snapshot.bound_actions.actions[request.action_index];
    const receipt = await this.session.submit({ requestId: `worker-${this.episodes}-${this.index}`,
      expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id, timeoutMs: 15000 });
    journal(path.join(this.spec.attempt, "public-receipts.jsonl"), { episode: this.episodes,
      index: this.index, snapshot_id: snapshot.snapshot_id, action, delivery: receipt.delivery,
      successor_snapshot_id: receipt.successor?.snapshot_id ?? null, reason_code: receipt.reason_code ?? null });
    if (receipt.delivery !== "delivered" || !receipt.successor)
      throw Error(this.nativeError ?? `Uncertain worker delivery: ${receipt.reason_code ?? receipt.delivery}`);
    recordDiagnosticNavigation(this.navigation, snapshot, action, receipt);
    this.snapshot = receipt.successor; this.index++;
    return this.observe();
  }
  async ending() {
    if (!this.facts?.terminal) throw Error("Cannot label an unfinished game");
    const identity = await this.raw({ cmd: "run_identity" });
    const agrees = checkNativeEnding({ status: "candidate_terminal", victory: this.facts.victory }, identity);
    return { native_ending_evidence_agrees: agrees, private_final_identity: identity, usage: await this.usage() };
  }
  async close() {
    this.closed = true;
    if (!this.child) return { clean_exit: false };
    await this.raw({ cmd: "quit" });
    const exit = await this.child.exit;
    const errors = this.child.diagnostics.filter(row => /\[ERROR\]|unobserved task exception|missingmethodexception|method not found|unhandled exception/iu.test(row.line));
    writeFileSync(path.join(this.spec.attempt, "diagnostics.json"), JSON.stringify(this.child.diagnostics), { flag: "wx" });
    if (exit.code !== 0 || exit.signal !== null || errors.length) throw Error("Native worker exit/runtime error");
    return { exit, clean_exit: true, runtime_errors: errors, episodes: this.episodes };
  }
  async stop() {
    if (!this.child) return;
    const exit = await this.child.stop({ timeoutMs: 2000 });
    const diagnostics = path.join(this.spec.attempt, "diagnostics.json");
    if (!existsSync(diagnostics)) writeFileSync(diagnostics, JSON.stringify(this.child.diagnostics), { flag: "wx" });
    writeFileSync(path.join(this.spec.attempt, "native-process-stop.json"),
      JSON.stringify({ process_id: this.child.pid, exit }), { flag: "wx" });
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const worker = new NativeWorker();
  try {
    for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
      let request;
      try {
        request = JSON.parse(line);
        let value;
        if (request.command === "initialize") value = await worker.initialize(request.spec);
        else if (request.command === "mount") value = await worker.mount(request.seed);
        else if (request.command === "step") value = await worker.step(request);
        else if (request.command === "ending") value = await worker.ending();
        else if (request.command === "close") value = await worker.close();
        else throw Error("Unsupported native worker control");
        console.log(JSON.stringify({ request_id: request.request_id, ok: true, value }));
        if (request.command === "close") { process.stdin.destroy(); break; }
      } catch (error) {
        if (request?.command === "initialize") writeFileSync(path.join(worker.spec.attempt, "startup-failure.json"),
          JSON.stringify({ phase: worker.phase ?? "initialize", error: error.message }), { flag: "wx" });
        console.log(JSON.stringify({ request_id: request?.request_id, ok: false, error: `${worker.phase ?? "worker"}: ${error.message}` }));
        // Never retry an uncertain mutation or reset a contaminated process.
        process.exitCode = 1; break;
      }
    }
  } finally { await worker.stop(); }
}
