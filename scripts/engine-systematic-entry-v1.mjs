// Exact save-entry control, separate from the fresh-run startup contract.
export function chooseFixtureEntry(snapshot) {
  if(!["main_menu","singleplayer_menu"].includes(snapshot.interaction.kind))
    throw Error("Unsupported diagnostic save entry");
  const actions=snapshot.bound_actions.actions.filter(row=>row.label==="Continue the saved run");
  if(actions.length!==1)throw Error("No unique current native saved-run control");
  return actions[0];
}
