// Named privileged shop scenarios. This is never a policy rollout or training dataset.
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";

export function shopPurchase(state, kind, index = 0) {
  const entry = kind === "remove_card" ? state.card_removal : state[{
    buy_card: "cards", buy_relic: "relics", buy_potion: "potions"
  }[kind]]?.[index];
  if (state?.decision !== "shop" || typeof entry?.native_ref !== "string")
    throw new Error(`Missing current shop entry ${kind}`);
  return { cmd: "action", action: kind, args: { entry_ref: entry.native_ref,
    quoted_cost: entry.cost, ...(entry.item_ref == null ? {} : { item_ref: entry.item_ref }) } };
}
export const selectionInput = (state, cancel = false) => ({ cmd: "action",
  action: cancel ? "skip_select" : "select_cards", args: {
    ...(cancel ? {} : { indices: "0" }), ...(state.selection_ref == null ? {} : { selection_ref: state.selection_ref }) } });

export async function checkShopScenarios(request, gates) {
  let bootstraps = 0;
  const check = (key, ok) => { gates[key] = ok === true; };
  const fixture = async (name, extras = {}) => {
    bootstraps++;
    await request({ cmd: bootstraps === 1 ? "start_run" : "reset_run", character: "Ironclad",
      ascension: 8, seed: `SPIRESHIFTSHOP${name}`, lang: "en" });
    const id = await request({ cmd: "run_identity" });
    check(`${name}_native_A8`, id.active === true && id.ascension === 8);
    const setup = await request({ cmd: "set_player", gold: 10000, ...extras });
    if (setup.type !== "ok") throw new Error(`Shop fixture setup failed: ${name}`);
    const state = await request({ cmd: "enter_room", type: "shop" });
    if (state.decision !== "shop") throw new Error(`Native shop missing: ${name}`);
    return state;
  };
  const pending = (name, state) => {
    if (state.decision !== "card_select") throw new Error(`Native removal selection missing: ${name}`);
    check(`${name}_native_selection_preferences_retained`, state.cancelable === true
      && state.require_manual_confirmation === true && state.min_select === 1 && state.max_select === 1
      && typeof state.selection_ref === "string");
  };
  let state = await fixture("NORMAL");
  const original = state, purchase = shopPurchase(state, "buy_card");
  state = await request(purchase);
  check("ordinary_card_native_commit", state.decision === "shop"
    && state.player.gold === original.player.gold - original.cards[0].cost
    && state.player.deck.length === original.player.deck.length + 1);
  check("consumed_card_refused", (await request(purchase)).type === "error");
  const firstGold = state.player.gold, second = state.cards.findIndex((row) => row.can_purchase);
  const price = state.cards[second].cost;
  state = await request(shopPurchase(state, "buy_card", second));
  check("shop_remains_available_after_second_purchase", state.decision === "shop" && state.player.gold === firstGold - price);
  state = await request({ cmd: "action", action: "leave_shop", args: { room_ref: state.room_ref } });
  check("explicit_shop_leave_opens_map", state.decision === "map_select");

  state = await fixture("REMOVAL");
  const before = state;
  state = await request(shopPurchase(state, "remove_card")); pending("removal", state);
  state = await request(selectionInput(state, true));
  check("removal_cancel_preserves_gold_deck_and_service", state.decision === "shop"
    && state.player.gold === before.player.gold && state.player.deck.length === before.player.deck.length
    && state.card_removal.is_stocked === true);
  state = await request(shopPurchase(state, "remove_card")); pending("removal_retry", state);
  state = await request(selectionInput(state));
  check("removal_native_effects_commit", state.decision === "shop"
    && state.player.gold === before.player.gold - before.card_removal.cost && state.player.deck.length === before.player.deck.length - 1);
  check("successful_removal_marks_native_service_used", state.card_removal.is_stocked === false && state.card_removal.can_purchase === false);
  check("repeat_removal_refused", (await request(shopPurchase(state, "remove_card"))).type === "error");

  state = await fixture("COURIER", { obtain_relics: ["THE_COURIER"] });
  const old = shopPurchase(state, "buy_card");
  const cost = state.cards[0].cost, gold = state.player.gold;
  state = await request(old);
  check("courier_native_purchase_and_restock", state.decision === "shop" && state.cards[0].is_stocked === true
    && state.player.gold === gold - cost);
  check("restocked_item_has_new_binding", typeof state.cards[0].item_ref === "string"
    && state.cards[0].item_ref !== old.args.item_ref);
  check("old_restocked_item_quote_refused", (await request(old)).type === "error");
  const staleQuote = shopPurchase(state, "buy_card"); staleQuote.args.quoted_cost += 1;
  check("changed_price_quote_refused", (await request(staleQuote)).type === "error");

  state = await fixture("POTIONS", { obtain_relics: ["THE_COURIER"] });
  for (let count = 0; count < state.player.max_potion_slots; count++) {
    state = await request(shopPurchase(state, "buy_potion"));
    if (state.decision !== "shop") throw new Error("Potion purchase did not return shop");
  }
  check("full_native_potion_capacity_observed", state.player.potions.length === state.player.max_potion_slots);
  check("full_potion_slots_not_offered_as_purchase", state.potions.every((row) => row.can_purchase === false));
  const fullGold = state.player.gold;
  const fullResponse = await request(shopPurchase(state, "buy_potion"));
  check("full_potion_purchase_refused", fullResponse.type === "error");
  check("full_potion_refusal_preserves_gold", fullResponse.type === "error" || fullResponse.player?.gold === fullGold);

  state = await fixture("SOZU", { obtain_relics: ["SOZU"] });
  check("native_forbidden_potions_not_offered_as_purchase", state.potions.every((row) => row.can_purchase === false));
  check("forbidden_potion_purchase_refused", (await request(shopPurchase(state, "buy_potion"))).type === "error");

  state = await fixture("MODAL");
  const shop = state;
  state = await request(shopPurchase(state, "remove_card")); pending("modal", state);
  check("shop_purchase_while_selection_pending_refused", (await request(shopPurchase(shop, "buy_card"))).type === "error");
  check("shop_leave_while_selection_pending_refused", (await request({ cmd: "action", action: "leave_shop",
    args: { room_ref: shop.room_ref } })).type === "error");
  const wrong = selectionInput(state); wrong.args.selection_ref = "stale-selection";
  check("wrong_selection_binding_refused", (await request(wrong)).type === "error");
  state = await request(selectionInput(state, true));
  check("modal_cancel_restores_shop", state.decision === "shop");

  state = await fixture("SINGLE", { deck: ["STRIKE_IRONCLAD"] });
  const single = state;
  state = await request(shopPurchase(state, "remove_card")); pending("single_removal", state);
  check("single_card_removal_still_waits", state.cards.length === 1);
  state = await request(selectionInput(state, true));
  check("single_card_removal_can_cancel", state.decision === "shop" && state.player.deck.length === 1 && state.player.gold === single.player.gold);
  state = await request(shopPurchase(state, "remove_card")); pending("single_removal_retry", state);
  state = await request(selectionInput(state));
  check("single_card_explicit_removal_commits_once", state.decision === "shop" && state.player.deck.length === 0
    && state.player.gold === single.player.gold - single.card_removal.cost && state.card_removal.is_stocked === false);
  return bootstraps;
}

