import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { gunzipSync } from "node:zlib";
import { loadPreparedSave } from "./engine-prepared-save-load-v1.mjs";

const source = JSON.stringify({
  rng: { seed: "TEST123" }, ascension: 8, current_act_index: 1, data: "x".repeat(48_000),
});

test("prepared loads send a private file path and preserve the exact bytes", async t => {
  const target = mkdtempSync(path.join(os.tmpdir(), "spire-save-"));
  t.after(() => rmSync(target, { recursive: true, force: true }));
  const file = path.join(target, "prepared-start.save");
  const expected = { type: "decision", decision: "map_select" };
  let calls = 0;
  const worker = {
    spec: { attempt: target, profile: target },
    child: { request(request, timeout) {
      calls++;
      assert.deepEqual(request, { cmd: "load_save", path: file });
      assert.equal(timeout, 20_000);
      assert.equal(readFileSync(file, "utf8"), source);
      return expected;
    } },
    cursor: { observe(response) { return response; } },
  };
  assert.deepEqual(await loadPreparedSave(worker, source, "TEST123", 20_000), expected);
  await assert.rejects(loadPreparedSave(worker, source, "TEST123", 20_000), { code: "EEXIST" });
  assert.equal(calls, 1);
  const raw = JSON.parse(gunzipSync(readFileSync(path.join(target, "private-transcript.jsonl.gz"))));
  assert.deepEqual(raw, { request: { cmd: "load_save", path: file }, response: expected });
});

test("a missing reply records uncertainty and keeps the staged save", async t => {
  const target = mkdtempSync(path.join(os.tmpdir(), "spire-save-"));
  t.after(() => rmSync(target, { recursive: true, force: true }));
  const worker = {
    spec: { attempt: target, profile: target },
    child: { async request() { throw Error("test timeout"); } },
  };
  await assert.rejects(loadPreparedSave(worker, source, "TEST123", 20_000), /test timeout/u);
  const rows = readFileSync(path.join(target, "prepared-load.jsonl"), "utf8").trim().split("\n")
    .map(line => JSON.parse(line));
  assert.deepEqual(rows.map(row => row.status), ["dispatching", "uncertain"]);
  assert.equal(readFileSync(path.join(target, "prepared-start.save"), "utf8"), source);
});
