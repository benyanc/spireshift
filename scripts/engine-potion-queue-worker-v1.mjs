// Private queue qualification only: never ordinary experience or a production action API.
import { NativeWorker } from "./engine-native-worker-v9.mjs";
import { createInterface } from "node:readline";
const worker = new NativeWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line); let value;
      if (request.command === "initialize") {
        if (request.spec.coverage_diagnostic !== true) throw Error("Queue qualification requires diagnostic isolation");
        value = await worker.initialize(request.spec);
      } else if (request.command === "mount") value = await worker.mount(request.seed);
      else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "inspect_queue") value = {
        identity: await worker.raw({ cmd: "run_identity" }), state: await worker.raw({ cmd: "observe" }) };
      else if (request.command === "legacy_discard") {
        try { await worker.step(request); throw Error("Legacy discard unexpectedly succeeded"); }
        catch (error) {
          if (!error.message.includes("Potion discard delivery is unknown")) throw error;
          value = { expected_legacy_error: error.message };
        }
      } else if (request.command === "legacy_finish_choice") {
        const state = await worker.raw({ cmd: "observe" });
        if (state.decision !== "card_select") throw Error("Expected the pending legacy card selection");
        value = { state: await worker.raw({ cmd: "action", action: "select_cards", args: {
          selection_ref: state.selection_ref, indices: state.cards.slice(0, state.min_select).map(c => c.index).join(",") } }),
          identity: await worker.raw({ cmd: "run_identity" }) };
      } else if (request.command === "reject_queued_discard") {
        const state = await worker.raw({ cmd: "observe" });
        const potion = state.player.potions.find(p => p.name === "Heart of Iron");
        if (!potion) throw Error("Queue negative control lost its exact potion");
        try {
          await worker.raw({ cmd: "action", action: "discard_potion", args: {
            potion_slot: request.stale_slot ? potion.slot + 1 : potion.slot, potion_ref: potion.native_ref } });
          throw Error("Queued/stale discard unexpectedly accepted");
        } catch (error) {
          const expected = request.stale_slot ? "observed potion is no longer" : "no longer natively discardable";
          if (!error.message.includes(expected)) throw error;
          value = { rejected: true, error: error.message };
        }
      } else if (request.command === "close") value = await worker.close();
      else throw Error("Unsupported private queue qualification request");
      console.log(JSON.stringify({ request_id: request.request_id, ok: true, value }));
      if (request.command === "close") { process.stdin.destroy(); break; }
    } catch (error) {
      console.log(JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message }));
      process.exitCode = 1; break;
    }
  }
} finally { await worker.stop(); }
