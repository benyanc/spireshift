// Private fixtures use the same patched worker and current public action path.
import { createInterface } from "node:readline";
import { LifecycleWorker } from "./engine-action-lifecycle-worker-v1.mjs";

class SelectorLifecycleWorker extends LifecycleWorker {
  async prepareHandoff(seed, count) {
    if (this.spec.lifecycle_fixture !== true) throw Error("Require a private lifecycle fixture");
    const result = await this.prepareShop(seed, count);
    const player = result.save.players[0];
    if (player.current_hp !== 48 || player.max_hp !== 80 || (player.potions ?? []).length)
      throw Error("Unexpected native shop preparation");
    player.potions = [
      { id: "POTION.BLOOD_POTION", slot_index: 0 },
      { id: "POTION.FOUL_POTION", slot_index: 1 },
    ];
    return result;
  }

  async rewardFixture(seed) {
    if (this.spec.lifecycle_fixture !== true || this.fixtureUsed || this.session)
      throw Error("Require a fresh reward lifecycle fixture");
    this.fixtureUsed = true;
    await this.mount(seed);
    await this.raw({ cmd: "set_player", hp: 48, max_hp: 80, gold: 0,
      potions: ["BLOOD_POTION", "FOUL_POTION"] });
    const state = await this.raw({ cmd: "coverage_fixture",
      fixture: { card_id: "BLUDGEON", upgrade: 1, copies: 5, funded: true } });
    this.snapshot = await this.session.acceptNativeObservation(state, 15000);
    return this.observe();
  }
}

const worker = new SelectorLifecycleWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let result;
      if (request.command === "initialize") result = await worker.initialize(request.spec);
      else if (request.command === "prepare") result = await worker.prepareHandoff(request.seed, request.count);
      else if (request.command === "load") result = await worker.mount(request.seed, request.save_json);
      else if (request.command === "reward_fixture") result = await worker.rewardFixture(request.seed);
      else if (request.command === "step") result = await worker.step(request);
      else if (request.command === "inspect") result = await worker.raw({ cmd: "run_identity" });
      else if (request.command === "close") result = await worker.close();
      else throw Error("Undeclared selector lifecycle request");
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
