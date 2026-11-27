// Two declared A8 combat fixtures. Rules, playability and all effects remain game-owned.
import { completePublicMenu } from "./engine-menu-probe.mjs";
import { actionKey as journeyAction, firstDifference, intentAmounts } from "./engine-journey-contract-v2.mjs";
import { restPersistentFacts } from "./engine-rest-bridge-contract.mjs";
export { firstDifference };

const sorted = rows => [...rows].sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b),"en"));
const fields = (row, keys) => Object.fromEntries(keys.map(key => {
  if(row?.[key] == null) throw Error(`Missing combat comparison field: ${key}`);
  return [key,row[key]];
}));
const text = value => {
  if(typeof value!=="string" || !value.trim() || /\{[A-Za-z][^}]*\}/u.test(value))
    throw Error("Missing or unresolved public combat description");
  return value.replace(/\s+/gu," ").trim();
};
const card = row => ({...fields(row,["definition_id","cost","is_upgraded","can_play","target_type"]),
  description:text(row.description)});
const power = row => ({...fields(row,["definition_id","amount","type"]),description:text(row.description)});

export const combatFixtures = {
  corruption: { deck:["CORRUPTION","DEFEND_IRONCLAD","DEFEND_IRONCLAD","STRIKE_IRONCLAD","BASH"],
    potions:["STRENGTH_POTION","SPEED_POTION"], obtain_relics:["PEN_NIB"] },
  "temporary-stats": {deck:["INFLAME","STRIKE_IRONCLAD","STRIKE_IRONCLAD","DEFEND_IRONCLAD","DEFEND_IRONCLAD"],
    potions:["FLEX_POTION","SPEED_POTION"], obtain_relics:["PEN_NIB"]}
};
export const combatPlans = {
  corruption:[{verb:"play",id:"CORRUPTION"},{verb:"play",id:"DEFEND_IRONCLAD"},
    {verb:"play",id:"DEFEND_IRONCLAD"},{verb:"end_turn"}],
  "temporary-stats":[{verb:"play",id:"INFLAME"},{verb:"use",id:"FLEX_POTION"},
    {verb:"use",id:"SPEED_POTION"},{verb:"play",id:"STRIKE_IRONCLAD"},
    {verb:"play",id:"DEFEND_IRONCLAD"},{verb:"end_turn"}]
};

const optionalText=value=>value==null || value===""?null:text(value);

export function combatActionKey(snapshot, action) {
  const kind=snapshot.interaction.kind;
  if(kind!=="combat_turn") return journeyAction(snapshot,action);
  const context=snapshot.interaction.content.context;
  const operand=id=>{
    const ref=snapshot.referents.find(row=>row.referent_id===id);
    if(!ref) throw Error("Combat action operand is not in the current menu");
    const props=ref.properties;
    const hand=context.player.hand.findIndex(row=>row.entity_id===props.entity_id);
    if(hand>=0) return {role:"hand",index:hand,...fields(context.player.hand[hand],["definition_id","cost","is_upgraded"])};
    const enemy=context.enemies.findIndex(row=>row.entity_id===props.entity_id);
    if(enemy>=0) return {role:"enemy",index:enemy,...fields(context.enemies[enemy],["definition_id"])};
    if(ref.role==="player" && (props.player_entity_id===context.player.player_entity_id
        || props.entity_id===context.player.player_entity_id)) return {role:"player"};
    const potions=snapshot.persistent.content.player.potions.filter(row=>
      row.entity_id===props.entity_id || props.definition_id!=null && row.definition_id===props.definition_id);
    if(["potion","usable_potion"].includes(ref.role) && potions.length===1)
      return {role:"potion",...fields(potions[0],["definition_id","slot"])};
    throw Error("Unqualified combat operand or ambiguous potion identity");
  };
  return {verb:action.verb,subject:action.verb==="end_turn" || action.subject_referent_id==null
    ?null:operand(action.subject_referent_id),
    arguments:sorted(action.arguments.map(arg=>({role:arg.role,target:operand(arg.referent_id)})))};
}

export function combatBridgeFacts(snapshot, deckRead, {tutorial=false}={}) {
  if(!completePublicMenu(snapshot,snapshot.session?.runtime_instance_id))
    throw Error("Combat comparison needs a complete current public menu");
  const actualKind=snapshot.interaction.kind,kind=tutorial?"combat_turn":actualKind;
  if(!["event_option","map_navigation","combat_turn"].includes(kind)
      || tutorial && actualKind!=="tutorial") throw Error("Unqualified combat comparison state");
  const facts={kind,...restPersistentFacts(snapshot,deckRead)};
  const player=snapshot.persistent.content.player;
  facts.player.relics=sorted(player.relics.map(row=>({...fields(row,["definition_id"]),
    counter:row.counter??null,description:text(row.description)})));
  facts.player.potions=sorted(player.potions.map(row=>({...fields(row,["definition_id","slot"]),description:text(row.description)})));
  // Explicit scope: the current shipped Host omits combat potion discard.
  // Preserve that gap; compare play/use/end-turn, not complete game-action parity.
  if(!tutorial) facts.actions=sorted(snapshot.bound_actions.actions
    .filter(action=>kind!=="combat_turn" || ["play","use","end_turn"].includes(action.verb))
    .map(action=>combatActionKey(snapshot,action)));
  const surface=snapshot.interaction.content.surface,context=snapshot.interaction.content.context;
  if(kind==="event_option") facts.options=surface.options.map(row=>({...fields(row,["index","title","is_locked"]),description:optionalText(row.description)}));
  if(kind==="map_navigation") facts.next_options=sorted(surface.next_options.map(row=>fields(row,["col","row","point_type"])));
  if(kind==="combat_turn") {
    if(context?.kind!=="combat" || !Array.isArray(context.player?.hand)
        || !Array.isArray(context.player.statuses) || !Array.isArray(context.enemies))
      throw Error("Incomplete public combat ownership");
    facts.combat={...fields(context,["round","turn_owner","is_play_phase"]),
      player:{...fields(context.player,["block","energy","max_energy","draw_pile_count","discard_pile_count","exhaust_pile_count"]),
        hand:context.player.hand.map(card),statuses:sorted(context.player.statuses.map(power))},
      enemies:context.enemies.map(row=>({...fields(row,["definition_id","hp","max_hp","block"]),
        statuses:sorted(row.statuses.map(power)),
        intents:row.intents.map(intent=>({...fields(intent,["type","label","title","description"]),...intentAmounts(intent)}))}))};
  }
  return facts;
}

