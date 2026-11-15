// Privileged fixture preparation and delivery through the current native selector.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { createInterface } from "node:readline";
import { SelectorWorker } from "./engine-a8-mixed-practice-worker-v2.mjs";
import { projectSelectionFlows } from "./engine-crystal-grid-v1.mjs";
import { selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { observeAfterMerchantExit } from "./engine-merchant-map-observation-v1.mjs";
import { prepareRestSave } from "./engine-rest-bridge-contract.mjs";

class RestWorker extends SelectorWorker {
  async raw(request) {
    const response = await super.raw(request);
    return observeAfterMerchantExit(request, response, next => super.raw(next));
  }

  async prepare(seed, relics, deck, belt) {
    if (this.spec.selector_fixture !== true || this.session)
      throw Error("Require a fresh privileged rest-site diagnostic");
    await this.mount(seed);
    await this.raw({ cmd: "set_player", max_hp: 80, hp: 31, deck, potions: belt, obtain_relics: relics });
    const file = path.join(this.spec.profile, "mixed-rest-source.save");
    const saved = await this.raw({ cmd: "write_continue_save", path: file, preserve_current_room: true });
    if (saved.success !== true) throw Error("Native rest fixture save failed");
    const bytes = readFileSync(file);
    return { save: prepareRestSave(JSON.parse(bytes)), source_sha256: createHash("sha256").update(bytes).digest("hex") };
  }

}

const worker = new RestWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let result;
      if (request.command === "initialize") {
        if (request.spec.selector_fixture !== true) throw Error("Rest fixtures require their private worker");
        result = await worker.initialize(request.spec);
        // Use the same projectors as the current ordinary learner.
        const CurrentSession = worker.prepared.module.ManagedPlayerEnvironmentSession;
        worker.prepared = { ...worker.prepared, module: { ...worker.prepared.module,
          ManagedPlayerEnvironmentSession: class extends CurrentSession {
            constructor(options) {
              super({ ...options, surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads });
            }
          }
        } };
      } else if (request.command === "prepare") {
        result = await worker.prepare(request.seed, request.relics, request.deck, request.belt);
      } else if (request.command === "load") {
        if (typeof request.save_json !== "string") throw Error("Require the declared diagnostic save");
        result = await worker.mount(request.seed, request.save_json);
      } else if (request.command === "step") result = await worker.step(request);
      else if (request.command === "close") result = await worker.close();
      else throw Error("Undeclared rest diagnostic command");
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
