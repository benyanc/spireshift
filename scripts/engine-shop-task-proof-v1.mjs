// Diagnostic native-task evidence only; no field here is a policy input.
export async function readShopLifecycle(spec, runtime) {
  const response = await fetch(`${spec.endpoint}/api/host-control/selection-provenance`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ expected_runtime_instance_id: runtime, host_control_token: spec.host_control_token }),
    signal: AbortSignal.timeout(3000),
  });
  if (!response.ok) throw Error("Shop lifecycle provenance unavailable");
  const value = await response.json();
  if (value.runtime_instance_id !== runtime || value.shop_lifecycle?.schema_version !== "native-shop-task-lifecycle-v1")
    throw Error("Foreign or unqualified shop lifecycle provenance");
  return value.shop_lifecycle;
}

export function shopTaskIdentity(receipt) {
  const match = /;native_shop_task_started:(\d+)\)/u.exec(receipt.detail ?? "");
  if (receipt.delivery !== "delivered" || !match || !Number.isSafeInteger(Number(match[1])) || Number(match[1]) < 1)
    throw Error("Missing exact native shop task acceptance identity");
  return Number(match[1]);
}

export function requireShopProgress(receipt, proof, successor) {
  const id = shopTaskIdentity(receipt);
  if (proof.schema_version !== "native-shop-task-lifecycle-v1" || !Array.isArray(proof.observations)
      || ![0, 1].includes(proof.pending)) throw Error("Malformed native shop proof");
  const observations = proof.observations.filter(row => row.accepted_task_id === id);
  const last = observations.at(-1);
  if (!last || last.faulted !== false || last.canceled !== false)
    throw Error("Unknown or failed native shop task");
  if (last.completion_proven === true && last.task_status === "RanToCompletion"
      && typeof last.purchase_succeeded === "boolean" && proof.pending === 0)
    return { accepted_task_id: id, completed: true, purchase_succeeded: last.purchase_succeeded };
  // Connector JSON omits nullable properties until a result exists. Neither
  // null nor absence is an outcome; an actual boolean requires completion.
  if (proof.pending !== 1 || last.completion_proven !== false || last.purchase_succeeded != null
      || last.task_status !== "WaitingForActivation" || typeof last.active_child_entity_id !== "string"
      || last.active_child_entity_id !== successor.interaction?.interaction_id
      || successor.status !== "interactive" || !successor.bound_actions?.actions?.length)
    throw Error("Unfinished shop task has no exact native child input owner");
  return { accepted_task_id: id, completed: false, child_entity_id: last.active_child_entity_id };
}
