// Reuse the verified selector worker with a dedicated Crystal Sphere surface.
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { PROJECTION as SELECTORS, SelectorWorker } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";

export const PROJECTION = "native_a8_crystal_grid_v1";

class GridWorker extends SelectorWorker {
  async initialize(spec) {
    if (spec.boss_qualification !== PROJECTION)
      throw Error("Require the pinned Crystal Sphere projection");
    const result = await super.initialize({ ...spec, boss_qualification: SELECTORS });
    return { ...result, projection_contract: PROJECTION };
  }

  async mount(seed) {
    if (this.session || this.closed || !/^[A-Z0-9]+$/u.test(seed))
      throw Error("Require one fresh canonical normal start per worker");
    this.navigation = newDiagnosticNavigation();
    this.index = 0;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({
      process: { request: request => this.raw(request) }, character: "Ironclad", ascension: 8,
      runtimeInstanceId: this.runtimeId, environmentFingerprint: this.spec.environment_fingerprint,
      surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads, validateSdk: true,
    });
    this.snapshot = await this.session.mount({ seed, reset: false });
    const identity = await this.raw({ cmd: "run_identity" });
    if (!identity.active || identity.seed !== seed || identity.ascension !== 8
        || identity.content_policy !== this.spec.content_policy
        || identity.native_unlock_run_count !== 999999999 || identity.started_with_neow !== true
        || identity.native_game_over || identity.native_player_dead
        || identity.pending_abandon_confirmation !== false || identity.native_abandoned !== false)
      throw Error("Native start has the wrong profile, seed or ending state");
    this.episodes++;
    return { ...await this.observe(), private_start_identity: identity,
      native_process_id: this.child.pid, episode: this.episodes, reset: false };
  }

  async gridFixture(seed) {
    if (this.spec.grid_fixture !== true) throw Error("Require a separate Crystal Sphere diagnostic");
    await this.mount(seed);
    await this.raw({ cmd: "set_player", hp: 30, gold: 200, potions: [] });
    const state = await this.raw({ cmd: "enter_room", type: "event", event: "CRYSTAL_SPHERE" });
    this.snapshot = await this.session.acceptNativeObservation(state, 15000);
    return this.observe();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const worker = new GridWorker();
  try {
    for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
      let request;
      try {
        request = JSON.parse(line);
        let value;
        if (request.command === "initialize") value = await worker.initialize(request.spec);
        else if (request.command === "mount") value = await worker.mount(request.seed);
        else if (request.command === "grid_fixture") value = await worker.gridFixture(request.seed);
        else if (request.command === "step") value = await worker.step(request);
        else if (request.command === "ending") value = await worker.ending();
        else if (request.command === "close") value = await worker.close();
        else throw Error("Undeclared Crystal Sphere worker operation");
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
