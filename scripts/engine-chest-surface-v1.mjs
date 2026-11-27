// Exact single-player chest lifecycle, including complete public relic hover facts.
// Current raw operands remain in the action ledger, outside the public graph.
import { projectSelectionFlows as previous, INVENTORY_CONTRACT } from "./engine-selection-flows-v9.mjs";
import { ownedBeltContext } from "./engine-relic-surface-v3.mjs";
import { appendPotionControls } from "./engine-potion-surface-v1.mjs";
export { INVENTORY_CONTRACT, selectionFlowReads } from "./engine-selection-flows-v9.mjs";

const identity = value => typeof value === "string" && value.length > 0;
const stages = {treasure_chest:"closed",treasure_relic:"relic_choice",treasure_complete:"completed"};

export function chestRelicFacts(relic, index, ctx, helpers) {
  if(relic.index!==index || !identity(relic.native_ref) || !identity(relic.id)
    || !identity(relic.name) || typeof relic.description!=="string" || !identity(relic.rarity)
    || relic.hover_facts_complete!==true || !Array.isArray(relic.keywords)
    || !Array.isArray(relic.card_previews))throw Error("Incomplete current treasure relic public facts");
  const {index:ordinal,native_ref,id,hover_facts_complete,...visible}=relic;
  for(const tip of visible.keywords)
    if(!identity(tip.name) || !(tip.description===null || typeof tip.description==="string"))
      throw Error("Incomplete treasure keyword hover");
  const entity_id=ctx.id("treasure_relic",ctx.snapshotId,native_ref);
  const card_previews=visible.card_previews.map((card,i)=>{
    if(!identity(card.id) || !identity(card.name) || typeof card.cost!=="string"
      || typeof card.is_upgraded!=="boolean" || card.is_selected!==false
      || typeof card.description!=="string" || !Object.hasOwn(card,"star_cost"))
      throw Error("Incomplete treasure card preview");
    const {id:cardId,native_ref:cardRef,index:cardIndex,upgraded,
      enchantment_id,enchantment_description,enchantment_amount,
      affliction_id,affliction_description,affliction_amount,...view}=card;
    const props={...view,...helpers.cardProperties(card),
      entity_id:ctx.id("treasure_hover_card",ctx.snapshotId,native_ref,i,card.id),
      star_cost:card.star_cost===null?null:String(card.star_cost),
      is_selected:false,unplayable_reason:card.unplayable_reason??null};
    if(!Object.hasOwn(props,"enchantment"))props.existing_enchantment=null;
    ctx.referent({role:"card_preview",id:props.entity_id,label:props.name,selected:false,properties:props});
    return props;
  });
  return {...visible,entity_id,definition_id:helpers.cardProperties(relic).definition_id,
    keywords:structuredClone(visible.keywords),card_previews};
}

export function projectSelectionFlows(state, ctx, helpers) {
  if(!Object.hasOwn(stages,state.decision))return previous(state,ctx,helpers);
  const stage=stages[state.decision];
  if(!identity(state.room_ref) || state.stage!==stage
    || !["chest_opened","can_choose","can_skip","can_proceed"].every(key=>typeof state[key]==="boolean"))
    throw Error("Missing current treasure lifecycle/permission export");
  if(state.chest_opened!==(stage!=="closed") || state.can_choose!==(stage==="relic_choice")
    || state.can_proceed!==(stage==="completed") || state.can_skip!==(stage==="relic_choice"))
    throw Error("Inconsistent or unsettled single-player treasure controls");
  const current=ownedBeltContext(state,ctx);
  let relics=[];
  if(stage==="relic_choice") {
    if(!Array.isArray(state.relics) || state.relics.length!==1)
      throw Error("Expected exact native single-player treasure holder");
    relics=state.relics.map((raw,index)=>{
      const properties=chestRelicFacts(raw,index,current,helpers);
      const subject=current.referent({role:"relic",id:properties.entity_id,label:properties.name,properties});
      current.action({verb:"activate",subject,label:`Take ${properties.name}`,
        raw:{cmd:"action",action:"select_treasure_relic",args:{relic_ref:raw.native_ref}}});
      return subject.properties;
    });
    current.action({verb:"skip",label:"Skip the visible treasure relic",
      raw:{cmd:"action",action:"skip_treasure_relic",args:{room_ref:state.room_ref}}});
  } else {
    if(Object.hasOwn(state,"relics") && (!Array.isArray(state.relics) || state.relics.length))
      throw Error("Treasure relic facts outside their current visible phase");
    current.action(stage==="closed"
      ? {verb:"open",label:"Open the treasure chest",raw:{cmd:"action",action:"open_treasure",args:{room_ref:state.room_ref}}}
      : {verb:"activate",label:"Continue from the treasure room",raw:{cmd:"action",action:"leave_room",args:{room_ref:state.room_ref}}});
  }
  return appendPotionControls(state,current,helpers,{
    kind:"treasure_room",stage,prompt:null,context:{kind:"treasure",run:state.context,player:helpers.withoutDeck(state.player)},
    surface:{kind:"treasure_room",stage,chest_opened:state.chest_opened,relics,
      can_choose:state.can_choose,can_skip:state.can_skip,can_proceed:state.can_proceed},
    complete:true,missing:[],visibleInformation:"current_native_single_player_treasure_controls_and_hover_facts",
    interactionDiscovery:"stable_native_chest_relic_choice_and_completion"});
}
