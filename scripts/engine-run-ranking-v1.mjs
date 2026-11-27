import { createHash } from "node:crypto";
import { publicEntityGraph, stableJson } from "./engine-public-input-v1.mjs";
import { actionSemantics, diagnosticScore } from "./engine-run-policy-v2.mjs";
export { actionSemantics, diagnosticScore } from "./engine-run-policy-v2.mjs";

export function publicActionKey(snapshot, action) {
  const graph = publicEntityGraph(snapshot), semantic = actionSemantics(snapshot, action);
  const candidate = graph.action(action);
  const controlOnly = ["skip_card", "skip_optional", "leave_shop", "proceed", "confirm", "cancel", "close"].includes(semantic);
  return stableJson({ semantic, ...candidate,
    label: controlOnly ? semantic : candidate.label,
    subject: controlOnly ? null : candidate.subject });
}

export function chooseRunAction(snapshot, scoreAction = diagnosticScore) {
  const actions = snapshot.bound_actions?.actions;
  if (!actions?.length) throw Error("Diagnostic policy has no legal action");
  const graph = publicEntityGraph(snapshot);
  const ranked = actions.map(action => {
    const score = scoreAction(snapshot, action);
    if (!Number.isFinite(score)) throw Error("Action score must be finite");
    const key = stableJson(graph.action(action));
    return { action, score, tie: createHash("sha256").update(key).digest("hex") };
  });
  ranked.sort((a, b) => b.score - a.score || (a.tie < b.tie ? -1 : a.tie > b.tie ? 1 : 0));
  return ranked[0].action;
}
