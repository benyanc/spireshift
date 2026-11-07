// Exact SDK action delivery over named native fixtures. Never a rollout or training admission.
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactSelectionShopSurface } from "./engine-selection-shop-surface.mjs";
import { checkRestScenarios } from "./probe-engine-cli-rest.mjs";
import { checkShopScenarios } from "./probe-engine-cli-shop.mjs";

const canonical = (value) => Array.isArray(value) ? value.map(canonical)
  : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])])) : value;
const same = (left, right) => JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));

async function main(spec) {
  if (!["rest", "shop"].includes(spec.panel)) throw new Error("A frozen native panel is required");
  const panel = spec.panel;
  const gates = {};
  let child, result = { status: `${panel}_projection_incomplete`, gates,
    privileged_scenarios: true, full_run_attempts: 0, optimizer_steps: 0, training_allowed: false };
  const check = (name, ok) => {
    gates[name] = ok === true;
    if (!gates[name]) throw new Error(`Public interaction gate failed: ${name}`);
  };
  try {
    const prepared = await preparePlayerProjection(spec);
    result.projection_identity = prepared.identity;
    const { ManagedPlayerEnvironmentSession } = prepared.module;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    check("exact_disk_game_and_host_bound", hashFile(spec.artifact) === spec.expected.artifact_sha256
      && hashFile(path.join(spec.candidate, "lib/sts2.dll")) === spec.expected.runtime_sts2_sha256);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact],
      cwd: spec.profile, env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"),
        STS2_GAME_DIR: spec.game_data }, readyTimeoutMs: 15_000, diagnosticLimit: 10000 });
    child = started.process;
    check("native_host_ready", started.ready.type === "ready");
    let nativeActionCalls = 0, lastDecision, lastBindings = new Map(), sequence = 0;
    let publicRestSnapshots = 0, publicShopSnapshots = 0, publicSelectionSnapshots = 0, deliveredActions = 0, negativeActions = 0;
    const raw = async (payload, timeoutMs = 15_000) => {
      if (payload.cmd === "action") nativeActionCalls++;
      const response = await child.request(payload, timeoutMs);
      if (response.type === "decision") lastDecision = response;
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), `${JSON.stringify({ request: payload, response })}\n`);
      return response;
    };
    const identity = await raw({ cmd: "runtime_identity" });
    result.runtime_identity = identity;
    check("runtime_process_and_assemblies_bound", identity.process_id === child.pid
      && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid
      && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256
      && identity.managed_runtime_version === spec.managed_runtime_version);
    const session = new ManagedPlayerEnvironmentSession({ process: { request: raw },
      runtimeInstanceId: `${panel}-projection-${child.pid}`, environmentFingerprint: spec.environment_fingerprint,
      character: "Ironclad", ascension: 8, validateSdk: true,
      surfaceProjector(state, ctx, helpers) {
        lastBindings = ctx.bindings;
        return projectExactSelectionShopSurface(state, ctx, helpers);
      } });
    function checkSnapshot(snapshot) {
      if (!["rest_site", "card_selection", "shop_inventory"].includes(snapshot.interaction.kind)) return;
      const key = snapshot.interaction.kind === "rest_site" ? "rest"
        : snapshot.interaction.kind === "shop_inventory" ? "shop" : "selection";
      if (key === "rest") publicRestSnapshots++; else if (key === "shop") publicShopSnapshots++; else publicSelectionSnapshots++;
      const serialized = JSON.stringify(snapshot);
      check(`snapshot_${++sequence}_${key}_public_operands`, !/"(?:native_ref|room_ref|option_ref|item_ref|selection_ref|raw_request|seed|rng|draw_order)"/u.test(serialized));
      const menu = snapshot.bound_actions;
      check(`snapshot_${sequence}_${key}_complete_bindings`, menu.status === "complete"
        && menu.actions.length === menu.materialized_count && menu.actions.length === menu.total_count
        && menu.actions.length === lastBindings.size && new Set(menu.actions.map((row) => row.bound_action_id)).size === menu.actions.length);
      const surface = snapshot.interaction.content.surface;
      if (key === "rest") {
        check(`snapshot_${sequence}_native_rest_options`, same(surface.options.map(({ index, option_id, is_enabled }) =>
          ({ index, option_id, is_enabled })), lastDecision.options.map(({ index, option_id, is_enabled }) => ({ index, option_id, is_enabled })))
          && surface.can_leave === lastDecision.can_leave);
        check(`snapshot_${sequence}_only_native_rest_actions`, menu.actions.length
          === lastDecision.options.filter((option) => option.is_enabled).length + (lastDecision.can_leave ? 1 : 0));
      } else if (key === "shop") {
        const original = [...lastDecision.cards, ...lastDecision.relics, ...lastDecision.potions, lastDecision.card_removal];
        const visible = [...surface.cards, ...surface.relics, ...surface.potions, surface.card_removal];
        check(`snapshot_${sequence}_native_prices_and_availability`, same(visible.map(({ price, can_purchase, is_stocked }) =>
          ({ price, can_purchase, is_stocked })), original.map(({ cost, can_purchase, is_stocked }) =>
          ({ price: cost, can_purchase, is_stocked }))));
        check(`snapshot_${sequence}_only_native_shop_purchases_and_leave`, menu.actions.length
          === original.filter((item) => item.can_purchase).length + 1);
        check(`snapshot_${sequence}_public_shop_model_definitions`, [...surface.cards, ...surface.relics, ...surface.potions]
          .every((item) => !item.is_stocked || typeof item.definition_id === "string"));
      } else {
        check(`snapshot_${sequence}_explicit_native_selection_preferences`, surface.min_select === lastDecision.min_select
          && surface.max_select === lastDecision.max_select && surface.cancelable === lastDecision.cancelable
          && surface.require_manual_confirmation === lastDecision.require_manual_confirmation
          && surface.unpowered_previews === lastDecision.unpowered_previews
          && surface.pretend_cards_can_be_played === lastDecision.pretend_cards_can_be_played);
        check(`snapshot_${sequence}_native_selection_prompt`, snapshot.interaction.prompt === lastDecision.prompt);
      }
      appendFileSync(path.join(spec.attempt, "private-public-snapshots.jsonl"), `${serialized}\n`);
    }
    let requestCounter = 0, ledgerChecked = false;
    const request = async (payload) => {
      if (["start_run", "reset_run"].includes(payload.cmd)) {
        const snapshot = await session.mount({ seed: payload.seed, reset: payload.cmd === "reset_run" });
        checkSnapshot(snapshot); return lastDecision;
      }
      if (payload.cmd !== "action") {
        const response = await raw(payload);
        if (response.type === "decision") checkSnapshot(await session.acceptNativeObservation(response));
        return response;
      }
      // The preserved rest-v1 panel predates instance binding; its positive and negative
      // selection payloads receive the live private reference. Explicitly wrong refs stay wrong.
      if (panel === "rest" && ["select_cards", "skip_select"].includes(payload.action)
          && payload.args?.selection_ref == null) payload = { ...payload,
        args: { ...payload.args, selection_ref: lastDecision?.selection_ref } };
      const entry = [...lastBindings.values()].find((binding) => same(binding.raw_request, payload));
      if (!entry) {
        // Only the frozen panel's explicitly invalid inputs bypass public delivery.
        const response = await raw(payload); negativeActions++;
        check(`negative_input_${negativeActions}_refused_natively`, response.type === "error");
        return response;
      }
      const before = session.observe();
      const submission = { requestId: `${panel}-action-${++requestCounter}`, expectedSnapshotId: before.snapshot_id,
        boundActionId: entry.action.bound_action_id, timeoutMs: 15_000 };
      const receipt = await session.submit(submission);
      check(`canonical_action_${++deliveredActions}_delivered`, receipt.delivery === "delivered"
        && receipt.successor.snapshot_id !== before.snapshot_id);
      checkSnapshot(receipt.successor);
      appendFileSync(path.join(spec.attempt, "private-receipts.jsonl"), `${JSON.stringify(receipt)}\n`);
      if (!ledgerChecked) {
        const calls = nativeActionCalls;
        const replay = await session.submit(submission);
        check("request_replay_returns_same_receipt_without_native_action", same(replay, receipt) && nativeActionCalls === calls);
        const conflict = await session.submit({ ...submission, boundActionId: "different-action" });
        check("request_identity_conflict_refused_before_delivery", conflict.delivery === "not_delivered"
          && conflict.reason_code === "request_id_conflict" && nativeActionCalls === calls);
        const stale = await session.submit({ ...submission, requestId: "old-interaction-snapshot" });
        check("stale_snapshot_refused_before_delivery", stale.delivery === "not_delivered"
          && stale.reason_code === "stale_snapshot" && nativeActionCalls === calls);
        ledgerChecked = true;
      }
      return lastDecision;
    };
    result.native_run_bootstraps = await (panel === "rest" ? checkRestScenarios : checkShopScenarios)(request, gates);
    const installed = await raw({ cmd: "runtime_identity" });
    check("seven_native_preference_boundaries_installed", installed.selection_preference_hooks === 7);
    result.selection_preference_boundaries_installed = installed.selection_preference_hooks;
    check("all_fixture_actions_counted", nativeActionCalls === deliveredActions + negativeActions);
    check("session_remains_untainted", session.tainted === false);
    check("canonical_panel_and_manual_selection_observed", (panel === "rest" ? publicRestSnapshots : publicShopSnapshots) > 0
      && publicSelectionSnapshots > 0);
    check("all_native_panel_gates_pass", Object.values(gates).every((ok) => ok === true));
    result.canonical_delivery = { rest_snapshots: publicRestSnapshots, shop_snapshots: publicShopSnapshots, selection_snapshots: publicSelectionSnapshots,
      delivered_actions: deliveredActions, invalid_native_inputs: negativeActions, native_action_calls: nativeActionCalls,
      sdk_validation_enabled: true, request_ledger_checked: ledgerChecked };
    await raw({ cmd: "quit" });
    result.exit = await child.exit;
    check("natural_exit", result.exit.code === 0 && result.exit.signal === null);
    result.status = `${panel}_public_projection_regression_pass`;
  } catch (error) { result.error = error.message; }
  finally {
    if (child) {
      result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics, null, 2));
      result.diagnostic_entries_retained = child.diagnostics.length;
      result.diagnostic_retention_limit = 10000;
    }
    writeFileSync(path.join(spec.attempt, `${panel}-probe.json`), `${JSON.stringify(result, null, 2)}\n`);
  }
  console.log(JSON.stringify({ status: result.status, checks: Object.keys(gates).length, error: result.error ?? null }));
  if (result.status !== `${panel}_public_projection_regression_pass`) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  await main(JSON.parse(input));
}
