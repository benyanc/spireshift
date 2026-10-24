// Reconstruct real recorded comparisons; no game launch or state repair happens here.
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { publicPolicyInput, stableJson } from "./engine-public-input-v1.mjs";
import { combatActionKey } from "./engine-combat-bridge-contract-v6.mjs";
import { verifyCombatEvidence } from "./verify-engine-combat-saved-v4.mjs";

export function projectPair(key, native, official) {
  const frames = [native, official];
  const result = { key, family: native.snapshot.interaction.kind };
  if (result.family !== official.snapshot.interaction.kind)
    throw Error("Matched observations have different decision families");
  for (const [index, host] of ["native", "official"].entries()) {
    const frame = frames[index], snapshot = frame.snapshot;
    const reads = frame.reads ?? [frame.deckRead];
    if (reads.some(read => !read || read.expected_snapshot_id !== snapshot.snapshot_id
        || read.observed_snapshot_id !== snapshot.snapshot_id
        || read.session?.runtime_instance_id !== snapshot.session.runtime_instance_id
        || read.completeness?.status !== "complete"
        || read.information_policy?.includes_hidden_information !== false))
      throw Error("Stale, partial, cross-runtime or hidden compatibility read");
    result[`${host}_input`] = publicPolicyInput(snapshot, reads);
    // Compare every offered action. The old mechanics comparison deliberately
    // excluded potion discard; that exclusion cannot qualify policy compatibility.
    result[`${host}_action_keys`] = snapshot.bound_actions.actions.map(action =>
      stableJson(combatActionKey(snapshot, action)));
    result[`missing_${host}_reads`] = snapshot.reads
      .filter(descriptor => !reads.some(read => read.read_id === descriptor.read_id))
      .map(descriptor => descriptor.kind);
  }
  return result;
}

export function replay(spec) {
  const json = file => JSON.parse(readFileSync(file, "utf8"));
  const native = json(spec.native), official = json(spec.official);
  const snapshots = readFileSync(spec.snapshots, "utf8").trim().split("\n").map(JSON.parse);
  const verified = verifyCombatEvidence(native, snapshots, official, spec.scenario);
  const pairs = snapshots.map((row, i) => projectPair(`${spec.key}-s${i}`, row,
    official.probe.comparisons[i]));
  return { verified, native_build_report_id: native.build_report_id,
    official_host_sha256: official.probe.capabilities.host.artifact_sha256 ?? null,
    pairs };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  process.stdout.write(`${JSON.stringify(replay(JSON.parse(input)))}\n`);
}
