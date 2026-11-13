// Current Python checkpoint choices delivered by the pinned official-game SDK.
// No fitting or action retries. Explicit stale reads may refresh before a policy choice.
import { spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import { randomUUID } from "node:crypto";
import { appendFileSync, writeFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { validateLoadedIdentity } from "./engine-menu-probe.mjs";
import { chooseStartupAction } from "./engine-new-run-contract-v1.mjs";
import { naturalTutorialAction } from "./engine-natural-tutorial-v3.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { sharedDecision, deliveredAction, recordInterfaceNavigation } from "./engine-shared-input-v14.mjs";
import { collectCurrentFrame } from "./engine-checkpoint-observation-v1.mjs";
import { requireCanonicalSeed, verifyEpisodeSeed } from "./engine-seed-contract-v1.mjs";
import { observationBoundary, observationDeadline } from "./engine-observation-boundary-v2.mjs";
import { requireAtomicCompletion } from "./engine-atomic-selection-receipt-v1.mjs";
import {rewardProceed,finishRewardProceed} from "./engine-reward-commit-v3.mjs";
import {bundleRoot,bundleConfirmation,verifyBundleCommit} from "./engine-bundle-commit-v1.mjs";
import { shippedEnding } from "./engine-natural-shipped-contract-v1.mjs";

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const emit = value => process.stdout.write(`${JSON.stringify(value)}\n`);

export async function run(spec, nextChoice) {
  requireCanonicalSeed(spec.seed);
  const deadline = Date.now() + spec.max_wall_seconds * 1000;
  const result = { schema_version: "official-live-checkpoint-prefix-v1", checks: {},
    policy_decisions: 0, enchantment_preview_choices: 0, presentation_steps: 0, reward_guidance_macros: 0, reward_confirmation_steps: 0, atomic_selections: 0, selection_ui_steps: 0, committed_packs: 0, pack_ui_steps: 0, terminal: false, training_allowed: false,
    optimizer_updates: 0, game_apps_created: 0, shutdown_requested: false };
  const journal = value => appendFileSync(path.join(spec.attempt, "live-public.jsonl.gz"),
    gzipSync(`${JSON.stringify(value)}\n`));
  const check = (key, value) => {
    result.checks[key] = value === true;
    if (value !== true) throw Error(`Official checkpoint check failed: ${key}`);
  };
  let session, client, runtime;
  const navigation = newDiagnosticNavigation();
  try {
    const sdk = await import(pathToFileURL(path.join(spec.toolchain,
      "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href);
    client = new sdk.PlayerEnvironmentRestClient(spec.endpoint, 2500);
    let capabilities;
    while (Date.now() < deadline) {
      process.kill(spec.expected_pid, 0);
      try { capabilities = (await client.capabilities()).data; break; } catch { await pause(200); }
    }
    check("loaded_identity", validateLoadedIdentity(capabilities, spec));
    runtime = capabilities.host.runtime_instance_id;
    const url = new URL(spec.endpoint);
    check("loopback_endpoint", url.hostname === "127.0.0.1" && url.protocol === "http:"
      && !!url.port && url.pathname === "/" && !url.username && !url.password && !url.search && !url.hash);
    const owner = spawnSync("/usr/sbin/lsof", ["-nP", `-iTCP:${url.port}`, "-sTCP:LISTEN", "-Fp"],
      { encoding: "utf8", timeout: 2000 });
    check("endpoint_owned_by_child", owner.status === 0 && JSON.stringify(
      owner.stdout.split("\n").filter(row => /^p\d+$/u.test(row))) === JSON.stringify([`p${spec.expected_pid}`]));
    session = new sdk.EnvironmentControllerSession(client, { productId: "spireshift-frozen-checkpoint",
      productName: "SpireShift Frozen Checkpoint", productVersion: "1" });
    await session.register(capabilities.host, capabilities.control);
    async function stable(previous = null, boundary = deadline, startup = false) {
      const until = observationDeadline(Date.now(), deadline, boundary, startup);
      let last;
      while (Date.now() < until) {
        last = (await client.observe()).data;
        journal({ kind: "observed", snapshot: last });
        if (observationBoundary(last, runtime, previous) === "ready") return last;
        await pause(150);
      }
      throw Error(`No complete fresh official snapshot before cap: ${last?.interaction?.kind}`);
    }
    async function submit(snapshot, action, startup = false) {
      const requestId = `checkpoint-${randomUUID()}`;
      const bundle = snapshot.interaction.kind === "card_bundle_selection" && snapshot.interaction.stage === "choosing" && action.verb === "select";
      const pack = bundle ? bundleRoot(snapshot,action) : null;
      const proceeding = rewardProceed(snapshot,action);
      const atomic = snapshot.interaction.content.surface?.selection_contract === "atomic_public_card_choice_v1"
        && ["confirm", "cancel"].includes(action.verb);
      const receipt = (await client.submit({ requestId,
        expectedSnapshotId: snapshot.snapshot_id, boundActionId: action.bound_action_id,
        ...await session.credentials() })).data;
      journal({ kind: atomic ? "selection_acceptance" : bundle ? "bundle_acceptance" : proceeding ? "reward_proceed_acceptance" : "receipt", before_snapshot_id: snapshot.snapshot_id, action, receipt });
      if (receipt.delivery !== "delivered" || receipt.attribution?.runtime_instance_id !== runtime)
        throw Error("Uncertain official delivery; no retry");
      let successor = await stable(snapshot.snapshot_id, deadline, startup);
      if(proceeding){
        const completion=await finishRewardProceed(snapshot,action,receipt,successor,{
          deadline:Math.min(deadline-5000,Date.now()+15000),
          observe:(previous,boundary)=>stable(previous,boundary,startup),
          send:async(current,control,kind)=>{
            const acknowledged=(await client.submit({requestId:`reward-${kind}-${randomUUID()}`,
              expectedSnapshotId:current.snapshot_id,boundActionId:control.bound_action_id,
              ...await session.credentials()})).data;
            journal({kind:"reward_ui_receipt",ui_kind:kind,before_snapshot_id:current.snapshot_id,
              action:control,receipt:acknowledged});
            return acknowledged;
          },
          onTutorial:()=>{if(++result.presentation_steps>64)throw Error("Tutorial presentation cap");}
        });
        successor=completion.successor;
        if(completion.proof.ui_steps.some(s=>s.kind==='tutorial'))result.reward_guidance_macros++;
        result.reward_confirmation_steps+=completion.proof.ui_steps.filter(s=>s.kind==='confirmation').length;
        journal({kind:"reward_proceed_completion",proof:completion.proof});
        journal({kind:"receipt",before_snapshot_id:snapshot.snapshot_id,action,receipt,semantic_successor_snapshot_id:successor.snapshot_id});
      }
      if(atomic) {
        const response=await fetch(`${spec.endpoint}/api/host-control/selection-provenance`,{
          method:"POST",headers:{"content-type":"application/json"},
          body:JSON.stringify({expected_runtime_instance_id:runtime,host_control_token:spec.host_control_token}),
          signal:AbortSignal.timeout(3000)});
        if(!response.ok)throw Error("Atomic selection completion evidence is unavailable; no retry");
        const body=await response.json(),proof=requireAtomicCompletion(body,snapshot,action,requestId,runtime);
        journal({kind:"atomic_selection_completion",proof,root_snapshot_id:snapshot.snapshot_id,root_bound_action_id:action.bound_action_id});
        journal({kind:"receipt",before_snapshot_id:snapshot.snapshot_id,action,receipt});
        result.atomic_selections++;result.selection_ui_steps+=proof.steps.length;
      }
      if(bundle){
        const preview=successor,confirm=bundleConfirmation(snapshot,pack,preview);
        const committed=(await client.submit({requestId:`pack-confirm-${randomUUID()}`,expectedSnapshotId:preview.snapshot_id,
          boundActionId:confirm.bound_action_id,...await session.credentials()})).data;
        journal({kind:"bundle_ui_receipt",before_snapshot_id:preview.snapshot_id,action:confirm,receipt:committed});
        if(committed.delivery!=="delivered"||committed.attribution?.runtime_instance_id!==runtime)throw Error("Uncertain pack confirmation; no retry");
        successor=await stable(preview.snapshot_id,deadline,startup);
        const proof=verifyBundleCommit(snapshot,action,preview,confirm,committed,successor);
        journal({kind:"bundle_selection_completion",proof});
        journal({kind:"receipt",before_snapshot_id:snapshot.snapshot_id,action,receipt,semantic_successor_snapshot_id:successor.snapshot_id});
        result.committed_packs++;result.pack_ui_steps+=2;
      }
      return { receipt, successor };
    }
    let snapshot = await stable(null, deadline, true);
    while (snapshot.interaction.kind !== "event_option") {
      if (++result.presentation_steps > 48) throw Error("Startup presentation cap");
      const action = chooseStartupAction(snapshot);
      snapshot = (await submit(snapshot, action, true)).successor;
    }
    const provenanceResponse = await fetch(`${spec.endpoint}/api/host-control/provenance`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ expected_runtime_instance_id: runtime, host_control_token: spec.host_control_token }),
      signal: AbortSignal.timeout(3000) });
    if (!provenanceResponse.ok) throw Error("Official episode provenance unavailable");
    const provenance = await provenanceResponse.json();
    journal({ kind: "episode_provenance", provenance });
    result.episode_seed = verifyEpisodeSeed(provenance, spec.seed, runtime);
    check("exact_declared_episode_seed", true);
    check("natural_Ironclad_A8_start", snapshot.persistent.content.run.ascension === 8
      && snapshot.persistent.content.player.character_definition_id === "IRONCLAD"
      && snapshot.persistent.content.run.floor === 1);
    while (Date.now() < deadline && result.policy_decisions < spec.maximum_decisions) {
      if (snapshot.interaction.kind === "tutorial") {
        if (++result.presentation_steps > 64) throw Error("Tutorial presentation cap");
        snapshot = (await submit(snapshot, naturalTutorialAction(snapshot))).successor;
        continue;
      }
      const collected = await collectCurrentFrame(snapshot, {
        read: async (id, expected) => (await client.read(id, expected)).data,
        refresh: stable, journal, deadline: Math.min(deadline - 5000, Date.now() + 15000) });
      snapshot = collected.snapshot;
      const reads = collected.reads;
      if (snapshot.interaction.kind === "tutorial") continue;
      // Preserve the complete public capture even when conversion rejects a
      // newly encountered family. Rejected inputs never reach the model.
      journal({ kind: "public_frame", snapshot, reads });
      const frame = sharedDecision(snapshot, reads, navigation);
      journal({ kind: "policy_input", snapshot, reads, frame });
      if(frame.public_input.context.interaction.content.surface.enchantment)result.enchantment_preview_choices++;
      if (frame.terminal) {
        result.terminal = true; result.ending = shippedEnding(snapshot, runtime);
        if (JSON.stringify(result.ending) !== JSON.stringify(frame.ending)) throw Error("Terminal outcome projection changed");
        break;
      }
      emit({ kind: "policy_observation", frame });
      const choice = await nextChoice();
      if (choice.command !== "choose") throw Error("No checkpoint choice supplied");
      const action = deliveredAction(frame, choice, snapshot);
      journal({ kind: "policy_choice", choice });
      const { receipt, successor } = await submit(snapshot, action);
      recordInterfaceNavigation(navigation, snapshot, action, receipt);
      emit({ kind: "delivered", acknowledgement: { binding_id: frame.binding_id,
        delivery: receipt.delivery, bound_action_id: action.bound_action_id,
        runtime_instance_id: runtime, before_snapshot_id: snapshot.snapshot_id,
        successor_snapshot_id: successor.snapshot_id } });
      snapshot = successor; result.policy_decisions++;
    }
    check("declared_prefix_or_ending_observed", result.terminal || result.policy_decisions === spec.maximum_decisions);
    result.status = "official_checkpoint_prefix_complete";
  } catch (error) {
    result.status = "official_checkpoint_prefix_blocked"; result.error = error.message;
  } finally {
    if (session) try { await session.close(); } catch (error) { result.session_close_error = error.message; }
    if (runtime && client) try {
      const response = await fetch(`${spec.endpoint}/api/host-control/shutdown`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ expected_runtime_instance_id: runtime, host_control_token: spec.host_control_token }),
        signal: AbortSignal.timeout(3000) });
      result.shutdown_requested = response.ok && (await response.json()).status === "shutdown_requested";
    } catch (error) { result.shutdown_error = error.message; }
    writeFileSync(path.join(spec.attempt, "live-control.json"), `${JSON.stringify(result, null, 2)}\n`, { flag: "wx" });
    emit({ kind: "complete", result });
  }
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  const iterator = lines[Symbol.asyncIterator]();
  try {
    const first = await iterator.next();
    const result = await run(JSON.parse(first.value), async () => {
      const next = await iterator.next();
      if (next.done) throw Error("Checkpoint policy disconnected");
      return JSON.parse(next.value);
    });
    if (result.status !== "official_checkpoint_prefix_complete" || !result.shutdown_requested) process.exitCode = 1;
  } finally { lines.close(); process.stdin.destroy(); }
}
