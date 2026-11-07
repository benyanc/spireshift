// Only the released Host's exact Combat Basics modal; buttons stay native public controls.
export function tutorialAction(snapshot) {
  const surface = snapshot.interaction?.content?.surface;
  const actions = snapshot.bound_actions?.actions;
  if (snapshot.interaction?.kind !== "tutorial" || surface?.tutorial_id !== "combat_rules_ftue"
      || surface.total_pages !== 3 || !Number.isSafeInteger(surface.current_page)
      || surface.current_page < 1 || surface.current_page > 3 || !Array.isArray(surface.options)
      || surface.options.length < 1 || surface.options.length > 2)
    throw new Error("Unqualified tutorial modal; no automatic dismissal");
  const allowed = surface.current_page < 3 ? ["advance_tutorial"]
    : ["dismiss_tutorial", "close_tutorial", "complete_tutorial"];
  const options = surface.options.filter((row) => row.enabled === true && allowed.includes(row.semantic_id));
  if (options.length !== 1) throw new Error("No unique public forward tutorial control");
  const matches = actions.filter((row) => row.verb === "activate" && row.label === options[0].label
    && row.subject_referent_id == null && row.arguments.length === 0);
  if (matches.length !== 1) throw new Error("Tutorial option does not bind uniquely");
  return matches[0];
}
