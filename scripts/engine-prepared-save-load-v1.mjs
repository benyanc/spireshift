import { createHash } from "node:crypto";
import { appendFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { gzipSync } from "node:zlib";

export async function loadPreparedSave(worker, source, seed, timeoutMs) {
  const save = JSON.parse(source);
  if (save.rng?.seed !== seed || save.ascension !== 8 || ![1, 2].includes(save.current_act_index))
    throw Error("Require a declared Ironclad/A8 later-act save");
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1)
    throw Error("Require a bounded prepared save load");
  const file = path.join(worker.spec.profile, "prepared-start.save");
  writeFileSync(file, source, { flag: "wx" });
  const request = { cmd: "load_save", path: file };
  const evidence = path.join(worker.spec.attempt, "prepared-load.jsonl");
  const record = row => appendFileSync(evidence, JSON.stringify(row) + "\n");
  record({ status: "dispatching", seed, save_sha256: createHash("sha256").update(source).digest("hex"),
    bytes: Buffer.byteLength(source), timeout_ms: timeoutMs, transport: "native_save_path" });
  let response;
  try {
    response = await worker.child.request(request, timeoutMs);
  } catch (error) {
    record({ status: "uncertain", error: error.message });
    throw Error(`Native prepared save load: ${error.message}`, { cause: error });
  }
  appendFileSync(path.join(worker.spec.attempt, "private-transcript.jsonl.gz"),
    gzipSync(JSON.stringify({ request, response }) + "\n"));
  if (response.type === "error") {
    record({ status: "native_error", error: response.message });
    throw Error(`Native prepared save load: ${response.message}`);
  }
  record({ status: "native_response", type: response.type, decision: response.decision });
  return worker.cursor.observe(response);
}
