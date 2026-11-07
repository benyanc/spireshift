// Saved public records only. This file cannot launch a game or load an optimizer.
import { createHash } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { once } from "node:events";
import { pipeline } from "node:stream/promises";
import { createGunzip, createGzip } from "node:zlib";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { actionsPreserved, convert, differencePaths, digest, restore } from "./converter.mjs";

const rootDefault = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const hash = async file => {
  const sha = createHash("sha256");
  for await (const chunk of createReadStream(file)) sha.update(chunk);
  return sha.digest("hex");
};
const json = async file => JSON.parse(await readFile(file, "utf8"));
function local(root, name) {
  if (path.isAbsolute(name) || name.split(/[\\/]/u).includes("..")) throw Error("Use repository-relative paths");
  const result = path.resolve(root, name);
  if (!result.startsWith(`${root}${path.sep}`)) throw Error("Path escaped the repository");
  return result;
}
async function pinned(root, ref) {
  const file = local(root, ref.path);
  if (await hash(file) !== ref.sha256) throw Error(`Changed sealed input: ${ref.path}`);
  return file;
}
async function protect(root, refs) {
  for (const [name, sha256] of Object.entries(refs)) await pinned(root, { path: name, sha256 });
}

// Bound the decompressed line BEFORE parsing; never load an entire capture.
export async function* publicLines(file, deadline, maximum = 16_000_000) {
  const source = createReadStream(file), stream = createGunzip();
  source.on("error", error => stream.destroy(error)); source.pipe(stream);
  let pending = Buffer.alloc(0);
  try {
    for await (const chunk of stream) {
      if (performance.now() >= deadline) throw Error("Saved-layout study wall cap");
      let start = 0;
      for (let end = chunk.indexOf(10); end >= 0; end = chunk.indexOf(10, start)) {
        const next = chunk.subarray(start, end);
        if (pending.length + next.length > maximum) throw Error("Public frame line cap");
        const line = Buffer.concat([pending, next]).toString("utf8");
        pending = Buffer.alloc(0); start = end + 1;
        if (line.trim()) yield JSON.parse(line);
      }
      const next = chunk.subarray(start);
      if (pending.length + next.length > maximum) throw Error("Public frame line cap");
      pending = Buffer.concat([pending, next]);
    }
    if (pending.length) yield JSON.parse(pending.toString("utf8"));
  } finally { source.destroy(); stream.destroy(); }
}

function probes(input) {
  const result = [], deck = input.context.reads.find(read => read.kind === "run_deck")?.content?.cards;
  const relics = input.context.persistent.player?.relics;
  if (deck?.length) {
    result.push(["deck_definition", copy => { copy.context.reads.find(row => row.kind === "run_deck")
      .content.cards[0].definition_id += "_LAYOUT_PROBE"; }]);
    result.push(["per_copy_cost", copy => { const card = copy.context.reads.find(row => row.kind === "run_deck").content.cards[0];
      card.cost = card.cost === "0" ? "1" : "0"; }]);
    result.push(["per_copy_upgrade", copy => { const card = copy.context.reads.find(row => row.kind === "run_deck").content.cards[0];
      card.is_upgraded = !card.is_upgraded; }]);
  }
  if (relics?.length) result.push(["relic_definition", copy => { copy.context.persistent.player.relics[0].definition_id += "_LAYOUT_PROBE"; }]);
  const counter = relics?.findIndex(relic => typeof relic.counter === "number") ?? -1;
  if (counter >= 0) result.push(["owned_relic_counter", copy => { copy.context.persistent.player.relics[counter].counter++; }]);
  return result;
}

