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
  "discard-automatic": {deck:["STRIKE_IRONCLAD","STRIKE_IRONCLAD","DEFEND_IRONCLAD","DEFEND_IRONCLAD","DEFEND_IRONCLAD"],
    potions:["FAIRY_IN_A_BOTTLE","STRENGTH_POTION"],obtain_relics:["PEN_NIB"]},
  "discard-duplicate": {deck:["STRIKE_IRONCLAD","STRIKE_IRONCLAD","DEFEND_IRONCLAD","DEFEND_IRONCLAD","DEFEND_IRONCLAD"],
    potions:["STRENGTH_POTION","STRENGTH_POTION"],obtain_relics:["PEN_NIB"]}
};
export const combatPlans=Object.fromEntries(Object.keys(combatFixtures).map(scenario=>[scenario,[
  {verb:"discard",slot:0},{verb:"use",id:"STRENGTH_POTION",slot:1},
  {verb:"play",id:"STRIKE_IRONCLAD"},{verb:"play",id:"DEFEND_IRONCLAD"},{verb:"end_turn"}
]]));

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
      row.entity_id===props.entity_id || Number.isSafeInteger(props.slot)
        && row.slot===props.slot && props.definition_id===row.definition_id);
    if(["potion","usable_potion","discardable_potion"].includes(ref.role) && potions.length===1) {
      if(props.slot!=null && props.slot!==potions[0].slot) throw Error("Potion moved from the offered slot");
      return {role:"potion",...fields(potions[0],["definition_id","slot"])};
    }
    throw Error("Unqualified combat operand or ambiguous potion identity");
  };
  let verb=action.verb;
  if(verb==="activate") {
    const ref=snapshot.referents.find(row=>row.referent_id===action.subject_referent_id);
    if(!ref || action.arguments.length!==0 || !(["discardable_potion","usable_potion"].includes(ref.role)
          && snapshot.interaction.content.surface.discardable_potions?.some(p=>p.entity_id===ref.properties.entity_id
            && action.label===`Discard ${p.name??p.entity_id} from slot ${p.slot+1}`)
        || ref.role==="potion" && ref.properties.can_discard===true && action.label===`Discard ${ref.properties.name}`))
      throw Error("Unknown combat activation outside the exact potion-discard menu");
    verb="discard";
  }
  if(!["play","use","discard","end_turn"].includes(verb))throw Error("Unsupported combat action in the full menu");
  return {verb,subject:action.verb==="end_turn" || action.subject_referent_id==null
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
  if(!tutorial) facts.actions=sorted(snapshot.bound_actions.actions.map(action=>combatActionKey(snapshot,action)));
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
      && (operation.slot==null || key.subject?.slot===operation.slot)
      && key.arguments.every(arg=>arg.target.role!=="enemy" || arg.target.index===0);
  }).sort((a,b)=>(combatActionKey(snapshot,a).subject?.index??0)-(combatActionKey(snapshot,b).subject?.index??0));
  if(!matches.length) throw Error(`The current game does not offer ${operation.verb} ${operation.id??""}`);
  return matches[0];
}

export function verifyCombatSignals(plan,scenario) {
  if(!Object.hasOwn(combatFixtures,scenario))throw Error("Unknown potion-discard fixture");
  const combat=plan.filter(row=>row.facts.kind==="combat_turn"),first=combat[0],last=combat.at(-1);
  const after=verb=>combat.find((row,index)=>index>0 && combat[index-1].action?.verb===verb);
  const removed=after("discard"),used=after("use");
  const strength=row=>row?.facts.combat.player.statuses.find(p=>p.definition_id==="STRENGTH_POWER")?.amount??0;
  const original=first?.facts.player.potions,remaining=removed?.facts.player.potions;
  const checks={second_turn_observed:first?.facts.combat.round===1 && last?.facts.combat.round===2,
    full_potion_discard_menu_present:first?.facts.actions.filter(a=>a.verb==="discard").length===2,
    exact_discard_slot_effect:original?.length===2 && remaining?.length===1 && remaining[0].slot===1
      && !remaining.some(p=>p.slot===0),
    other_slot_preserved:first!=null && removed!=null && firstDifference(original.find(p=>p.slot===1),remaining[0])==null,
    discard_does_not_use_effect:strength(first)===0 && strength(removed)===0,
    remaining_potion_used_once:used?.facts.player.potions.length===0 && strength(used)===2 && strength(last)===2,
    original_relic_counter_preserved:last?.facts.player.relics.find(r=>r.definition_id==="PEN_NIB")?.counter===1};
  if(scenario==="discard-automatic") checks.automatic_potion_is_discardable_without_manual_use=
    original?.find(p=>p.slot===0)?.definition_id==="FAIRY_IN_A_BOTTLE"
      && first.facts.actions.some(a=>a.verb==="discard" && a.subject.slot===0)
      && !first.facts.actions.some(a=>a.verb==="use" && a.subject.slot===0);
  else checks.identical_definitions_have_distinct_slots=original?.every(p=>p.definition_id==="STRENGTH_POTION")
    && new Set(first.facts.actions.filter(a=>a.verb==="use").map(a=>a.subject.slot)).size===2;
  if(Object.values(checks).some(ok=>ok!==true))throw Error(`Potion-discard signal missing: ${Object.keys(checks).filter(k=>!checks[k]).join(", ")}`);
  return checks;
}
