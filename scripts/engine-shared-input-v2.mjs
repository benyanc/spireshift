// Versioned consolidation. All prior projectors/results remain immutable.
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { sharedDecision as original, deliveredAction } from "./engine-shared-input-v1.mjs";
import { publicShopSlots } from "./engine-interface-contract-v1.mjs";
import { newDiagnosticNavigation, recordDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
export { CONTRACT, deliveredAction } from "./engine-shared-input-v1.mjs";
export function sharedDecision(snapshot, reads, navigation = null) {
  const fixed = publicShopSlots(snapshot, reads);
  return original(fixed.snapshot, fixed.reads, navigation);
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const navigation = newDiagnosticNavigation(); let current;
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      if (request.command === "commit") {
        if (!current || request.acknowledgement?.delivery !== "delivered") throw Error("No delivered shared choice");
        const action = deliveredAction(current.frame, request, current.snapshot);
        if (request.acknowledgement.bound_action_id !== action.bound_action_id
            || request.acknowledgement.runtime_instance_id !== current.frame.observation.runtime_instance_id)
          throw Error("Wrong shared navigation receipt");
        recordDiagnosticNavigation(navigation, current.snapshot, action, request.acknowledgement); current = null;
        process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true })}\n`); continue;
      }
      if (current) throw Error("Previous choice is unacknowledged");
      const frame = sharedDecision(request.snapshot, request.reads, request.navigation ?? navigation);
      current = { snapshot: request.snapshot, frame };
      process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true, frame })}\n`);
    } catch (e) {
      process.stdout.write(`${JSON.stringify({ request_id: request?.request_id, ok: false, error: e.message })}\n`);
      process.exitCode = 1; break;
    }
  }
}
