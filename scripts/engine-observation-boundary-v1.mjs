// The pinned SnapshotBuilder emits interactive / observed / settling / visible_unsupported.
export function observationBoundary(snapshot,runtime,previous=null) {
  if(snapshot?.session?.runtime_instance_id!==runtime)throw Error("Official runtime changed");
  if(snapshot.status==="visible_unsupported"||snapshot.status==="unsupported"
    ||snapshot.completeness?.status==="unsupported")throw Error("Unsupported official state; no fallback action");
  if(!["interactive","observed","settling"].includes(snapshot.status))throw Error("Unknown official observation status");
  if(snapshot.information_policy?.includes_hidden_information!==false)throw Error("Nonpublic official observation");
  if(snapshot.snapshot_id!==previous&&snapshot.completeness?.status==="complete"
    &&["interactive","observed"].includes(snapshot.status))return "ready";
  return "wait";
}
