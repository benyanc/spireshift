import { createInterface } from "node:readline";
import { requireShopProgress } from "./engine-shop-task-proof-v1.mjs";

for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
  const request = JSON.parse(line);
  try {
    const value = requireShopProgress(request.receipt, request.proof, request.successor);
    process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true, value })}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: false, error: error.message })}\n`);
  }
}
