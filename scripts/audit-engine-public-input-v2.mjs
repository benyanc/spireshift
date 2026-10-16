// Read-only regression over saved public observations. No engine or optimizer starts.
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { chooseRunAction } from "./engine-run-policy-v7.mjs";

export function renamePublicHandles(value, salt) {
  const handles = new Map();
  function collect(v) {
    if (Array.isArray(v)) return v.forEach(collect);
    if (!v || typeof v !== "object") return;
    for (const [key, item] of Object.entries(v)) {
      if (/(?:entity|referent)_id$/u.test(key) && typeof item === "string" && !handles.has(item))
        handles.set(item, `renamed-${salt}-${handles.size}`);
      collect(item);
    }
  }
  collect(value);
  const walk = v => Array.isArray(v) ? v.map(walk) : v && typeof v === "object"
    ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x)])) : handles.get(v) ?? v;
  return walk(value);
}

if (process.argv[1]?.endsWith("audit-engine-public-input-v2.mjs")) {
  const spec = JSON.parse(readFileSync(0, "utf8"));
  const directory = path.dirname(fileURLToPath(import.meta.url));
  for (const [name, expected] of Object.entries(spec.helpers_sha256 ?? {}))
    if (createHash("sha256").update(readFileSync(path.join(directory, name))).digest("hex") !== expected)
      throw Error("ID audit helper source changed");
  const files = [], families = {}, started = performance.now();
  let observations = 0, decisions = 0, comparisons = 0;
  for (const file of spec.public_traces) {
    const bytes = readFileSync(file);
    files.push({ path: file, sha256: createHash("sha256").update(bytes).digest("hex") });
    for (const line of (file.endsWith(".gz") ? gunzipSync(bytes) : bytes).toString().trim().split("\n")) {
      const row = JSON.parse(line); if (!row.snapshot || (row.stage && row.stage !== "observation")) continue;
      const { snapshot, reads } = row;
      const baseline = stableJson(publicPolicyInput(snapshot, reads));
      const hasActions = snapshot.bound_actions.actions.length > 0;
      const selected = hasActions ? chooseRunAction(snapshot).bound_action_id : null;
      for (let salt = 0; salt < spec.renamings; salt++) {
        const changed = renamePublicHandles({ snapshot, reads }, salt);
        if (stableJson(publicPolicyInput(changed.snapshot, changed.reads)) !== baseline
            || (hasActions && chooseRunAction(changed.snapshot).bound_action_id !== selected))
          throw Error(`ID invariance failed at observation ${row.index}`);
        comparisons++;
      }
      observations++; decisions += Number(hasActions);
      families[snapshot.interaction.kind] = (families[snapshot.interaction.kind] ?? 0) + 1;
    }
  }
  const result = { schema_version: "actual-engine-id-invariance-audit-v2", valid: true, files,
    helpers_sha256: spec.helpers_sha256,
    observations, decisions, comparisons, families, game_attempts: 0, optimizer_steps: 0,
    training_allowed: false, wall_seconds: (performance.now() - started) / 1000 };
  writeFileSync(spec.output, `${JSON.stringify(result, null, 2)}\n`, { flag: "wx" });
  console.log(JSON.stringify(result));
}
