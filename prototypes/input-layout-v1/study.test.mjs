import assert from "node:assert/strict";
import test from "node:test";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, writeFile, rm, access } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { publicLines, run } from "./study.mjs";
import { digest } from "./converter.mjs";

const sha = value => createHash("sha256").update(value).digest("hex");
async function withDirectory(fn) {
  const root = await mkdtemp(path.join(os.tmpdir(), "spireshift-offline-layout-"));
  try { await fn(root); } finally { await rm(root, { recursive: true, force: true }); }
}
async function fixture(root) {
  const put = async (name, value) => {
    const bytes = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value) + "\n");
    const file = path.join(root, name); await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, bytes); return { path: name, sha256: sha(bytes) };
  };
  const saved = await put("saved-player-and-Adam.json", { weights: [1, 2], moments: [3, 4], steps: 42 });
  const protection = await put("protection.json", { [saved.path]: saved.sha256 });
  const objective = await put("objective.json", { schema_version: "full-run-training-objective-v1",
    evaluation_objective: { id: "terminal-victory-v1", primary: "terminal_victory",
      constraint: "cpu_time_per_run", whole_run_budget: 128, auxiliary_reward_allowed: false } });
  const sourcePath = "artifacts/completed/report.json", key = "fixture-start";
  const input = { schema_version: "actual-engine-public-entity-graph-v1", candidates: [], context: {
    persistent: { scope: "active_single_player_run", run: { floor: 1, act: 1, ascension: 8 },
      player: { character_definition_id: "IRONCLAD" } },
    interaction: { kind: "event_option", content: { surface: { kind: "event_option", options: [] }, context: { kind: "event" } } },
    reads: [], referents: [] } };
  const captures = [], report = { schema_version: "native-live-checkpoint-adapter-result-v1",
    report_id: "fixture-completed-report", status: "live_checkpoint_delivery_control_pass", evidence: {},
    cases: [{ key, native: { policy_decisions: 1 }, official: { probe: { policy_decisions: 1 } } }] };
  for (const host of ["native", "official"]) {
    const frame = { public_input: input, input_digest: digest(input).slice(7), source_family: "event_option" };
    const name = host === "native" ? "shared-public.jsonl.gz" : "live-public.jsonl.gz";
    const ref = await put(`artifacts/completed/${key}/${host}/${name}`,
      gzipSync(JSON.stringify({ kind: "policy_input", frame }) + "\n"));
    report.evidence[ref.path] = ref.sha256;
    captures.push({ ...ref, case: key, host, expected_frames: 1 });
  }
  const completed = await put(sourcePath, report);
  const cfg = { schema_version: "offline-input-layout-study-v1", games_allowed: false,
    maximum_frames: 512, maximum_output_bytes: 50_000_000, sources: {}, protection, objective_spec: objective,
    completed_reports: [{ ...completed, report_id: report.report_id, cohort: "fixture", captures }],
    workspace: "artifacts/native-input-layout/result" };
  await mkdir(path.join(root, "artifacts/native-input-layout"), { recursive: true });
  await put("plan.json", cfg);
  return { cfg, put, saved };
}

test("saved-record run reconstructs all inputs and preserves full saved-player bytes", async () => withDirectory(async root => {
  const { saved } = await fixture(root);
  const before = await readFile(path.join(root, saved.path));
  const result = await run(root, "plan.json");
  assert.equal(result.frames, 2); assert.equal(result.exact_round_trips, 2);
  assert.equal(result.initial_comparisons[0].equal_after, true);
  assert.equal(result.full_compatibility_granted, false);
  assert.equal(result.optimizer_updates, 0); assert.equal(result.games_launched, 0);
  assert.deepEqual(await readFile(path.join(root, saved.path)), before);
  await assert.rejects(run(root, "plan.json"), /EEXIST/);
}));

test("changed protected state stops before any output is created", async () => withDirectory(async root => {
  const { saved } = await fixture(root);
  await writeFile(path.join(root, saved.path), "changed Adam state");
  await assert.rejects(run(root, "plan.json"), /Changed sealed input/);
  await assert.rejects(access(path.join(root, "artifacts/native-input-layout/result")));
}));

test("an unsealed or truncated source cannot become a completed-record study", async () => withDirectory(async root => {
  const { cfg, put } = await fixture(root);
  cfg.completed_reports[0].captures[0].expected_frames = 2;
  await put("plan.json", cfg);
  await assert.rejects(run(root, "plan.json"), /original counts/);
  await assert.rejects(access(path.join(root, "artifacts/native-input-layout/result")));
}));

test("changing a sealed capture stops before output and never attempts recovery", async () => withDirectory(async root => {
  const { cfg } = await fixture(root);
  await writeFile(path.join(root, cfg.completed_reports[0].captures[0].path), gzipSync("{}\n"));
  await assert.rejects(run(root, "plan.json"), /Changed sealed input/);
  await assert.rejects(access(path.join(root, "artifacts/native-input-layout/result")));
}));

test("compressed record streaming bounds lines and propagates missing-file errors", async () => withDirectory(async root => {
  const file = path.join(root, "public.jsonl.gz");
  await writeFile(file, gzipSync(JSON.stringify({ text: "A".repeat(80_000) }) + "\n"));
  const collect = async (name, limit) => {
    const rows = [];
    for await (const row of publicLines(name, performance.now() + 1000, limit)) rows.push(row);
    return rows;
  };
  await assert.rejects(collect(file, 1024), /line cap/);
  assert.equal((await collect(file, 90_000))[0].text.length, 80_000);
  await assert.rejects(collect(file + ".missing", 1024), /ENOENT/);
}));
