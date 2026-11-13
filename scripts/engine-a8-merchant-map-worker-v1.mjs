import { createHash } from "node:crypto";
import { appendFileSync, readFileSync } from "node:fs";
import { createInterface } from "node:readline";
import path from "node:path";
import { PROJECTION as SELECTORS, SelectorWorker } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { CardAnswerPlanner } from "./engine-card-answer-v1.mjs";
import { selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { observeAfterMerchantExit } from "./engine-merchant-map-observation-v1.mjs";
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { loadPreparedSave } from "./engine-prepared-save-load-v1.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";

const NORMAL = "native_a8_merchant_map_normal_v1";
const PREPARED = "native_a8_merchant_map_prepared_v1";

class MerchantMapWorker extends SelectorWorker {
  async initialize(spec) {
    const contract = spec.boss_qualification;
    if (this.spec || ![NORMAL, PREPARED].includes(contract) || spec.confirmation_control !== false)
      throw Error("Require the pinned merchant-map worker");
    this.preparedStart = contract === PREPARED;
    if (!this.preparedStart) {
      const result = await super.initialize({ ...spec, boss_qualification: SELECTORS });
      return { ...result, projection_contract: contract };
    }
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

  async raw(request) {
    const response = await super.raw(request);
    return observeAfterMerchantExit(request, response, next => super.raw(next));
  }

  async mount(seed, save = null) {
    if (this.session || this.closed || !/^[A-Z0-9]+$/u.test(seed)
        || (this.preparedStart ? typeof save !== "string" : save !== null))
      throw Error("Require one declared start in a fresh merchant-map worker");
    this.navigation = newDiagnosticNavigation();
    this.index = 0;
    let loaded = false;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({
      process: { request: request => {
        if (!this.preparedStart || request.cmd !== "start_run") return this.raw(request);
        if (loaded) throw Error("Prepared native save delivery cannot be retried");
        loaded = true;
        return loadPreparedSave(this, save, seed, 20_000);
      } }, character: "Ironclad", ascension: 8,
      runtimeInstanceId: this.runtimeId, environmentFingerprint: this.spec.environment_fingerprint,
      surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads, validateSdk: true,
    });
    this.snapshot = await this.session.mount({ seed, reset: false });
    const identity = await this.raw({ cmd: "run_identity" });
    if (!identity.active || identity.seed !== seed || identity.ascension !== 8
        || identity.native_unlock_run_count !== 999999999 || identity.native_game_over
        || identity.native_player_dead || identity.native_abandoned !== false
        || identity.pending_abandon_confirmation !== false
        || (this.preparedStart
          ? !loaded || ![2, 3].includes(identity.act) || identity.content_policy !== "serialized_native"
            || !identity.prepared_load_initialized
          : identity.started_with_neow !== true || identity.content_policy !== this.spec.content_policy))
      throw Error("The native start has the wrong identity");
    this.episodes++;
    const result = await this.observe();
    return this.preparedStart ? { ...result, private_setup_identity: identity }
      : { ...result, private_start_identity: identity, native_process_id: this.child.pid,
        episode: this.episodes, reset: false };
  }

  async merchantFixture(merchant) {
    if (this.spec.merchant_map_diagnostic !== true || this.fixtureUsed || !this.session
        || !["real", "fake"].includes(merchant))
      throw Error("Require a separate merchant diagnostic");
    this.fixtureUsed = true;
    await this.raw({ cmd: "set_player", hp: 30, gold: 200, potions: ["FOUL_POTION", "BLOOD_POTION"] });
    const state = await this.raw(merchant === "real" ? { cmd: "enter_room", type: "shop" }
      : { cmd: "enter_room", type: "event", event: "FAKE_MERCHANT" });
    this.snapshot = await this.session.acceptNativeObservation(state, 15000);
    return this.observe();
  }
}

const worker = new MerchantMapWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let result;
      if (request.command === "initialize") result = await worker.initialize(request.spec);
      else if (request.command === "mount") result = await worker.mount(request.seed);
      else if (request.command === "load") result = await worker.mount(request.seed, request.save_json);
      else if (request.command === "merchant_fixture") result = await worker.merchantFixture(request.merchant);
      else if (request.command === "step") result = await worker.step(request);
      else if (request.command === "ending") result = await worker.ending();
      else if (request.command === "close") result = await worker.close();
      else throw Error("Undeclared merchant-map worker operation");
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
