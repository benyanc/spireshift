// Bounded streaming independent-frame diagnostics; never sends a game command.
import { createInterface } from "node:readline";
import { inspectFrame } from "./engine-interface-contract-v1.mjs";
for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
  const request = JSON.parse(line);
  try {
    const result = inspectFrame(request.snapshot, request.reads, request.contract);
    process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true, result })}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: false, error: error.message })}\n`);
  }
}
