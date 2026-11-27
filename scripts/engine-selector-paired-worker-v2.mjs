// Both execution hosts load these exact serialized, explicitly privileged fixtures.
import {createInterface} from "node:readline";
import {InventoryLifecycleWorker} from "./engine-inventory-lifecycle-worker-v1.mjs";
import {requireCanonicalSeed} from "./engine-seed-contract-v1.mjs";

class PairedWorker extends InventoryLifecycleWorker {
  async prepare(seed, count, reward) {
    requireCanonicalSeed(seed);
    if (!this.spec.lifecycle_fixture || typeof reward !== "boolean") throw Error("Undeclared paired fixture");
    const result = await this.prepareShop(seed, count), player = result.save.players[0];
    player.potions = [{id:"POTION.BLOOD_POTION",slot_index:0},{id:"POTION.FOUL_POTION",slot_index:1}];
    if (reward) {
      const map = result.save.acts[0].saved_map;
      map.start.type = "monster";
      const start = map.points.find(p => p.coord.col === map.start.coord.col && p.coord.row === map.start.coord.row);
      if (start) start.type = "monster";
      player.deck = Array.from({length:5}, () => ({id:"CARD.BLUDGEON",current_upgrade_level:1}));
      player.max_energy = 20;
      player.gold = 0;
    }
    return result;
  }
}

const worker = new PairedWorker();
try {
  for await (const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
    let request;
    try {
      request = JSON.parse(line);
      let value;
      if (request.command === "initialize") value = await worker.initialize(request.spec);
      else if (request.command === "prepare") value = await worker.prepare(request.seed,request.count,request.reward);
      else if (request.command === "load") value = await worker.mount(request.seed,request.save_json);
      else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "inspect") value = await worker.raw({cmd:"run_identity"});
      else if (request.command === "close") value = await worker.close();
      else throw Error("Undeclared paired selector request");
      console.log(JSON.stringify({request_id:request.request_id,ok:true,value}));
      if (request.command === "close") {process.stdin.destroy();break;}
    } catch (error) {
      console.log(JSON.stringify({request_id:request?.request_id,ok:false,error:error.message}));
      process.exitCode = 1;break;
    }
  }
} finally {
  if (worker.child && !worker.closed) await worker.stop();
}
