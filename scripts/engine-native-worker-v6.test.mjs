import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { NativeWorker } from "./engine-native-worker-v6.mjs";

test("native option errors are preserved before the SDK can mistake them for an old menu", async () => {
  const attempt = mkdtempSync(path.join(os.tmpdir(), "spireshift-native-error-"));
  try {
    const worker = new NativeWorker(); worker.spec = { attempt };
    worker.child = { request: async () => ({ type: "error", message: "Event DENSE_VEGETATION failed" }) };
    await assert.rejects(worker.raw({ cmd: "action", action: "choose_option" }),
      /Native choose_option: Event DENSE_VEGETATION failed/u);
  } finally { rmSync(attempt, { recursive: true, force: true }); }
});

test("failure shutdown preserves diagnostics and native termination evidence without another action", async () => {
  const attempt = mkdtempSync(path.join(os.tmpdir(), "spireshift-retired-worker-"));
  try {
    const worker = new NativeWorker();
    worker.spec = { attempt };
    let calls = 0;
    const exit = { code: null, signal: "SIGTERM" };
    worker.child = { pid: 123, diagnostics: [{ line: "event failure" }],
      stop: async () => { calls++; return exit; } };
    await worker.stop();
    assert.equal(calls, 1);
    assert.deepEqual(JSON.parse(readFileSync(path.join(attempt, "native-process-stop.json"))),
      { process_id: 123, exit });
    assert.equal(JSON.parse(readFileSync(path.join(attempt, "diagnostics.json")))[0].line, "event failure");
  } finally { rmSync(attempt, { recursive: true, force: true }); }
});

test("stale, out-of-range and terminal actions never reach native submission", async () => {
  const worker = new NativeWorker();
  worker.snapshot = { snapshot_id: "current", bound_actions: { actions: [{ bound_action_id: "one" }] } };
  worker.facts = { terminal: false };
  let submissions = 0;
  worker.session = { submit: async () => { submissions++; throw Error("unexpected submission"); } };
  for (const request of [
    {snapshot_id: "old", action_index: 0}, {snapshot_id: "current", action_index: -1},
    {snapshot_id: "current", action_index: 1}, {snapshot_id: "current", action_index: 0.5}
  ]) await assert.rejects(worker.step(request), /Stale or unadvertised/u);
  worker.facts.terminal = true;
  await assert.rejects(worker.step({snapshot_id: "current", action_index: 0}), /Stale or unadvertised/u);
  assert.equal(submissions, 0);
});
test("uncertain native delivery preserves its cause without an automatic second attempt", async () => {
  const attempt = mkdtempSync(path.join(os.tmpdir(), "spireshift-native-uncertain-"));
  try {
    const worker = new NativeWorker(); worker.spec = { attempt }; worker.episodes = 1; worker.index = 0;
    worker.snapshot = { snapshot_id: "current", bound_actions: { actions: [{ bound_action_id: "one" }] } };
    worker.facts = { terminal: false }; worker.nativeError = "Native play_card: no exact native play was recorded";
    let submissions = 0;
    worker.session = { submit: async () => { submissions++; return { delivery: "unknown" }; } };
    await assert.rejects(worker.step({snapshot_id: "current", action_index: 0}), /no exact native play was recorded/u);
    assert.equal(submissions, 1); assert.equal(worker.index, 0);
  } finally { rmSync(attempt, { recursive: true, force: true }); }
});
