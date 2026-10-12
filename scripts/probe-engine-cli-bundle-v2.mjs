// Finite natural Neow/Scroll Boxes choices, invalid operands and pending-choice reset.
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactBundleSurface } from "./engine-bundle-surface-v1.mjs";
import { projectExactCombatReads } from "./engine-combat-surface.mjs";

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const ids = (cards) => cards.map((row) => row.definition_id).sort();
async function main(spec) {
  const gates = {}, result = { status: "bundle_projection_incomplete", gates,
    privileged_scenarios: true, full_run_attempts: 0, optimizer_steps: 0, training_allowed: false,
    native_run_bootstraps: 0, cases: [], snapshots: 0, invalid_native_inputs: 0, delivered_actions: 0 };
  const check = (name, ok) => { gates[name] = ok === true; if (!ok) throw Error(`Bundle gate failed: ${name}`); };
  let child;
  try {
    const prepared = await preparePlayerProjection(spec); result.projection_identity = prepared.identity;
    const { startJsonLineProcess } = await import(pathToFileURL(path.join(spec.headless_root, "src/json-line-process.mjs")).href);
    const started = await startJsonLineProcess({ command: "/usr/bin/sandbox-exec",
      args: ["-f", path.join(spec.attempt, "profile-isolation.sb"), spec.dotnet, spec.artifact], cwd: spec.profile,
      env: { ...process.env, STS2_LIB: path.join(spec.candidate, "lib"), STS2_GAME_DIR: spec.game_data },
      readyTimeoutMs: 15000, diagnosticLimit: 10000 }); child = started.process;
    let latest, bindings;
    const raw = async (request) => {
      const response = await child.request(request, 15000);
      if (response.type === "decision") latest = response;
      appendFileSync(path.join(spec.attempt, "private-transcript.jsonl"), JSON.stringify({ request, response }) + "\n");
      return response;
    };
    const identity = await raw({ cmd: "runtime_identity" }); result.runtime_identity = identity;
    check("runtime_process_and_assemblies_bound", identity.process_id === child.pid
      && identity.host_assembly_sha256 === spec.expected.artifact_sha256
      && identity.host_module_mvid === spec.expected.artifact_mvid
      && identity.sts2_assembly_sha256 === spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256 === spec.expected.godot_stub_sha256
      && identity.managed_runtime_version === spec.managed_runtime_version);
    const session = new prepared.module.ManagedPlayerEnvironmentSession({ process: { request: raw },
      character: "Ironclad", ascension: 8, runtimeInstanceId: `bundle-${child.pid}`,
      environmentFingerprint: spec.environment_fingerprint, validateSdk: true,
      readProjector: projectExactCombatReads,
      surfaceProjector(state, ctx, helpers) { bindings = ctx.bindings; return projectExactBundleSurface(state, ctx, helpers); } });
    const readDeck = (snapshot) => {
      const descriptor = snapshot.reads.find((row) => row.kind === "run_deck");
      const read = session.read({ readId: descriptor?.read_id, expectedSnapshotId: snapshot.snapshot_id });
      check(`deck_read_${result.snapshots}_complete`, read.completeness.status === "complete");
      return ids(read.content.cards);
    };
    const capture = (snapshot) => {
      result.snapshots++;
      check(`snapshot_${result.snapshots}_complete`, snapshot.completeness.status === "complete"
        && snapshot.bound_actions.status === "complete");
      check(`snapshot_${result.snapshots}_public`, !/"(?:native_ref|selection_ref|bundle_ref|raw_request|seed|rng|draw_order)"/u.test(JSON.stringify(snapshot)));
      appendFileSync(path.join(spec.attempt, "private-public-snapshots.jsonl"), JSON.stringify(snapshot) + "\n");
      return snapshot;
    };
    let requestId = 0;
    const submit = async (snapshot, action) => {
      const receipt = await session.submit({ requestId: `bundle-${++requestId}`,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id, timeoutMs: 15000 });
      check(`delivery_${requestId}`, receipt.delivery === "delivered"); result.delivered_actions++;
      appendFileSync(path.join(spec.attempt, "private-receipts.jsonl"), JSON.stringify(receipt) + "\n");
      return capture(receipt.successor);
    };
    const reset = async (seed) => {
      result.native_run_bootstraps++;
      const response = await raw({ cmd: "reset_run", character: "Ironclad", ascension: 8,
        seed, lang: "en", content_policy: "native_all_unlocked" });
      const snapshot = capture(await session.acceptNativeObservation(response));
      const run = await raw({ cmd: "run_identity" });
      check(`run_${result.native_run_bootstraps}_A8_seed`, run.active && run.seed === seed && run.ascension === 8
        && run.pending_bundle === false);
      check(`run_${result.native_run_bootstraps}_hook`, (await raw({ cmd: "runtime_identity" })).native_bundle_selection_hook === true);
      return snapshot;
    };
    const scrollBoxes = async (snapshot) => {
      const actions = snapshot.bound_actions.actions.filter((row) => row.label === "Scroll Boxes");
      check(`run_${result.native_run_bootstraps}_natural_scroll_boxes`, actions.length === 1);
      const next = await submit(snapshot, actions[0]);
      check(`run_${result.native_run_bootstraps}_bundle_menu`, next.interaction.kind === "card_bundle_selection"
        && next.bound_actions.actions.length === 2 && next.interaction.content.surface.bundles.length === 2);
      return next;
    };
    const prefixes = new Map(); let abandoned;
    for (const seed of spec.bundle_seeds) for (const index of [0, 1]) for (const repeat of [1, 2]) {
      let snapshot = await reset(seed); const initialDeck = readDeck(snapshot);
      snapshot = await scrollBoxes(snapshot);
      const offered = snapshot.interaction.content.surface.bundles;
      check(`case_${result.cases.length}_definitions_present`, offered.every((bundle) => bundle.cards.length === 3
        && bundle.cards.every((card) => typeof card.definition_id === "string" && card.definition_id)));
      const action = snapshot.bound_actions.actions.find((row) => {
        const request = bindings.get(row.bound_action_id)?.raw_request; return request?.args?.bundle_index === index;
      });
      check(`case_${result.cases.length}_selected_binding`, !!action);
      const current = structuredClone(bindings.get(action.bound_action_id).raw_request);
      const pending = await raw({ cmd: "run_identity" });
      for (const change of [
        (r) => { delete r.args.selection_ref; }, (r) => { r.args.selection_ref = "stale-selection"; },
        (r) => { r.args.bundle_ref = "stale-bundle"; }, (r) => { r.args.bundle_index = -1; },
        (r) => { r.args.bundle_index = 2; }, (r) => { r.args.bundle_index = true; },
        (r) => { r.args.bundle_index = "1"; }, (r) => { r.args.bundle_index = 0.5; }
      ]) {
        const bad = structuredClone(current); change(bad);
        check(`invalid_${++result.invalid_native_inputs}_rejected`, (await raw(bad)).type === "error");
        check(`invalid_${result.invalid_native_inputs}_pending_unchanged`, same(pending, await raw({ cmd: "run_identity" })));
      }
      if (abandoned) check(`stale_${result.cases.length}_old_instance_rejected`, (await raw(abandoned)).type === "error");
      abandoned = current;
      const selectedIds = ids(offered[index].cards);
      snapshot = await submit(snapshot, action);
      const finalDeck = readDeck(snapshot);
      check(`case_${result.cases.length}_chosen_pack_awarded`, same(finalDeck, [...initialDeck, ...selectedIds].sort()));
      check(`case_${result.cases.length}_choice_finished`, (await raw({ cmd: "run_identity" })).pending_bundle === false);
      const key = `${seed}-${index}`, facts = { offered: offered.map((b) => ids(b.cards)), selectedIds, initialDeck, finalDeck };
      if (repeat === 2) check(`repeat_${key}`, same(facts, prefixes.get(key))); prefixes.set(key, facts);
      result.cases.push({ seed, index, repeat, facts });
    }
    // Abandon an actual pending Scroll Boxes choice, then reset the same process.
    for (const seed of spec.bundle_seeds) {
      const before = await reset(seed); const initialDeck = readDeck(before);
      const pending = await scrollBoxes(before);
      const old = structuredClone(bindings.get(pending.bound_actions.actions[0].bound_action_id).raw_request);
      const after = await reset(seed);
      check(`cleanup_${seed}_no_pack_awarded`, same(initialDeck, readDeck(after)));
      check(`cleanup_${seed}_abandoned_operand_rejected`, (await raw(old)).type === "error");
      const fresh = await scrollBoxes(after);
      const action = fresh.bound_actions.actions[1];
      const chosen = ids(fresh.interaction.content.surface.bundles[1].cards);
      const final = await submit(fresh, action);
      check(`cleanup_${seed}_fresh_second_pack_works`, same(readDeck(final), [...initialDeck, ...chosen].sort()));
    }
    await raw({ cmd: "quit" }); result.exit = await child.exit;
    check("natural_exit", result.exit.code === 0 && result.exit.signal === null);
    result.status = "bundle_public_projection_regression_pass";
  } catch (error) { result.error = error.message; }
  finally {
    if (child) { result.exit ??= await child.stop({ timeoutMs: 2000 });
      writeFileSync(path.join(spec.attempt, "diagnostics.json"), JSON.stringify(child.diagnostics)); }
    writeFileSync(path.join(spec.attempt, "bundle-probe.json"), JSON.stringify(result, null, 2) + "\n");
  }
  console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
  if (result.status !== "bundle_public_projection_regression_pass") process.exitCode = 1;
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = ""; for await (const chunk of process.stdin) input += chunk.toString(); await main(JSON.parse(input));
}
