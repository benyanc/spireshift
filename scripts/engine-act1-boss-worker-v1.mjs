// Fresh normal-start worker using the saved-verified generated-choice belt.
import {appendFileSync} from "node:fs";
import path from "node:path";
import {createInterface} from "node:readline";
import {gzipSync} from "node:zlib";
import {NativeWorker} from "./engine-native-worker-v24.mjs";
import {projectSelectionFlows, selectionFlowReads} from "./engine-generated-choice-belt-surface-v1.mjs";
import {newDiagnosticNavigation} from "./engine-run-policy-v7.mjs";
import {OrderedAnswerPlanner} from "./engine-ordered-plan-v1.mjs";
import {runtimeErrors} from "./engine-native-runtime-errors-v1.mjs";

const PROJECTION = "act1_generated_choice_belt_v1";

class BossQualificationWorker extends NativeWorker {
  async initialize(spec) {
    if (this.spec || spec.boss_qualification !== PROJECTION)
      throw Error("Require the separately pinned boss qualification");
    const identity = await super.initialize(spec);
    this.cursor = new OrderedAnswerPlanner();
    return {...identity, projection_contract: PROJECTION,
      decision_contract: "one_committed_ordered_answer_factorization_v1"};
  }

  async mount(seed) {
    if (this.session || this.closed || !/^[A-Z0-9]+$/u.test(seed))
      throw Error("Require one fresh canonical normal start per worker");
    this.navigation = newDiagnosticNavigation();
    this.index = 0;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({
      process: {request: request => this.raw(request)},
      character: "Ironclad", ascension: 8, runtimeInstanceId: this.runtimeId,
      environmentFingerprint: this.spec.environment_fingerprint,
      surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads, validateSdk: true
    });
    this.snapshot = await this.session.mount({seed, reset: false});
    const identity = await this.raw({cmd: "run_identity"});
    if (!identity.active || identity.seed !== seed || identity.ascension !== 8
        || identity.content_policy !== this.spec.content_policy
        || identity.native_unlock_run_count !== 999999999 || identity.started_with_neow !== true
        || identity.native_game_over || identity.native_player_dead)
      throw Error("Native start has the wrong profile, seed or ending state");
    this.episodes++;
    return {...await this.observe(), private_start_identity: identity,
      native_process_id: this.child.pid, episode: this.episodes, reset: false};
  }

  async step(request) {
    const snapshot = this.snapshot;
    const action = snapshot.bound_actions.actions[request.action_index];
    const local = this.cursor.active && action?.verb === "select";
    const result = await super.step(request);
    const delivery_domain = local ? "local_answer_factor" : "native";
    appendFileSync(path.join(this.spec.attempt, "answer-plan-deliveries.jsonl.gz"),
      gzipSync(JSON.stringify({index: this.index - 1, before_snapshot_id: snapshot.snapshot_id,
        successor_snapshot_id: this.snapshot.snapshot_id, action_id: action.bound_action_id,
        delivery_domain}) + "\n"));
    return {...result, delivery_domain};
  }

  async observe() {
    const errors = runtimeErrors(this.child.diagnostics);
    if (errors.length) throw Error(`Native runtime error: ${errors[0].line}`);
    return super.observe();
  }
}

const worker = new BossQualificationWorker();
try {
  for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
    let request;
    try {
      request = JSON.parse(line);
      let value;
      if (request.command === "initialize") value = await worker.initialize(request.spec);
      else if (request.command === "mount") value = await worker.mount(request.seed);
      else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "ending") value = await worker.ending();
      else if (request.command === "close") value = await worker.close();
      else throw Error("Undeclared boss-qualification operation");
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