export function chooseCombatBridgeAction(snapshot,{startingOption,operation}) {
  const actions=snapshot.bound_actions.actions,kind=snapshot.interaction.kind;
  if(kind==="event_option") {
    if(startingOption) {
      const matches=actions.filter(row=>combatActionKey(snapshot,row).subject?.title===startingOption);
      if(matches.length===1) return matches[0];
    }
    if(actions.length===1 && actions[0].verb==="activate" && actions[0].arguments.length===0
        && combatActionKey(snapshot,actions[0]).subject?.title==="Proceed") return actions[0];
    throw Error("The fixed starting option or event exit is not uniquely offered");
  }
  if(kind==="map_navigation") {
    const candidates=actions.filter(row=>["monster","combat"].includes(combatActionKey(snapshot,row).subject?.point_type))
      .sort((a,b)=>{const x=combatActionKey(snapshot,a).subject,y=combatActionKey(snapshot,b).subject;return x.row-y.row||x.col-y.col;});
    if(!candidates.length) throw Error("No public first combat route");
    return candidates[0];
  }
  if(kind!=="combat_turn" || !operation) throw Error("No declared combat operation");
  const matches=actions.filter(row=>{
    const key=combatActionKey(snapshot,row);
    return key.verb===operation.verb && (operation.id==null || key.subject?.definition_id===operation.id)
      && key.arguments.every(arg=>arg.target.role!=="enemy" || arg.target.index===0);
  }).sort((a,b)=>(combatActionKey(snapshot,a).subject?.index??0)-(combatActionKey(snapshot,b).subject?.index??0));
  if(!matches.length) throw Error(`The current game does not offer ${operation.verb} ${operation.id??""}`);
  return matches[0];
}

export function verifyCombatSignals(plan,scenario) {
  const combat=plan.filter(row=>row.facts.kind==="combat_turn"),first=combat[0]?.facts,last=combat.at(-1)?.facts;
  if(!first || !last || first.combat.round!==1 || last.combat.round!==2)
    throw Error("Both initial and subsequent combat turns are required");
  const amount=(row,id)=>row.facts.combat.player.statuses.find(p=>p.definition_id===id)?.amount??0;
  const after=id=>combat.find((row,index)=>index>0 && combat[index-1].action?.subject?.definition_id===id);
  const checks={second_turn_observed:true};
  if(scenario==="corruption") {
    const changed=after("CORRUPTION"),defends=changed?.facts.combat.player.hand.filter(c=>c.definition_id==="DEFEND_IRONCLAD");
    checks.native_global_cost_reduction=changed?.facts.combat.player.energy===0 && defends?.length===2
      && defends.every(c=>c.cost==="0" && c.can_play===true);
    checks.skills_exhaust_and_preserve_energy=combat.some(row=>row.facts.combat.player.exhaust_pile_count===2 && row.facts.combat.player.energy===0);
    checks.corruption_owned_by_player=changed!=null && amount(changed,"CORRUPTION_POWER")===1
      && changed.facts.combat.enemies.every(e=>!e.statuses.some(p=>p.definition_id==="CORRUPTION_POWER"));
  } else if(scenario==="temporary-stats") {
    const boosted=after("SPEED_POTION"),struck=after("STRIKE_IRONCLAD");
    checks.separate_strength_dexterity=boosted!=null && amount(boosted,"STRENGTH_POWER")===7 && amount(boosted,"DEXTERITY_POWER")===5;
    checks.temporary_stats_expire=amount(combat.at(-1),"STRENGTH_POWER")===2 && amount(combat.at(-1),"DEXTERITY_POWER")===0;
    checks.relic_counter_tracks_attack=first.player.relics.find(r=>r.definition_id==="PEN_NIB")?.counter===0
      && struck?.facts.player.relics.find(r=>r.definition_id==="PEN_NIB")?.counter===1;
    checks.consumed_potions_removed=boosted?.facts.player.potions.length===0;
  } else throw Error("Unknown combat fixture");
  if(Object.values(checks).some(ok=>ok!==true)) throw Error(`Combat signal missing: ${Object.keys(checks).filter(key=>!checks[key]).join(", ")}`);
  return checks;
}