async function main(spec) {
  const gates = {};
  let child, result = { status: "shop_probe_incomplete", gates, privileged_scenarios: true,
    full_run_attempts: 0, optimizer_steps: 0, training_allowed: false };
  try {
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    if (hashFile(spec.artifact) !== spec.expected.artifact_sha256) throw new Error("CLI artifact drifted");
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact],
      cwd: spec.profile, env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"),
        STS2_GAME_DIR: spec.game_data }, readyTimeoutMs: 15_000, diagnosticLimit: 10000 });
    child = started.process;
    const request = async (payload) => {
      const response = await child.request(payload, 15_000);
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`);
      return response;
    };
    const identity = await request({ cmd: "runtime_identity" }); result.runtime_identity = identity;
    gates.runtime_identity_bound = identity.process_id === child.pid && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256 && identity.managed_runtime_version === spec.managed_runtime_version;
    if (!gates.runtime_identity_bound) throw new Error("Native shop identity did not bind");
    result.native_run_bootstraps = await checkShopScenarios(request, gates);
    await request({ cmd: "quit" }); result.exit = await child.exit;
    gates.natural_exit = result.exit.code === 0 && result.exit.signal === null;
    if (Object.values(gates).every((value) => value === true)) result.status = "shop_native_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) {
      result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics, null, 2));
      result.diagnostic_entries_retained = child.diagnostics.length;
    }
    writeFileSync(path.join(spec.attempt, "shop-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, failed: Object.keys(gates).filter((key) => !gates[key]), error: result.error ?? null }));
  if (result.status !== "shop_native_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
