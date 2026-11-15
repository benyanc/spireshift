// Named privileged native scenarios, never policy rollouts or training data.
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";

export function restAction(state, id) {
  const option = state?.options?.find((entry) => entry.option_id === id);
  if (state?.decision !== "rest_site" || typeof state.room_ref !== "string"
      || typeof option?.native_ref !== "string") throw new Error(`Missing bound rest choice ${id}`);
  return { cmd: "action", action: "choose_option",
    args: { room_ref: state.room_ref, option_index: option.index, option_ref: option.native_ref } };
}
export const leaveRest = (state) => ({ cmd: "action", action: "leave_room", args: { room_ref: state.room_ref } });

export async function checkRestScenarios(request, gates) {
  const check = (name, condition) => {
    gates[name] = condition === true;
    if (!gates[name]) throw new Error(`Rest gate failed: ${name}`);
  };
  let bootstraps = 0;
  const fixture = async (name, extras = {}) => {
    bootstraps++;
    await request({ cmd: bootstraps === 1 ? "start_run" : "reset_run",
      character: "Ironclad", ascension: 8, seed: `SPIRESHIFTREST${name}`, lang: "en" });
    const identity = await request({ cmd: "run_identity" });
    check(`${name}_native_A8`, identity.active === true && identity.ascension === 8);
    const setup = await request({ cmd: "set_player", hp: 25, max_hp: 80, ...extras });
    check(`${name}_privileged_setup_acknowledged`, setup.type === "ok");
    const state = await request({ cmd: "enter_room", type: "rest" });
    check(`${name}_rest_visible`, state.decision === "rest_site" && state.can_leave === false);
    return state;
  };
  const error = async (name, payload) => check(name, (await request(payload)).type === "error");
  const choose = (state, id) => request(restAction(state, id));
  const select = (indices) => request({ cmd: "action", action: "select_cards", args: { indices } });
  const cancel = () => request({ cmd: "action", action: "skip_select" });
  const smithPending = (name, state) => check(name, state.decision === "card_select"
    && state.cancelable === true && state.require_manual_confirmation === true
    && state.min_select === 1 && state.max_select === 1);

  let state = await fixture("NORMAL");
  const original = state;
  await error("premature_leave_refused", leaveRest(state));
  await error("missing_rest_room_binding_refused", { cmd: "action", action: "choose_option", args: { option_index: 0 } });
  const heal = restAction(state, "HEAL");
  await error("wrong_room_refused", { ...heal, args: { ...heal.args, room_ref: "stale-room" } });
  await error("wrong_option_refused", { ...heal, args: { ...heal.args, option_ref: "stale-option" } });
  await error("negative_option_index_refused", { ...heal, args: { ...heal.args, option_index: -1 } });
  await error("large_option_index_refused", { ...heal, args: { ...heal.args, option_index: 999 } });
  state = await request(heal);
  check("normal_heal_committed_before_observation", state.player.hp > 25);
  check("normal_options_exhausted_without_forced_map", state.decision === "rest_site"
    && state.options.length === 0 && state.can_leave === true);
  await error("consumed_choice_refused", heal);
  await error("missing_leave_binding_refused", { cmd: "action", action: "leave_room" });
  state = await request(leaveRest(state));
  check("explicit_proceed_opens_map", state.decision === "map_select");
  await error("choice_after_map_open_refused", restAction(original, "SMITH"));

  state = await fixture("TENTHEAL", { obtain_relics: ["MINIATURE_TENT"] });
  const oldSmith = restAction(state, "SMITH");
  state = await choose(state, "HEAL");
  check("tent_keeps_smith_available", state.decision === "rest_site" && state.options.length === 1
    && state.options[0].option_id === "SMITH" && state.can_leave === true);
  await error("old_option_index_after_refresh_refused", oldSmith);
  const awaitingRest = state;
  state = await choose(state, "SMITH");
  smithPending("tent_upgrade_suspends", state);
  state = await cancel();
  check("cancel_after_heal_preserves_existing_proceed", state.decision === "rest_site"
    && state.can_leave === true && state.options.length === 1 && state.options[0].option_id === "SMITH");
  state = await choose(state, "SMITH");
  smithPending("tent_upgrade_retry_suspends", state);
  await error("leave_during_selection_refused", leaveRest(awaitingRest));
  await error("noninteger_selection_refused", { cmd: "action", action: "select_cards", args: { indices: "bad,0" } });
  await error("duplicate_selection_refused", { cmd: "action", action: "select_cards", args: { indices: "0,0" } });
  await error("out_of_range_selection_refused", { cmd: "action", action: "select_cards", args: { indices: "999" } });
  await error("empty_confirmation_refused", { cmd: "action", action: "select_cards", args: { indices: "" } });
  state = await select("0");
  check("tent_upgrade_committed_without_forced_map", state.decision === "rest_site"
    && state.options.length === 0 && state.can_leave === true && state.player.deck.some((card) => card.is_upgraded === true));

  state = await fixture("TENTCANCEL", { obtain_relics: ["MINIATURE_TENT"] });
  state = await choose(state, "SMITH");
  smithPending("cancel_upgrade_suspends", state);
  state = await cancel();
  check("canceled_upgrade_preserves_options_and_disables_proceed", state.decision === "rest_site"
    && state.options.length === 2 && state.can_leave === false && !state.player.deck.some((card) => card.is_upgraded === true));
  await error("canceled_upgrade_does_not_enable_leave", leaveRest(state));
  state = await choose(state, "SMITH");
  smithPending("canceled_choice_can_retry", state);
  state = await select("0");
  check("smith_first_keeps_heal", state.decision === "rest_site" && state.can_leave === true
    && state.options.length === 1 && state.options[0].option_id === "HEAL");
  state = await choose(state, "HEAL");
  check("smith_then_heal_both_commit", state.decision === "rest_site" && state.options.length === 0
    && state.player.hp > 25 && state.player.deck.some((card) => card.is_upgraded === true));

  state = await fixture("GIRYA", { obtain_relics: ["GIRYA"] });
  check("native_relic_extra_option_visible", state.options.some((option) => option.option_id === "LIFT"));
  state = await choose(state, "LIFT");
  check("extra_option_native_commit", state.decision === "rest_site" && state.options.length === 0
    && state.can_leave === true && state.player.relics.some((relic) => relic.id === "GIRYA" && relic.counter === 1));

  state = await fixture("DISABLED", { deck: ["ASCENDERS_BANE"] });
  check("native_disabled_smith_observed", state.options.find((option) => option.option_id === "SMITH")?.is_enabled === false);
  await error("disabled_native_option_refused", restAction(state, "SMITH"));
  await error("disabled_choice_does_not_enable_leave", leaveRest(state));

  state = await fixture("SINGLE", { deck: ["STRIKE_IRONCLAD"] });
  state = await choose(state, "SMITH");
  smithPending("single_card_requires_manual_confirmation", state);
  check("single_card_visible", state.cards.length === 1);
  state = await cancel();
  check("single_card_can_cancel_without_upgrading", state.decision === "rest_site"
    && state.can_leave === false && state.player.deck[0].is_upgraded === false);
  state = await choose(state, "SMITH");
  smithPending("single_card_retry_requires_confirmation", state);
  state = await select("0");
  check("single_card_explicit_upgrade_commits", state.decision === "rest_site"
    && state.can_leave === true && state.options.length === 0 && state.player.deck[0].is_upgraded === true);

  state = await fixture("RESETPENDING");
  const oldRoom = state;
  state = await choose(state, "SMITH");
  smithPending("reset_pending_choice_suspends", state);
  state = await fixture("AFTERRESET");
  const identity = await request({ cmd: "run_identity" });
  check("reset_drains_old_pending_operation", !identity.pending_host_operation && !identity.pending_card_selection);
  await error("old_room_after_reset_refused", restAction(oldRoom, "HEAL"));
  await error("reset_does_not_inherit_proceed", leaveRest(state));

  state = await fixture("LEAVEREMAINDER", { obtain_relics: ["MINIATURE_TENT"] });
  state = await choose(state, "HEAL");
  const restRoom = state;
  state = await request(leaveRest(state));
  check("can_explicitly_leave_remaining_options", state.decision === "map_select");
  const point = state.choices[0];
  state = await request({ cmd: "action", action: "select_map_node",
    args: { col: point.col, row: point.row, map_point_ref: point.native_ref } });
  check("native_map_vote_exits_rest_without_hanging", state.type === "decision" && state.decision !== "rest_site");
  await error("old_rest_ref_after_travel_refused", leaveRest(restRoom));
  return bootstraps;
}

