// Native A8 worker using the shared card selector and shop-read rules.
import { appendFileSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { gzipSync } from "node:zlib";
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { CardAnswerPlanner } from "./engine-card-answer-v1.mjs";
import { projectSelectionFlows, selectionFlowReads } from "./engine-combat-selector-belt-v2.mjs";
import { publicShopSlots } from "./engine-interface-contract-v3.mjs";
import { checkNativeEnding } from "./engine-native-ending-v1.mjs";
import { runtimeErrors } from "./engine-native-runtime-errors-v1.mjs";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { inspectRunInput } from "./engine-run-contract-v7.mjs";
import { chooseRunAction, newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { prepareRestSave } from "./engine-rest-bridge-contract.mjs";

export const PROJECTION = "native_a8_shared_card_selector_v1";
const journal = (directory, name, row) =>
  appendFileSync(path.join(directory, name + ".jsonl.gz"), gzipSync(JSON.stringify(row) + "\n"));

export function flowWorkerInput(snapshot, reads, navigation) {
  const owned = publicShopSlots(snapshot, reads);
  return publicPolicyInput(owned.snapshot, owned.reads, navigation);
}

export class SelectorWorker extends NativeWorker {
  async initialize(spec) {
    if (this.spec || spec.boss_qualification !== PROJECTION || spec.confirmation_control !== false)
      throw Error("Require the pinned shared-selector worker");
    const adapter = spec.confirmation_adapter;
    if (!adapter || !path.isAbsolute(adapter.path)
        || createHash("sha256").update(readFileSync(adapter.path)).digest("hex") !== adapter.sha256)
      throw Error("Frozen confirmation adapter changed");
    appendFileSync(path.join(spec.attempt, "profile-isolation.sb"),
      "(deny file-write* (subpath " + JSON.stringify(path.dirname(adapter.path)) + "))\n");
    const prior = process.env.DOTNET_STARTUP_HOOKS;
    process.env.DOTNET_STARTUP_HOOKS = adapter.path;
    let identity;
    try { identity = await super.initialize(spec); }
    finally {
      if (prior === undefined) delete process.env.DOTNET_STARTUP_HOOKS;
      else process.env.DOTNET_STARTUP_HOOKS = prior;
    }
    if (identity.initial_identity.confirmation_adapter_sha256 !== adapter.sha256
        || identity.initial_identity.pending_abandon_confirmation !== false)
      throw Error("Native confirmation adapter did not initialize cleanly");
    this.cursor = new CardAnswerPlanner();
    return {...identity, projection_contract: PROJECTION,
      decision_contract: "one_committed_ordered_answer_factorization_v1"};
  }

  async mount(seed, save = null) {
    if (this.session || this.closed || !/^[A-Z0-9]+$/u.test(seed))
      throw Error("Require one fresh canonical normal start per worker");
    const fixture = save !== null;
    if (fixture && (this.spec.selector_fixture !== true || typeof save !== "string"))
      throw Error("Shop fixtures require the declared diagnostic worker");
    this.navigation = newDiagnosticNavigation();
    this.index = 0;
    let pending = fixture;
    this.session = new this.prepared.module.ManagedPlayerEnvironmentSession({
      process: {request: request => {
        if (!fixture || request.cmd !== "start_run") return this.raw(request);
        if (!pending) throw Error("A diagnostic save can only be loaded once");
        pending = false;
        return this.raw({cmd: "load_save", json: save});
      }}, character: "Ironclad", ascension: 8,
      runtimeInstanceId: this.runtimeId, environmentFingerprint: this.spec.environment_fingerprint,
      surfaceProjector: projectSelectionFlows, readProjector: selectionFlowReads, validateSdk: true,
    });
    this.snapshot = await this.session.mount({seed, reset: false});
    const identity = await this.raw({cmd: "run_identity"});
    if (!identity.active || identity.seed !== seed || identity.ascension !== 8
        || identity.content_policy !== (fixture ? "serialized_native" : this.spec.content_policy)
        || (!fixture && (identity.native_unlock_run_count !== 999999999 || identity.started_with_neow !== true))
        || identity.native_game_over || identity.native_player_dead
        || identity.pending_abandon_confirmation !== false || identity.native_abandoned !== false)
      throw Error("Native start has the wrong profile, seed or ending state");
    this.episodes++;
    return {...await this.observe(), private_start_identity: identity,
      native_process_id: this.child.pid, episode: this.episodes, reset: false,
      ...(fixture ? {privileged_fixture: true} : {})};
  }

  async prepareShop(seed, cardCount) {
    if (this.spec.selector_fixture !== true || ![3, 13].includes(cardCount))
      throw Error("Require the declared three- or thirteen-card shop diagnostic");
    await this.mount(seed);
    const deck = Array.from({length: cardCount}, (_, i) =>
      ["STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "BASH"][i % 3]);
    await this.raw({cmd: "set_player", max_hp: 80, hp: 48, gold: 1000, potions: [], deck});
    const file = path.join(this.spec.profile, "selector-shop-source.save");
    const result = await this.raw({cmd: "write_continue_save", path: file, preserve_current_room: true});
    if (result.success !== true) throw Error("Native selector fixture save failed");
    const native = readFileSync(file);
    const save = prepareRestSave(JSON.parse(native)), map = save.acts[0].saved_map, player = save.players[0];
    map.start.type = "shop";
    const point = map.points.find(row => row.coord.row === map.start.coord.row && row.coord.col === map.start.coord.col);
    if (point) point.type = "shop";
    // MerchantRelicEntry pulls the shop tier from the back of the player's bag.
    // Arrange a copy of the bag with its existing Kifuda last. Native stock and
    // price generation, purchase, selector and enchantment still run in the game.
    const bag = player.relic_grab_bag.relic_id_lists.shop, key = "RELIC.KIFUDA";
    if (player.deck.length !== cardCount || player.gold !== 1000
        || !Array.isArray(bag) || bag.filter(item => item === key).length !== 1)
      throw Error("Missing the exact funded selector fixture and shop-tier relic");
    player.relic_grab_bag.relic_id_lists.shop = [...bag.filter(item => item !== key), key];
    return {save, original_save_sha256: createHash("sha256").update(native).digest("hex"),
      privileged_fixture: true, training_allowed: false};
  }

  async step(request) {
    const snapshot = this.snapshot, action = snapshot.bound_actions.actions[request.action_index];
    const local = this.cursor.active && action?.verb === "select";
    const result = await super.step(request);
    const delivery_domain = local ? "local_answer_factor" : "native";
    journal(this.spec.attempt, "answer-plan-deliveries", {index: this.index - 1,
      before_snapshot_id: snapshot.snapshot_id, successor_snapshot_id: this.snapshot.snapshot_id,
      action_id: action.bound_action_id, delivery_domain});
    return {...result, delivery_domain};
  }

  async observe() {
    const errors = runtimeErrors(this.child.diagnostics);
    if (errors.length) throw Error(`Native runtime error: ${errors[0].line}`);
    const snapshot = this.snapshot, reads = snapshot.reads.map(row => this.session.read({
      readId: row.read_id, expectedSnapshotId: snapshot.snapshot_id,
    }));
    this.facts = inspectRunInput(snapshot, reads, this.runtimeId);
    const model_input = flowWorkerInput(snapshot, reads, this.navigation);
    const public_key = createHash("sha256").update(stableJson(model_input)).digest("hex");
    const actions = snapshot.bound_actions.actions;
    const choice = this.facts.terminal ? null : this.cursor.active
      ? actions.find(a => a.verb === "confirm") ?? actions.find(a => a.verb === "select") ?? actions[0]
      : chooseRunAction(snapshot, undefined, this.navigation);
    const result = {snapshot, reads, facts: this.facts, model_input, public_key,
      default_action_index: choice == null ? null : actions.indexOf(choice), index: this.index};
    journal(this.spec.attempt, "public-observations", {episode: this.episodes, ...result});
    return {...result, usage: await this.usage()};
  }

  async ending() {
    if (!this.facts?.terminal) throw Error("Cannot label an unfinished game");
    const identity = await this.raw({cmd: "run_identity"});
    const agrees = checkNativeEnding({status: "candidate_terminal", victory: this.facts.victory}, identity);
    return {native_ending_evidence_agrees: agrees, private_final_identity: identity, usage: await this.usage()};
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const worker = new SelectorWorker();
  try {
    for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
      let request;
      try {
        request = JSON.parse(line);
        let value;
        if (request.command === "initialize") value = await worker.initialize(request.spec);
        else if (request.command === "mount") value = await worker.mount(request.seed);
        else if (request.command === "prepare_shop") value = await worker.prepareShop(request.seed, request.card_count);
        else if (request.command === "load_shop") {
          if (typeof request.save_json !== "string") throw Error("Missing prepared shop fixture");
          value = await worker.mount(request.seed, request.save_json);
        }
        else if (request.command === "step") value = await worker.step(request);
        else if (request.command === "ending") value = await worker.ending();
        else if (request.command === "close") value = await worker.close();
        else throw Error("Undeclared shared-selector worker operation");
        console.log(JSON.stringify({request_id: request.request_id, ok: true, value}));
        if (request.command === "close") { process.stdin.destroy(); break; }
      } catch (error) {
        console.log(JSON.stringify({request_id: request?.request_id, ok: false, error: error.message}));
        process.exitCode = 1;
        break;
      }
    }
  } finally {
    if (worker.child && !worker.closed) await worker.stop();
  }
}
