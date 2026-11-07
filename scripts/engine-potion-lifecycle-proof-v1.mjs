export async function readPotionLifecycle(spec, runtime) {
  const response = await fetch(`${spec.endpoint}/api/host-control/selection-provenance`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ expected_runtime_instance_id: runtime, host_control_token: spec.host_control_token }),
    signal: AbortSignal.timeout(3000),
  });
  if (!response.ok) throw Error("Potion lifecycle provenance unavailable");
  const value = await response.json();
  if (value.runtime_instance_id !== runtime || value.potion_lifecycle?.schema_version !== "native-potion-lifecycle-v1")
    throw Error("Foreign or unqualified potion lifecycle provenance");
  return value.potion_lifecycle;
}

export function requireFinishedPotionUse(receipt, proof) {
  const match = /^Native UI input was delivered \(native_noncombat_potion_use_enqueued:(\d+)\)/u.exec(receipt.detail ?? "");
  if (!match) throw Error("Missing exact native potion acceptance identity");
  const id = Number(match[1]);
  const observations = proof.observations.filter(row => row.accepted_action_id === id);
  if (!observations.length || proof.pending !== 0) throw Error("Potion completion is still pending");
  const last = observations.at(-1);
  if (last.state !== "Finished" || last.task_status !== "RanToCompletion"
      || last.faulted !== false || last.completion_proven !== true)
    throw Error("Native potion effect did not finish successfully");
  return { accepted_action_id: id, completion: last };
}