async function main(spec) {
  const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
  const output = path.join(spec.attempt, "rest-probe.json");
  const gates = {};
  let result = { status: "rest_probe_incomplete", gates, privileged_scenarios: true,
    full_run_attempts: 0, optimizer_steps: 0, training_allowed: false };
  let child;
  try {
    if (hashFile(spec.artifact) !== spec.expected.artifact_sha256
        || hashFile(path.join(spec.candidate, "lib/sts2.dll")) !== spec.expected.runtime_sts2_sha256)
      throw new Error("Managed runtime disk identity changed before launch");
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact],
      cwd: spec.profile, env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"),
        STS2_GAME_DIR: spec.game_data }, readyTimeoutMs: 15_000, diagnosticLimit: 10000 });
    child = started.process;
    if (started.ready.type !== "ready") throw new Error("Managed host not ready");
    const request = async (payload) => {
      const response = await child.request(payload, 15_000);
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`);
      return response;
    };
    const identity = await request({ cmd: "runtime_identity" });
    result.runtime_identity = identity;
    gates.runtime_process_and_assemblies_bound = identity.process_id === child.pid
      && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid
      && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256
      && identity.managed_runtime_version === spec.managed_runtime_version;
    if (!gates.runtime_process_and_assemblies_bound) throw new Error("Managed runtime identity did not bind");
    result.native_run_bootstraps = await checkRestScenarios(request, gates);
    await request({ cmd: "quit" });
    result.exit = await child.exit;
    gates.natural_exit = result.exit.code === 0 && result.exit.signal === null;
    if (Object.values(gates).every((gate) => gate === true)) result.status = "rest_native_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) {
      result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics, null, 2));
      result.diagnostic_entries_retained = child.diagnostics.length;
      result.diagnostic_retention_limit = 10000;
    }
    writeFileSync(output, `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, checks: Object.keys(gates).length, error: result.error ?? null }));
  if (result.status !== "rest_native_regression_pass") process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  await main(JSON.parse(input));
}
