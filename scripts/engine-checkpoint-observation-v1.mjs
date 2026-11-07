// READ-ONLY retries, before policy sampling. No submit/choice endpoint is accepted.
export function staleRead(error) {
  if (error?.statusCode !== 409 || typeof error.message !== "string") return false;
  const prefix = "Player Environment request failed with HTTP 409: ";
  if (!error.message.startsWith(prefix)) return false;
  try { return JSON.parse(error.message.slice(prefix.length)).error?.code === "stale_state"; }
  catch { return false; }
}

export async function collectCurrentFrame(initial, { read, refresh, journal = () => {},
  deadline, now = Date.now, maximumRefreshes = 3 }) {
  if (!Number.isInteger(maximumRefreshes) || maximumRefreshes < 0 || maximumRefreshes > 3
      || !Number.isFinite(deadline)) throw Error("Use the bounded read-only refresh contract");
  const runtime = initial.session?.runtime_instance_id;
  let snapshot = initial;
  for (let attempt = 0; attempt <= maximumRefreshes; attempt++) {
    if (now() >= deadline) throw Error("Read-only snapshot refresh wall cap");
    if (!runtime || snapshot.session?.runtime_instance_id !== runtime
        || snapshot.completeness?.status !== "complete"
        || snapshot.information_policy?.includes_hidden_information !== false
        || !Array.isArray(snapshot.reads)
        || new Set(snapshot.reads.map(row => row.read_id)).size !== snapshot.reads.length)
      throw Error("Changed runtime, incomplete state or ambiguous advertised reads");
    const reads = [];
    try {
      for (const descriptor of snapshot.reads) {
        if (now() >= deadline) throw Error("Read-only snapshot refresh wall cap");
        const result = await read(descriptor.read_id, snapshot.snapshot_id);
        if (result.kind !== descriptor.kind || result.read_id !== descriptor.read_id
            || result.expected_snapshot_id !== snapshot.snapshot_id || result.observed_snapshot_id !== snapshot.snapshot_id
            || result.session?.runtime_instance_id !== runtime || result.completeness?.status !== "complete"
            || result.information_policy?.includes_hidden_information !== false)
          throw Error("Successful advertised read has inconsistent ownership or completeness");
        reads.push(result);
      }
      if (now() >= deadline) throw Error("Read-only snapshot refresh wall cap");
      return { snapshot, reads, refreshes: attempt };
    } catch (error) {
      if (!staleRead(error)) throw error;
      journal({ kind: "stale_read_discarded", snapshot, reads,
        reason: "explicit_HTTP_409_stale_state_before_policy_choice", refresh: attempt,
        policy_sampled: false, action_submitted: false });
      if (attempt === maximumRefreshes || now() >= deadline)
        throw Error("Read-only snapshot refresh limit; no choice or action was made");
      const next = await refresh(snapshot.snapshot_id, deadline);
      if (next.snapshot_id === snapshot.snapshot_id) throw Error("Refresh returned the same stale snapshot");
      snapshot = next;
    }
  }
  throw Error("Unreachable read-only refresh state");
}
