// Privileged, short-horizon learning diagnostics. Never an ordinary full-run worker.
import { NativeWorker } from "./engine-native-worker-v10.mjs";
import { createInterface } from "node:readline";
const worker = new NativeWorker();
try {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      let value;
      if (request.command === "initialize") {
        if (request.spec.tactical_diagnostic !== true || request.spec.coverage_diagnostic !== true)
          throw Error("Use the separately marked tactical diagnostic constructor");
        value = await worker.initialize(request.spec);
      } else if (request.command === "prepare_tactical") {
        if (!["finish_combat", "survive_turn"].includes(request.family)) throw Error("Unknown tactical task");
        await worker.mount(request.seed);
        await worker.raw({ cmd: "set_player", relics: [], potions: [] });
        const attack = request.family === "finish_combat";
        const fixture = await worker.raw({ cmd: "coverage_fixture", fixture: {
          card_id: attack ? "WHIRLWIND" : "DEFEND_IRONCLAD", copies: 1,
          upgrade: 0, funded: attack,
          hand_extra: attack ? "DEFEND_IRONCLAD" : "STRIKE_IRONCLAD"
        } });
        worker.snapshot = await worker.session.acceptNativeObservation(fixture, 15000);
        let current = await worker.observe();
        let hp = 1;
        if (!attack) {
          for (let turn = 0; turn < 3 && !current.model_input.context.interaction.content.context.enemies.some(e => e.intends_attack); turn++) {
            const index = current.model_input.candidates.findIndex(c => c.verb === "end_turn");
            if (index < 0) throw Error("No verified End Turn during fixture setup");
            current = await worker.step({ snapshot_id: worker.snapshot.snapshot_id, action_index: index });
          }
          const context = current.model_input.context.interaction.content.context;
          const damage = context.enemies.flatMap(e => e.intents).reduce((sum, i) => sum + (i.total_damage ?? (i.damage == null ? 0 : i.damage * (i.hits ?? 1))), 0);
          const defend = current.model_input.candidates.find(c => c.subject?.properties?.definition_id === "DEFEND_IRONCLAD");
          const block = defend?.subject?.properties?.stats?.block;
          if (!(damage > 0) || !(block > 0)) throw Error("Fixture needs a visible attack and playable native block");
          hp = Math.max(1, damage - block + 1);
          if (!Number.isSafeInteger(hp) || hp > 20) throw Error("Fixture health outside its finite diagnostic scope");
        }
        await worker.raw({ cmd: "set_player", hp });
        const state = await worker.raw({ cmd: "observe" });
        worker.snapshot = await worker.session.acceptNativeObservation(state, 15000);
        value = await worker.observe();
      } else if (request.command === "step") value = await worker.step(request);
      else if (request.command === "close") value = await worker.close();
      else throw Error("Unsupported tactical diagnostic operation");
      console.log(JSON.stringify({ request_id: request.request_id, ok: true, value }));
      if (request.command === "close") { process.stdin.destroy(); break; }
    } catch (error) {
      console.log(JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message }));
      process.exitCode = 1; break;
    }
  }
} finally { await worker.stop(); }
