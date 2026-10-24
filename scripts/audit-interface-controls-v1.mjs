// Stream independent completed public frames; no live client, action or model loading.
import { createInterface } from "node:readline";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { sharedDecision } from "./engine-shared-input-v3.mjs";
import { sharedDecision as previous } from "./engine-shared-input-v2.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";
import { caseBank, POLICY, PRESENTATION } from "./engine-interface-case-bank-v1.mjs";
import { mutationChecks } from "./engine-interface-mutations-v1.mjs";

export function auditFrame(snapshot, reads, includeInput = false) {
  const before = stableJson({ snapshot, reads }), issues = [];
  let oldError = null, frame;
  try { previous(snapshot, reads); } catch (error) { oldError = error.message; }
  try { frame = sharedDecision(snapshot, reads); }
  catch (error) { issues.push({ code: "conversion_blocked", detail: error.message }); }
  if (stableJson({ snapshot, reads }) !== before) throw Error("Source public observation mutated");
  if (frame) {
    const actions = snapshot.bound_actions.actions;
    if (frame.actions.length !== actions.length
        || new Set(frame.actions.map(row => row.raw_index)).size !== actions.length
        || frame.actions.some(row => actions[row.raw_index]?.bound_action_id !== row.bound_action_id))
      throw Error("Legal actions or raw delivery ownership changed");
    const surface = snapshot.interaction.content.surface;
    if (Array.isArray(surface.selected_card_entity_ids) && Array.isArray(surface.cards)) {
      const selected = surface.cards.filter(card => card.is_selected === true).map(card => card.entity_id).sort();
      const declared = [...surface.selected_card_entity_ids].sort();
      if (stableJson(selected) !== stableJson(declared))
        issues.push({ code: "active_selection_flags_disagree_with_current_selection", detail: snapshot.interaction.kind });
      if (Number.isInteger(surface.selected_count) && surface.selected_count !== declared.length)
        issues.push({ code: "selected_count_disagrees_with_owned_cards", detail: snapshot.interaction.kind });
    }
  }
  return { family: snapshot.interaction.kind, converted: !!frame, issues, previous_error: oldError,
    repaired_previous_failure: oldError !== null && !!frame,
    legal_actions: frame?.actions.length ?? null, terminal: frame?.terminal ?? false,
    scoped_card_view_fact_groups: frame?.public_input.context.referents.reduce((n, row) =>
      n + Object.keys(row.properties?.public_card_views ?? {}).length, 0) ?? 0,
    input: includeInput ? frame : undefined };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  for await (const line of createInterface({ input: process.stdin, crlfDelay: Infinity })) {
    let request;
    try {
      request = JSON.parse(line);
      if (request.command === "case_bank") {
        const cases = caseBank().map(row => ({ key: row.key, source_kind: row.snapshot.interaction.kind,
          frame: sharedDecision(row.snapshot, row.reads) }));
        process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true,
          cases, policy_kinds: POLICY, presentation_kinds: PRESENTATION })}\n`); continue;
      }
      if (request.command === "mutations") {
        process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true, results: mutationChecks() })}\n`); continue;
      }
      process.stdout.write(`${JSON.stringify({ request_id: request.request_id, ok: true,
        result: auditFrame(request.snapshot, request.reads, request.include_input === true) })}\n`);
    } catch (error) {
      process.stdout.write(`${JSON.stringify({ request_id: request?.request_id, ok: false, error: error.message })}\n`);
    }
  }
}
