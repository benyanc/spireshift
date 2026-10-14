import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { NativeWorker } from "./engine-native-worker-v4.mjs";

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