export async function run(root, recipePath) {
  const started = performance.now(), deadline = started + 90_000;
  const cfg = await json(local(root, recipePath));
  if (cfg.schema_version !== "offline-input-layout-study-v1" || cfg.games_allowed !== false
      || cfg.maximum_frames !== 512 || cfg.maximum_output_bytes !== 50_000_000)
    throw Error("Use the finite completed-record layout plan");
  const protectionFile = await pinned(root, cfg.protection);
  const protection = await json(protectionFile);
  await protect(root, protection);
  await protect(root, cfg.sources);
  const objectiveFile = await pinned(root, cfg.objective_spec), spec = await json(objectiveFile);
  const objective = spec.evaluation_objective;
  if (spec.schema_version !== "full-run-training-objective-v1" || objective.id !== "terminal-victory-v1"
      || objective.primary !== "terminal_victory" || objective.constraint !== "cpu_time_per_run"
      || objective.whole_run_budget !== 128 || objective.auxiliary_reward_allowed !== false)
    throw Error("Preserve the versioned terminal-victory objective and whole-run budget");
  const reports = [];
  for (const source of cfg.completed_reports) {
    const file = await pinned(root, source), report = await json(file);
    if (report.report_id !== source.report_id
        || report.schema_version !== "native-live-checkpoint-adapter-result-v1"
        || !["live_checkpoint_delivery_blocked", "live_checkpoint_delivery_control_pass"].includes(report.status))
      throw Error("Expected an explicitly sealed completed diagnostic");
    for (const capture of source.captures) {
      if (report.evidence[capture.path] !== capture.sha256) throw Error("Capture is not sealed by its completed report");
      const item = report.cases.find(row => row.key === capture.case);
      const name = capture.host === "native" ? "shared-public.jsonl.gz" : "live-public.jsonl.gz";
      const expected = item?.[capture.host]?.policy_decisions ?? item?.[capture.host]?.probe?.policy_decisions;
      if (!["native", "official"].includes(capture.host) || expected !== capture.expected_frames
          || capture.path !== `${path.dirname(source.path)}/${capture.case}/${capture.host}/${name}`)
        throw Error("Use only declared completed public policy captures with their original counts");
      await pinned(root, capture);
    }
    reports.push({ source, report });
  }
  const workspace = local(root, cfg.workspace);
  if (!workspace.startsWith(path.join(root, "artifacts/native-input-layout") + path.sep))
    throw Error("Use a separate offline output directory");
  // No replacement or retries of interrupted studies; preserve evidence on error.
  await mkdir(workspace, { recursive: false });
  await writeFile(path.join(workspace, "active.json"), JSON.stringify({ config_id: digest(cfg) }) + "\n", { flag: "wx" });
  const snapshot = path.join(workspace, "source-at-launch");
  for (const [name, sha256] of Object.entries({ ...cfg.sources, [cfg.objective_spec.path]: cfg.objective_spec.sha256 })) {
    const destination = path.join(snapshot, name);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, await readFile(await pinned(root, { path: name, sha256 })), { flag: "wx" });
  }
  await mkdir(snapshot, { recursive: true });
  await writeFile(path.join(snapshot, "recipe.json"), JSON.stringify(cfg, null, 2) + "\n", { flag: "wx" });
  await writeFile(path.join(snapshot, "protection.json"), await readFile(protectionFile), { flag: "wx" });
  const outputPath = path.join(workspace, "converted-public-inputs.jsonl.gz");
  const output = createGzip(), file = createWriteStream(outputPath, { flags: "wx" });
  const writing = pipeline(output, file);
  writing.catch(() => {}); // Error is awaited below; avoid an early unhandled rejection.
  const summaries = [], initials = new Map(), probeGroups = new Set(), probeCounts = {};
  let frames = 0, rewrites = 0, unresolved = 0, outputBytes = 0;
  async function emit(value) {
    const line = JSON.stringify(value) + "\n";
    outputBytes += Buffer.byteLength(line);
    if (outputBytes > cfg.maximum_output_bytes) throw Error("Saved-layout study output cap");
    if (!output.write(line)) await once(output, "drain");
  }
  try {
    for (const { source } of reports) {
      for (const capture of source.captures) {
        let ordinal = 0;
        const summary = { cohort: source.cohort, case: capture.case, host: capture.host,
          capture: capture.path, frames: 0, rewrites: {}, unresolved: {} };
        for await (const row of publicLines(local(root, capture.path), deadline)) {
          if (row.kind !== "policy_input") continue;
          if (++frames > cfg.maximum_frames) throw Error("Saved-layout study frame cap");
          const frame = row.frame, input = frame.public_input;
          if (`sha256:${frame.input_digest}` !== digest(input)) throw Error("Saved input digest changed");
          const result = convert(input);
          if (digest(restore(result)) !== digest(input) || !actionsPreserved(result, input))
            throw Error("Saved public facts or legal choice identities changed");
          summary.frames++;
          for (const item of result.rewrites) { rewrites++; summary.rewrites[item.rule] = (summary.rewrites[item.rule] ?? 0) + 1; }
          for (const item of result.unresolved) { unresolved++; summary.unresolved[item.code] = (summary.unresolved[item.code] ?? 0) + 1; }
          if (!ordinal) {
            const identity = `${source.cohort}/${capture.case}`;
            if (!initials.has(identity)) initials.set(identity, {});
            initials.get(identity)[capture.host] = { before: input, after: result.canonical_input,
              source_family: frame.source_family };
          }
          const group = `${source.cohort}/${capture.host}/${frame.source_family}`;
          if (!probeGroups.has(group)) {
            probeGroups.add(group);
            for (const [name, change] of probes(input)) {
              const changed = structuredClone(input); change(changed);
              const altered = convert(changed);
              if (altered.canonical_digest === result.canonical_digest || digest(restore(altered)) !== digest(changed))
                throw Error(`Lost meaningful representation distinction: ${name}`);
              probeCounts[name] = (probeCounts[name] ?? 0) + 1;
            }
          }
          await emit({ cohort: source.cohort, case: capture.case, host: capture.host,
            ordinal: ordinal++, source_family: frame.source_family, ...result });
        }
        if (ordinal !== capture.expected_frames) throw Error("A completed capture is missing policy-input records");
        summaries.push(summary);
      }
    }
    output.end();
    await writing;
  } catch (error) { output.destroy(); file.destroy(); throw error; }
  const comparisons = [];
  for (const [name, pair] of initials) {
    if (!pair.native || !pair.official || pair.native.source_family !== "event_option"
        || pair.official.source_family !== "event_option"
        || pair.native.before.context.persistent.run.floor !== 1
        || pair.official.before.context.persistent.run.floor !== 1)
      throw Error("Initial-only comparison requires both fresh starting observations");
    comparisons.push({ pair: name,
      scope: "same_declared_world_initial_observations_before_any_delivered_choice_only",
      source_unchanged: "neither_replayed_nor_repaired_in_place",
      equal_before: digest(pair.native.before) === digest(pair.official.before),
      equal_after: digest(pair.native.after) === digest(pair.official.after),
      remaining_paths: differencePaths(pair.native.after, pair.official.after),
      later_states_compared_as_equal: false });
  }
  await protect(root, protection);
  await protect(root, cfg.sources);
  await pinned(root, cfg.objective_spec);
  // Recheck complete input files too, including unused lines, before sealing.
  for (const { source } of reports) {
    await pinned(root, source);
    for (const capture of source.captures) await pinned(root, capture);
  }
  const result = { schema_version: "offline-input-layout-study-result-v1", config_id: digest(cfg),
    status: "offline_preservation_checks_pass", frames, exact_round_trips: frames,
    legal_choice_sequences_preserved: frames, rewrites, unresolved_singleton_facts: unresolved,
    preservation_probes: probeCounts, probe_scope: "synthetic_public_input_distinctions_not_engine_effects_or_action_correctness",
    captures: summaries, initial_comparisons: comparisons,
    input_layout_identity: "offline-public-input-layout-v1", historical_and_repaired_cohorts_separate: true,
    unmatched_later_frames_used_for_parity: false, protected_files_unchanged: Object.keys(protection).length,
    protected_receipt_sha256: cfg.protection.sha256,
    originals_weights_and_all_Adam_bytes_unchanged: true,
    sources: cfg.sources, completed_report_ids: reports.map(row => row.source.report_id),
    full_run_objective: objective, training_spec_file_sha256: cfg.objective_spec.sha256,
    evidence: { "converted-public-inputs.jsonl.gz": await hash(outputPath) },
    wall_seconds: (performance.now() - started) / 1000,
    process_peak_resident_memory_bytes: process.resourceUsage().maxRSS * 1024,
    uncompressed_output_bytes: outputBytes,
    games_launched: 0, optimizer_updates: 0, training_allowed: false,
    full_compatibility_granted: false, production_ready: false, checkpoint_promoted: false,
    new_action_probabilities_or_playing_strength_evaluated: false };
  result.report_id = digest(result);
  await writeFile(path.join(workspace, "report.json"), JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
  await writeFile(path.join(workspace, "completed.json"), JSON.stringify({ report_id: result.report_id }) + "\n", { flag: "wx" });
  // Keep the active receipt as the launch identity; completed.json disambiguates it.
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const recipe = process.argv[2];
  if (!recipe || process.argv.length !== 3) throw Error("Pass one offline completed-record plan");
  const result = await run(rootDefault, recipe);
  console.log(JSON.stringify({ report_id: result.report_id, frames: result.frames,
    exact_round_trips: result.exact_round_trips,
    legal_choice_sequences_preserved: result.legal_choice_sequences_preserved,
    preservation_probes: result.preservation_probes, rewrites: result.rewrites,
    unresolved_singleton_facts: result.unresolved_singleton_facts,
    initial_comparisons: result.initial_comparisons.map(({ remaining_paths, ...row }) => row),
    protected_files_unchanged: result.protected_files_unchanged,
    wall_seconds: result.wall_seconds, games_launched: 0, optimizer_updates: 0,
    full_compatibility_granted: false }, null, 2));
}
