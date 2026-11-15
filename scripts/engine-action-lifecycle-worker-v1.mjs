import { createHash } from "node:crypto";
import { appendFileSync, readFileSync } from "node:fs";
import path from "node:path";
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";
import { SelectorWorker } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { CardAnswerPlanner } from "./engine-card-answer-v1.mjs";
import { projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { observeAfterMerchantExit } from "./engine-merchant-map-observation-v1.mjs";

const PROJECTION = "native_a8_action_lifecycle_v1";

// The ordinary learner still sends the same mount, step and ending requests.
// Privileged controls can enter a selected room in a disposable profile.
export class LifecycleWorker extends SelectorWorker {
  async initialize(spec) {
    const fixture = spec.lifecycle_fixture === true;
    if (this.spec || spec.boss_qualification !== PROJECTION || spec.confirmation_control !== false
        || (!fixture && !spec.lifecycle_adapter))
      throw Error("Require the pinned lifecycle worker");
    const adapters = [spec.confirmation_adapter];
    if (spec.lifecycle_adapter) adapters.push(spec.lifecycle_adapter);
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
        || identity.lifecycle_adapter_sha256 !== spec.lifecycle_adapter?.sha256
        || identity.pending_abandon_confirmation !== false)
      throw Error("Lifecycle adapters did not initialize on an empty worker");
    this.cursor = new CardAnswerPlanner();
    const Session = this.prepared.module.ManagedPlayerEnvironmentSession;
    this.prepared = { ...this.prepared, module: { ...this.prepared.module,
      ManagedPlayerEnvironmentSession: class extends Session {
        constructor(options) {
          super({ ...options, surfaceProjector: projectSelectionFlows });
        }
      }
    } };
    return { ...result, projection_contract: PROJECTION,
      decision_contract: "one_committed_ordered_answer_factorization_v1" };
  }

  async raw(request) {
    const response = await super.raw(request);
    return observeAfterMerchantExit(request, response, next => super.raw(next));
  }

  async combatFixture(hp) {
    if (this.spec.lifecycle_fixture !== true || this.fixtureUsed || !this.session
        || !Number.isSafeInteger(hp) || hp < 1 || hp > 80)
      throw Error("Require a fresh, declared combat diagnostic");
    this.fixtureUsed = true;
    await this.raw({ cmd: "set_player", hp, max_hp: 80,
      deck: ["STAMPEDE", "STRIKE_IRONCLAD"], potions: [] });
    const state = await this.raw({ cmd: "enter_room", type: "combat", encounter: "SPINY_TOAD_NORMAL" });
    this.snapshot = await this.session.acceptNativeObservation(state, 15000);
    return this.observe();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const worker = new LifecycleWorker();
  try {
    for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
      let request;
      try {
        request = JSON.parse(line);
        let value;
        if (request.command === "initialize") value = await worker.initialize(request.spec);
        else if (request.command === "mount") value = await worker.mount(request.seed);
        else if (request.command === "combat_fixture") value = await worker.combatFixture(request.hp);
        else if (request.command === "step") value = await worker.step(request);
        else if (request.command === "ending") value = await worker.ending();
        else if (request.command === "close") value = await worker.close();
        else throw Error("Undeclared lifecycle operation");
        console.log(JSON.stringify({ request_id: request.request_id, ok: true, value }));
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
}
