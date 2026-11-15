// Named privileged native combat fixtures. No complete runs or learner updates.
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";

const id = (card) => card?.id?.replace(/^CARD\./u, "");
const card = (state, name) => state.hand?.find((row) => id(row) === name);
const status = (state, name) => state.player_statuses?.find((row) => row.id === name)?.amount ?? 0;
export function combatPlay(state, name, target = 0) {
  const current = typeof name === "string" ? card(state, name) : name;
  if (state.decision !== "combat_play" || !current?.native_ref) throw new Error(`Missing native hand card ${name}`);
  return { cmd: "action", action: "play_card", args: { card_ref: current.native_ref,
    ...(["AnyEnemy", "AnyAlly"].includes(current.target_type) ? { target_ref: state.enemies[target].native_ref } : {}) } };
}
export function combatPotion(state, name) {
  const current = state.player.potions.find((row) => row.id === name);
  if (!current) throw new Error(`Missing native potion ${name}`);
  return { cmd: "action", action: "use_potion", args: { potion_slot: current.slot, potion_ref: current.native_ref,
    ...(current.target_type === "AnyEnemy" ? { target_ref: state.enemies[0].native_ref }
      : current.target_type === "AnyPlayer" ? { target_ref: state.player.native_ref } : {}) } };
}

export async function checkCombatScenarios(request, gates) {
  let bootstraps = 0;
  const check = (name, ok) => { gates[name] = ok === true; };
  const fixture = async (name, deck, extras = {}) => {
    bootstraps++;
    await request({ cmd: bootstraps === 1 ? "start_run" : "reset_run", character: "Ironclad",
      ascension: 8, seed: `SPIRESHIFTCOMBAT${name}`, lang: "en" });
    const identity = await request({ cmd: "run_identity" });
    check(`${name}_native_A8`, identity.active === true && identity.ascension === 8);
    const setup = await request({ cmd: "set_player", deck, ...extras });
    if (setup.type !== "ok" || setup.player.deck.length !== deck.length) throw new Error(`Invalid native combat fixture ${name}`);
    const state = await request({ cmd: "enter_room", type: "combat", encounter: "SHRINKER_BEETLE_WEAK" });
    if (state.decision !== "combat_play") throw new Error(`Native combat missing: ${name}`);
    check(`${name}_public_play_phase`, state.is_play_phase === true && state.turn_owner === "player");
    return state;
  };
  const play = async (state, name) => {
    const next = await request(combatPlay(state, name));
    if (next.type !== "decision") throw new Error(`Native play failed: ${name}: ${next.error}`);
    return next;
  };
  const end = (state) => request({ cmd: "action", action: "end_turn", args: { player_ref: state.player.native_ref } });

  let state = await fixture("ENERGY", ["STRIKE_IRONCLAD", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "BASH", "BLUDGEON"]);
  const copies = state.hand.filter((row) => id(row) === "STRIKE_IRONCLAD");
  check("duplicate_cards_have_distinct_native_bindings", copies.length === 2 && copies[0].native_ref !== copies[1].native_ref);
  const staleCard = combatPlay(state, copies[0]);
  const oldTarget = state.enemies[0].native_ref;
  state = await play(state, copies[0]);
  check("native_play_spends_current_cost", state.energy === 2 && state.hand.some((row) => row.native_ref === copies[1].native_ref)
    && !state.hand.some((row) => row.native_ref === copies[0].native_ref) && state.enemies[0].native_ref === oldTarget);
  check("consumed_card_copy_refused", (await request(staleCard)).type === "error");
  state = await play(state, "STRIKE_IRONCLAD"); state = await play(state, "DEFEND_IRONCLAD");
  check("native_insufficient_energy_disables_attack", state.energy === 0 && card(state, "BASH").can_play === false);
  check("unplayable_card_refused_natively", (await request(combatPlay(state, "BASH"))).type === "error");
  state = await end(state);
  check("native_end_turn_refreshes_hand_energy_and_round", state.decision === "combat_play" && state.energy === 3 && state.round === 2);

  state = await fixture("CORRUPTION", ["CORRUPTION", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "STRIKE_IRONCLAD", "BASH"]);
  state = await play(state, "CORRUPTION");
  check("native_global_cost_reduction_visible", state.energy === 0 && card(state, "DEFEND_IRONCLAD").cost === 0
    && card(state, "DEFEND_IRONCLAD").can_play === true && card(state, "STRIKE_IRONCLAD").can_play === false);
  check("corruption_status_owned_by_player", status(state, "CORRUPTION_POWER") === 1
    && state.enemies.every((row) => !row.statuses.some((power) => power.id === "CORRUPTION_POWER")));
  const defend = card(state, "DEFEND_IRONCLAD"); state = await play(state, defend);
  check("corruption_skill_exhausts_and_keeps_energy", state.energy === 0 && state.player.block === 5
    && state.exhaust_pile_count === 1 && state.combat_piles.find((row) => row.pile === "exhaust").cards.some((row) => row.native_ref === defend.native_ref));

  state = await fixture("VULNERABILITY", ["BASH", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD"]);
  state = await play(state, "BASH");
  const beforeStrike = state.enemies[0].hp;
  check("native_debuff_owned_by_exact_enemy", state.enemies[0].statuses.some((row) => row.id === "VULNERABLE_POWER" && row.amount === 2)
    && status(state, "VULNERABLE_POWER") === 0);
  state = await play(state, "STRIKE_IRONCLAD");
  check("vulnerability_applies_to_later_native_attack", beforeStrike - state.enemies[0].hp === 9);

  state = await fixture("STATS", ["INFLAME", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD"],
    { potions: ["STRENGTH_POTION", "DEXTERITY_POTION"] });
  state = await play(state, "INFLAME");
  const potion = combatPotion(state, "STRENGTH_POTION"), strength = await request(potion);
  check("native_player_targeted_potion_supported", strength.decision === "combat_play");
  if (strength.decision === "combat_play") {
    state = strength;
    check("consumed_potion_refused", (await request(potion)).type === "error");
    state = await request(combatPotion(state, "DEXTERITY_POTION"));
    if (state.decision !== "combat_play") throw new Error(`Native dexterity potion failed: ${state.message}`);
    check("strength_and_dexterity_are_owned_separate_facts", status(state, "STRENGTH_POWER") === 4 && status(state, "DEXTERITY_POWER") === 2);
    check("native_damage_and_block_previews_follow_separate_stats", card(state, "STRIKE_IRONCLAD").stats.damage === 10
      && card(state, "DEFEND_IRONCLAD").stats.block === 7);
    const hp = state.enemies[0].hp; state = await play(state, "STRIKE_IRONCLAD"); state = await play(state, "DEFEND_IRONCLAD");
    check("native_damage_and_block_match_stat_ownership", hp - state.enemies[0].hp === 10 && state.player.block === 7);
  }

  state = await fixture("ANGER", ["ANGER", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD"]);
  state = await play(state, "ANGER");
  const anger = state.combat_piles.find((row) => row.pile === "discard").cards.filter((row) => id(row) === "ANGER");
  check("native_generated_copy_has_distinct_identity", state.energy === 3 && anger.length === 2 && anger[0].native_ref !== anger[1].native_ref);

  state = await fixture("BLOODLETTING", ["BLOODLETTING", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD"]);
  const ownHp = state.player.hp; state = await play(state, "BLOODLETTING");
  check("native_hp_cost_precedes_energy_gain", state.player.hp === ownHp - 3 && state.energy === 5);

  state = await fixture("SECONDWIND", ["SECOND_WIND", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "BURN", "STRIKE_IRONCLAD"]);
  check("status_card_not_playable", card(state, "BURN").can_play === false);
  state = await play(state, "SECOND_WIND");
  check("native_exhaust_block_and_retained_attack", state.exhaust_pile_count === 3 && state.player.block === 15
    && state.hand.length === 1 && id(state.hand[0]) === "STRIKE_IRONCLAD" && state.energy === 2);

  state = await fixture("DRAW", Array(10).fill("BATTLE_TRANCE"));
  const drawBefore = state.draw_pile_count; state = await play(state, "BATTLE_TRANCE");
  check("native_draw_updates_all_pile_counts", state.hand.length === 7 && state.draw_pile_count === drawBefore - 3 && state.discard_pile_count === 1);
  check("native_no_draw_status_visible", status(state, "NO_DRAW_POWER") === 1);
  const drawAfter = state.draw_pile_count; state = await play(state, "BATTLE_TRANCE");
  check("native_no_draw_blocks_later_card_draw", state.hand.length === 6 && state.draw_pile_count === drawAfter);

  state = await fixture("XCOST", ["WHIRLWIND", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD"]);
  check("native_X_cost_is_displayed_as_X", card(state, "WHIRLWIND").cost === "X");
  const xHp = state.enemies[0].hp; state = await play(state, "WHIRLWIND");
  check("native_X_cost_uses_live_energy", state.energy === 0 && xHp - state.enemies[0].hp === 15);

  state = await fixture("ARMAMENTS", ["ARMAMENTS", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "BASH", "STRIKE_IRONCLAD"]);
  state = await play(state, "ARMAMENTS");
  check("native_hand_upgrade_has_complete_selection_preferences", state.decision === "card_select"
    && state.selection_preferences_complete === true && state.min_select === 1 && state.max_select === 1 && state.cancelable === false);
  if (state.decision !== "card_select") throw new Error("Armaments did not open native hand upgrade");
  const upgradedRef = state.cards[0].native_ref;
  state = await request({ cmd: "action", action: "select_cards", args: { selection_ref: state.selection_ref, indices: "0" } });
  check("native_hand_upgrade_resumes_card_effects", state.decision === "combat_play"
    && state.hand.some((row) => row.native_ref === upgradedRef && row.is_upgraded) && state.player.block === 5 && state.energy === 2);

  state = await fixture("TARGET", ["STRIKE_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD", "DEFEND_IRONCLAD"]);
  const wrong = combatPlay(state, "STRIKE_IRONCLAD"); wrong.args.target_ref = "not-a-native-enemy";
  check("wrong_creature_target_refused", (await request(wrong)).type === "error");
  state = await play(state, "STRIKE_IRONCLAD");
  check("valid_action_after_target_refusal", state.decision === "combat_play" && state.energy === 2);

  state = await fixture("TURN", Array(5).fill("DEFEND_IRONCLAD"));
  state = await end(state);
  check("native_enemy_effects_and_intents_refresh", state.round === 2 && state.enemies[0].intents.length > 0
    && state.enemies[0].intents.every((row) => typeof row.label === "string" && typeof row.description === "string")
    && state.player_statuses.some((row) => row.id === "SHRINK_POWER"));
  return bootstraps;
}

async function main(spec) {
  const gates = {};
  let child, result = { status: "combat_probe_incomplete", gates, privileged_scenarios: true,
    full_run_attempts: 0, optimizer_steps: 0, training_allowed: false };
  try {
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    if (hashFile(spec.artifact) !== spec.expected.artifact_sha256) throw new Error("CLI artifact drifted");
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact],
      cwd: spec.profile, env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15_000, diagnosticLimit: 10000 });
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
    if (!gates.runtime_identity_bound) throw new Error("Native combat identity did not bind");
    result.native_run_bootstraps = await checkCombatScenarios(request, gates);
    await request({ cmd: "quit" }); result.exit = await child.exit;
    gates.natural_exit = result.exit.code === 0 && result.exit.signal === null;
    if (Object.values(gates).every((value) => value === true)) result.status = "combat_native_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) {
      result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics, null, 2));
      result.diagnostic_entries_retained = child.diagnostics.length;
    }
    writeFileSync(path.join(spec.attempt, "combat-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, failed: Object.keys(gates).filter((key) => !gates[key]), error: result.error ?? null }));
  if (result.status !== "combat_native_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
