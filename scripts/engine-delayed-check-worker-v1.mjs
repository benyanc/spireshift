// Privileged delayed diagnostic only. Reuse v11 production projection/delivery.
import { NativeWorker } from "./engine-native-worker-v11.mjs";
import { createInterface } from "node:readline";

const worker = new NativeWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let value;
      if (request.command === "initialize") {
        if (request.spec.delayed_diagnostic !== true || request.spec.coverage_diagnostic !== true)
          throw Error("Use the separate privileged delayed diagnostic constructor");
        value = await worker.initialize(request.spec);
      } else if (request.command === "prepare_delayed") {
        if (!["vulnerable_then_attack", "dexterity_then_block"].includes(request.family)
          || ![0, 1, 2].includes(request.variant)) throw Error("Unknown frozen delayed fixture");
        await worker.mount(request.seed);
        await worker.raw({ cmd: "set_player", hp: 40, max_hp: 80, relics: [], potions: [] });
        const attack = request.family === "vulnerable_then_attack";
        const reversed = request.variant === 2;
        const setup = attack ? "THUNDERCLAP" : "FOOTWORK";
        const followup = attack ? "BLUDGEON" : "DEFEND_IRONCLAD";
        const fixture = await worker.raw({ cmd: "coverage_fixture", fixture: {
          card_id: reversed ? followup : setup, copies: 1,
          upgrade: reversed ? 0 : request.variant, funded: attack,
          hand_extra: reversed ? setup : followup
        } });
        worker.snapshot = await worker.session.acceptNativeObservation(fixture, 15000);
        let current = await worker.observe();
        if (!attack) {
          for (let turn = 0; turn < 3 && !current.model_input.context.interaction.content.context.enemies.some(e => e.intends_attack); turn++) {
            const end = current.model_input.candidates.findIndex(c => c.verb === "end_turn");
            if (end < 0) throw Error("No verified End Turn during fixture preparation");
            current = await worker.step({ snapshot_id: worker.snapshot.snapshot_id, action_index: end });
          }
          const context = current.model_input.context.interaction.content.context;
          const damage = context.enemies.flatMap(e => e.intents)
            .reduce((sum, i) => sum + (i.total_damage ?? (i.damage == null ? 0 : i.damage * (i.hits ?? 1))), 0);
          const defend = current.model_input.candidates.find(c => c.subject?.properties?.definition_id === "DEFEND_IRONCLAD");
          const block = defend?.subject?.properties?.stats?.block;
          const hp = damage - block;
          if (!(block > 0) || !Number.isSafeInteger(hp) || hp < 1 || hp > 25)
            throw Error("Fixture needs an advertised attack exceeding native base block");
          await worker.raw({ cmd: "set_player", hp });
          const state = await worker.raw({ cmd: "observe" });
          worker.snapshot = await worker.session.acceptNativeObservation(state, 15000);
          current = await worker.observe();
        }
        value = current;
      } else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "close") value = await worker.close();
      else throw Error("Unsupported delayed diagnostic operation");
      console.log(JSON.stringify({ request_id: request.request_id, ok: true, value }));
      if (request.command === "close") { process.stdin.destroy(); break; }
    } catch (error) {
      console.log(JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message }));
      process.exitCode = 1; break;
    }
  }
} finally { await worker.stop(); }
