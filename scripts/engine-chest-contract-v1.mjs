// Validate the actual complete public chest menu before any policy sampling.
export function requireChestMenu(snapshot) {
  if(snapshot.interaction?.kind!=="treasure_room")return;
  const content=snapshot.interaction.content, surface=content?.surface;
  const actions=snapshot.bound_actions?.actions;
  if(content?.context?.kind!=="treasure" || surface?.kind!=="treasure_room"
    || !["closed","relic_choice","completed"].includes(surface.stage)
    || !["chest_opened","can_choose","can_skip","can_proceed"].every(key=>typeof surface[key]==="boolean")
    || !Array.isArray(surface.relics) || !Array.isArray(actions) || !Array.isArray(snapshot.referents))
    throw Error("Incomplete current public chest contract");
  const choose=surface.stage==="relic_choice";
  if(surface.chest_opened!==(surface.stage!=="closed") || surface.can_choose!==choose
    || surface.can_skip!==choose || surface.can_proceed!==(surface.stage==="completed"))
    throw Error("Unsettled or contradictory public chest permissions");
  if(surface.relics.length!==Number(choose))throw Error("Ambiguous current treasure holder");
  const controls=[];
  for(const action of actions) {
    const subject=action.subject_referent_id==null?null:
      snapshot.referents.find(row=>row.referent_id===action.subject_referent_id);
    if(action.subject_referent_id!=null && !subject)throw Error("Unowned chest action subject");
    if(subject?.role==="potion")continue; // Existing global belt contract remains separate.
    if(action.interaction_id!==snapshot.interaction.interaction_id || action.arguments?.length!==0)
      throw Error("Foreign or unexpected chest control operands");
    controls.push(action);
    if(surface.stage==="closed") {
      if(subject!==null || action.verb!=="open" || action.label!=="Open the treasure chest")
        throw Error("Incorrect current chest Open binding");
    } else if(surface.stage==="completed") {
      if(subject!==null || action.verb!=="activate" || action.label!=="Continue from the treasure room")
        throw Error("Incorrect completed chest Continue binding");
    } else if(subject===null) {
      if(action.verb!=="skip" || action.label!=="Skip the visible treasure relic")
        throw Error("Incorrect current treasure Skip binding");
    } else if(subject.role!=="relic" || subject.referent_id!==surface.relics[0].entity_id
      || subject.properties?.entity_id!==surface.relics[0].entity_id || action.verb!=="activate"
      || action.label!==`Take ${surface.relics[0].name}`)
      throw Error("Take does not bind the current visible relic");
  }
  if(controls.length!==(choose?2:1) || new Set(controls.map(row=>row.verb)).size!==controls.length)
    throw Error("Incomplete or duplicated current chest menu");
  if(choose) {
    const relic=surface.relics[0];
    if(typeof relic.entity_id!=="string" || !relic.entity_id || typeof relic.definition_id!=="string"
      || !relic.definition_id || typeof relic.name!=="string" || typeof relic.description!=="string"
      || typeof relic.rarity!=="string" || !Array.isArray(relic.keywords) || !Array.isArray(relic.card_previews))
      throw Error("Incomplete current treasure relic hover facts");
  }
}
