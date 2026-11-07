// The released Host uses advance_tutorial on all three Combat Basics pages.
// Resolve its current public forward button; never choose the previous-page button.
export function tutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  const actions = snapshot.bound_actions?.actions;
  if (snapshot.interaction?.kind !== "tutorial" || surface?.tutorial_id !== "combat_rules_ftue"
      || surface.total_pages !== 3 || !Number.isSafeInteger(surface.current_page)
      || surface.current_page < 1 || surface.current_page > 3 || !Array.isArray(surface.options)
      || surface.options.length < 1 || surface.options.length > 2 || !Array.isArray(actions))
    throw new Error("Unqualified tutorial modal; no automatic dismissal");
  const options = surface.options.filter((row) => row.enabled === true
    && row.semantic_id === "advance_tutorial");
  if (options.length !== 1) throw new Error("No unique public forward tutorial control");
  const matches = actions.filter((row) => row.verb === "activate" && row.label === options[0].label
    && row.subject_referent_id == null && Array.isArray(row.arguments) && row.arguments.length === 0);
  if (matches.length !== 1) throw new Error("Tutorial option does not bind uniquely");
  return matches[0];
}
