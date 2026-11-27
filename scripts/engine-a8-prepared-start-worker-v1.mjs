import { createHash } from "node:crypto";
import { appendFileSync, readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import path from "node:path";
import { SelectorWorker } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { CardAnswerPlanner } from "./engine-card-answer-v1.mjs";
import { selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";

const contract = "native_a8_later_act_start_v1";

class PreparedWorker extends SelectorWorker {
  async initialize(spec) {
    if (this.spec || spec.boss_qualification !== contract || spec.confirmation_control !== false)
      throw Error("Require the pinned later-act worker");
    const adapters = [spec.confirmation_adapter, spec.prepared_start_adapter];
    for (const adapter of adapters) {
      if (!adapter || !path.isAbsolute(adapter.path)
          || createHash("sha256").update(readFileSync(adapter.path)).digest("hex") !== adapter.sha256)
        throw Error("A pinned headless adapter differs");
      appendFileSync(path.join(spec.attempt, "profile-isolation.sb"),
        "(deny file-write* (subpath " + JSON.stringify(path.dirname(adapter.path)) + "))\n");
    }
    const prior = process.env.DOTNET_STARTUP_HOOKS;
    process.env.DOTNET_STARTUP_HOOKS = adapters.map(adapter => adapter.path).join(path.delimiter);
    let result;
    try {
      result = await NativeWorker.prototype.initialize.call(this, spec);
    } finally {
      if (prior === undefined) delete process.env.DOTNET_STARTUP_HOOKS;
      else process.env.DOTNET_STARTUP_HOOKS = prior;
    }
    const identity = result.initial_identity;
    if (identity.confirmation_adapter_sha256 !== adapters[0].sha256
        || identity.prepared_start_adapter_sha256 !== adapters[1].sha256
        || identity.prepared_load_initialized !== false || identity.pending_abandon_confirmation !== false)
      throw Error("Later-act adapters did not initialize on an empty worker");
    this.cursor = new CardAnswerPlanner();
    return { ...result, projection_contract: contract };
  }

  async load({ seed, save_json }) {
    if (this.session || this.closed || !/^[A-Z0-9]+$/u.test(seed) || typeof save_json !== "string")
      throw Error("Load exactly one declared save in a fresh prepared worker");
    this.navigation = newDiagnosticNavigation();
    this.index = 0;
    let loaded = false;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({
      process: { request: request => {
        if (request.cmd !== "start_run") return this.raw(request);
        if (loaded) throw Error("Prepared native save delivery cannot be retried");
        loaded = true;
        return this.raw({ cmd: "load_save", json: save_json });
      } },
      character: "Ironclad", ascension: 8, runtimeInstanceId: this.runtimeId,
      environmentFingerprint: this.spec.environment_fingerprint, surfaceProjector: projectSelectionFlows,
      readProjector: selectionFlowReads, validateSdk: true,
    });
    this.snapshot = await this.session.mount({ seed, reset: false });
    const identity = await this.raw({ cmd: "run_identity" });
    if (!loaded || !identity.active || identity.seed !== seed || identity.ascension !== 8
        || ![2, 3].includes(identity.act) || identity.content_policy !== "serialized_native"
        || identity.native_unlock_run_count !== 999999999 || !identity.prepared_load_initialized
        || identity.native_game_over || identity.native_player_dead || identity.native_abandoned !== false
        || identity.pending_abandon_confirmation !== false)
      throw Error("The saved later-act start has the wrong native identity");
    this.episodes++;
    return { ...await this.observe(), private_setup_identity: identity };
  }

  async crystalDiagnostic() {
    if (this.spec.prepared_diagnostic !== true || this.episodes !== 1 || this.index !== 0)
      throw Error("Require a separate saved-start Crystal Sphere diagnostic");
    const state = await this.raw({ cmd: "enter_room", type: "event", event: "CRYSTAL_SPHERE" });
    this.snapshot = await this.session.acceptNativeObservation(state, 15000);
    return this.observe();
  }
}

const worker = new PreparedWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let result;
      if (request.command === "initialize") result = await worker.initialize(request.spec);
      else if (request.command === "load") result = await worker.load(request);
      else if (request.command === "crystal_diagnostic") result = await worker.crystalDiagnostic();
      else if (request.command === "step") result = await worker.step(request);
      else if (request.command === "ending") result = await worker.ending();
      else if (request.command === "close") result = await worker.close();
      else throw Error("Undeclared later-act worker operation");
      console.log(JSON.stringify({ request_id: request.request_id, ok: true, value: result }));
      if (request.command === "close") { process.stdin.destroy(); break; }
    } catch (error) {
      console.log(JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message }));
      process.exitCode = 1;
      break;
    }
  }
} finally {
  if (worker.child && !worker.closed) await worker.stop();
}
