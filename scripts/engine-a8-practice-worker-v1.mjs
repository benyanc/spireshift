// Load only an isolated prepared start, then use the full native decision surface.
import {appendFileSync, readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {createInterface} from "node:readline";
import path from "node:path";
import {gzipSync} from "node:zlib";
import {NativeWorker} from "./engine-native-worker-v24.mjs";
import {projectSelectionFlows, selectionFlowReads} from "./engine-abandon-confirmation-surface-v1.mjs";
import {checkNativeEnding} from "./engine-native-ending-v1.mjs";
import {newDiagnosticNavigation} from "./engine-run-policy-v7.mjs";
import {OrderedAnswerPlanner} from "./engine-ordered-plan-v1.mjs";
import {runtimeErrors} from "./engine-native-runtime-errors-v1.mjs";

const contract = "native_a8_model_owned_practice_v1";

class PracticeWorker extends NativeWorker {
  async initialize(spec) {
    const adapter = spec.confirmation_adapter;
    if (this.spec || spec.boss_qualification !== contract || !adapter
        || !path.isAbsolute(adapter.path)
        || createHash("sha256").update(readFileSync(adapter.path)).digest("hex") !== adapter.sha256)
      throw Error("Prepared practice requires the frozen confirmation adapter");
    appendFileSync(path.join(spec.attempt, "profile-isolation.sb"),
      "(deny file-write* (subpath " + JSON.stringify(path.dirname(adapter.path)) + "))\n");
    const prior = process.env.DOTNET_STARTUP_HOOKS;
    process.env.DOTNET_STARTUP_HOOKS = adapter.path;
    let identity;
    try {
      identity = await super.initialize(spec);
    } finally {
      if (prior === undefined) delete process.env.DOTNET_STARTUP_HOOKS;
      else process.env.DOTNET_STARTUP_HOOKS = prior;
    }
    if (identity.initial_identity.confirmation_adapter_sha256 !== adapter.sha256
        || identity.initial_identity.pending_abandon_confirmation !== false)
      throw Error("Prepared practice confirmation adapter did not initialize");
    this.cursor = new OrderedAnswerPlanner();
    return {...identity, projection_contract: contract};
  }

  async load({seed, save_json}) {
    if (this.session || this.closed || !/^[A-Z0-9]+$/u.test(seed) || typeof save_json !== "string")
      throw Error("Require a fresh isolated prepared start");
    this.navigation = newDiagnosticNavigation();
    this.index = 0;
    let loaded = false;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({
      process: {request: request => {
        if (request.cmd !== "start_run") return this.raw(request);
        if (loaded) throw Error("Prepared save delivery cannot be retried");
        loaded = true;
        return this.raw({cmd: "load_save", json: save_json});
      }},
      character: "Ironclad", ascension: 8, runtimeInstanceId: this.runtimeId,
      environmentFingerprint: this.spec.environment_fingerprint,
      surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads, validateSdk: true,
    });
    this.snapshot = await this.session.mount({seed});
    const identity = await this.raw({cmd: "run_identity"});
    if (!loaded || !identity.active || identity.seed !== seed || identity.ascension !== 8
        || identity.content_policy !== "serialized_native" || identity.native_unlock_run_count !== 999999999
        || identity.native_game_over || identity.native_player_dead || identity.native_abandoned
        || identity.pending_abandon_confirmation !== false)
      throw Error("Prepared practice loaded the wrong native run or profile");
    this.episodes++;
    return {...await this.observe(), private_setup_identity: identity};
  }

  async step(request) {
    const before = this.snapshot;
    const action = before.bound_actions.actions[request.action_index];
    const local = this.cursor.active && action?.verb === "select";
    const result = await super.step(request);
    const delivery_domain = local ? "local_answer_factor" : "native";
    appendFileSync(path.join(this.spec.attempt, "answer-plan-deliveries.jsonl.gz"),
      gzipSync(JSON.stringify({index: this.index - 1, before_snapshot_id: before.snapshot_id,
        successor_snapshot_id: this.snapshot.snapshot_id, action_id: action.bound_action_id,
        delivery_domain}) + "\n"));
    return {...result, delivery_domain};
  }

  async observe() {
    const errors = runtimeErrors(this.child.diagnostics);
    if (errors.length) throw Error(`Native runtime error: ${errors[0].line}`);
    return super.observe();
  }

  async ending() {
    if (!this.facts?.terminal) throw Error("Cannot label an unfinished game");
    const identity = await this.raw({cmd: "run_identity"});
    const run = {status: "candidate_terminal", victory: this.facts.victory};
    return {native_ending_evidence_agrees: checkNativeEnding(run, identity),
      private_final_identity: identity, usage: await this.usage()};
  }
}

const worker = new PracticeWorker();
try {
  for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
    let request;
    try {
      request = JSON.parse(line);
      let value;
      if (request.command === "initialize") value = await worker.initialize(request.spec);
      else if (request.command === "load") value = await worker.load(request);
      else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "ending") value = await worker.ending();
      else if (request.command === "close") value = await worker.close();
      else throw Error("Undeclared prepared practice operation");
      console.log(JSON.stringify({request_id: request.request_id, ok: true, value}));
      if (request.command === "close") { process.stdin.destroy(); break; }
    } catch (error) {
      console.log(JSON.stringify({request_id: request?.request_id, ok: false, error: error.message}));
      process.exitCode = 1;
      break;
    }
  }
} finally {
  if (worker.child && !worker.closed) await worker.stop();
}
