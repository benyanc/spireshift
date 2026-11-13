// Privileged diagnostics only. Never used as an ordinary learner/evaluation worker.
import { NativeWorker } from "./engine-native-worker-v9.mjs";
import { createInterface } from "node:readline";
const worker = new NativeWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let value;
      if (request.command === "initialize") {
        if (request.spec.coverage_diagnostic !== true) throw Error("Privileged coverage requires its separate entry point");
        value = await worker.initialize(request.spec);
      } else if (request.command === "catalog") {
        await worker.mount("SP1RESH1FTCATALOG001");
        value = await worker.raw({ cmd: "mechanics_catalog" });
      }
      else if (request.command === "mount") value = await worker.mount(request.seed);
      else if (request.command === "fixture") {
        if (!worker.session) throw Error("Mount the disposable diagnostic episode first");
        const state = await worker.raw({ cmd: "coverage_fixture", fixture: request.fixture });
        worker.snapshot = await worker.session.acceptNativeObservation(state, 15000);
        value = await worker.observe();
      } else if (request.command === "potion_fixture") {
        if (!worker.session) throw Error("Mount the diagnostic episode first");
        await worker.raw({ cmd: "set_player", hp: 30, gold: 200, potions: request.potions });
        let state;
        if (request.room === "reward") state = await worker.raw({ cmd: "coverage_fixture", fixture: { reward_cards: true } });
        else {
          state = await worker.raw({ cmd: "enter_room", type: request.room === "map" ? "shop" : request.room,
            ...(request.event ? { event: request.event } : {}) });
          if (request.room === "map") state = await worker.raw({ cmd: "action", action: "leave_shop", args: { room_ref: state.room_ref } });
        }
        worker.snapshot = await worker.session.acceptNativeObservation(state, 15000);
        value = await worker.observe();
      } else if (request.command === "reject_potion_action") {
        // Dedicated negative-control worker; caller retires it after this request.
        try { await worker.raw(request.payload); throw Error("Malformed potion action was accepted"); }
        catch (error) {
          if (!error.message.includes(request.expected_error)) throw error;
          value = { rejected: true, error: error.message };
        }
      } else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "close") value = await worker.close();
      else throw Error("Unsupported coverage control");
      console.log(JSON.stringify({ request_id: request.request_id, ok: true, value }));
      if (request.command === "close") { process.stdin.destroy(); break; }
    } catch (error) {
      console.log(JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message }));
      process.exitCode = 1; break;
    }
  }
} finally { await worker.stop(); }
