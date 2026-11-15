// Native-only compact answer grammar; small menus retain the exact old contract.
import {projectSelectionFlows as previous,selectionFlowReads} from "./engine-reward-belt-surface-v1.mjs";
import {cardFacts,contextReference} from "./engine-atomic-selection-v6.mjs";
import {projectExactCombatSurface} from "./engine-combat-surface-v6.mjs";
import {appendPotionControls} from "./engine-potion-surface-v1.mjs";
import {ownedBeltContext} from "./engine-relic-surface-v3.mjs";
import {PLAN} from "./engine-ordered-plan-v1.mjs";
export {selectionFlowReads};
export function projectSelectionFlows(state,ctx,helpers){
  if(!state.answer_plan)return previous(state,ctx,helpers);
  const result=projectPlan(state,ctx,helpers);
  // Before selecting an answer, keep every unrelated native belt action available.
  // Once an answer prefix exists the conditional grammar is local model work.
  return state.answer_plan.selected.length===0 ? appendPotionControls(state,ownedBeltContext(state,ctx),helpers,result) : result;
}
function enchantmentPreview(value){
  if(value==null)return {};
  if(typeof value!=="object"||Array.isArray(value)||typeof value.definition_id!=="string"||!value.definition_id
    ||typeof value.name!=="string"||typeof value.description!=="string"||!Number.isSafeInteger(value.amount)
    ||value.observation_source!=="native_command_enchantment_and_amount")throw Error("Incomplete exact native enchantment preview");
  return {enchantment:structuredClone(value)};
}
function projectPlan(state,ctx,helpers){
  if(state.decision!=='card_select')throw Error('Not an atomic card selector');
  if(state.selection_preferences_complete!==true||typeof state.selection_ref!=='string'||!state.selection_ref
    ||!Array.isArray(state.cards)||new Set(state.cards.map(c=>c.native_ref)).size!==state.cards.length)
    throw Error('Incomplete exact native selection source');
  for(const flag of ['cancelable','require_manual_confirmation','unpowered_previews','pretend_cards_can_be_played'])
    if(typeof state[flag]!=='boolean')throw Error(`Missing current selection preference: ${flag}`);
  if(!state.selection_owner||!['event','rest','shop','combat','treasure'].includes(state.selection_owner.kind))throw Error('Missing public selector owner');
  let context={...state.selection_owner,run:state.context,player:helpers.withoutDeck(state.player)};
  const contextRefs=[];
  if(state.selection_combat){
    const observed=projectExactCombatSurface(state.selection_combat,{...ctx,action(){},referent(value){
      contextRefs.push(value);return contextReference(value);
    }},helpers);
    if(observed.missing.some(m=>m!=='native_local_player_play_phase'))throw Error(`Incomplete selected combat observation: ${observed.missing}`);
    context=observed.context;
  }
  const refs=state.cards.map(card=>{const props=cardFacts(state,card,ctx,helpers);return ctx.referent({role:'card',id:props.entity_id,label:props.name,selected:false,properties:props});});
  const selectedIds=new Set(refs.map(r=>r.properties.entity_id));
  // The global HUD appender registers actionable belt operands exactly once.
  // Their inspectable sparse context stays above; never duplicate one physical
  // bottle under the same ID in the referent catalog.
  const belt=state.player?.potions??[];
  const beltIds=new Set(belt.map((p,i)=>ctx.id('potion',ctx.snapshotId,p.native_ref,i)));
  const needsPlayer=belt.some(p=>p.can_use&&p.target_type==='AnyPlayer');
  const registeredByBelt=value=>['potion','usable_potion'].includes(value.role)&&beltIds.has(value.id)
    || needsPlayer&&value.role==='player'&&value.id===ctx.id('player',ctx.snapshotId,state.player.native_ref);
  for(const value of contextRefs)if(!selectedIds.has(value.id)&&!registeredByBelt(value))ctx.referent({...value,
    // These are inspectable context operands while a selector owns input.
    ...(value.role==='playable_card'?{role:'hand',selected:false}:{})});
  const selected=state.answer_plan.selected;
  if(state.answer_plan.contract!==PLAN||!Array.isArray(selected)||new Set(selected).size!==selected.length
     ||selected.some(i=>!Number.isSafeInteger(i)||i<0||i>=refs.length)||selected.length>state.max_select)
    throw Error("Invalid public ordered answer prefix");
  const args={selection_ref:state.selection_ref,prefix:selected.join(',')};
  if(selected.length<Math.min(state.max_select,refs.length))for(let i=0;i<refs.length;i++)if(!selected.includes(i))
    ctx.action({verb:'select',subject:refs[i],label:'Append '+refs[i].label,
      raw:{cmd:'action',action:'ordered_answer_append',args:{...args,index:i}}});
  if(selected.length>=state.min_select)ctx.action({verb:'confirm',arguments:selected.map(i=>({role:'selected_card',referent:refs[i]})),
    label:selected.length?'Commit ordered answer: '+selected.map(i=>refs[i].label).join(', '):'Commit empty answer',
    raw:{cmd:'action',action:'ordered_answer_commit',args}});
  if(state.cancelable)ctx.action({verb:'cancel',label:'Cancel selection',raw:{cmd:'action',action:'ordered_answer_cancel',args}});
  return {kind:'card_selection',stage:'choosing',prompt:helpers.visibleText(state.prompt),context,
    surface:{kind:'card_selection',stage:'choosing',cards:refs.map(r=>r.properties),min_select:state.min_select,max_select:state.max_select,
      cancelable:state.cancelable,require_manual_confirmation:state.require_manual_confirmation,unpowered_previews:state.unpowered_previews,
      pretend_cards_can_be_played:state.pretend_cards_can_be_played,selection_contract:PLAN,answer_plan:{contract:PLAN,selected:[...selected],native_commits_only_at_answer_completion:true},...enchantmentPreview(state.enchantment)},
    complete:true,missing:[],visibleInformation:PLAN,interactionDiscovery:'compact_ordered_answer_grammar_without_native_prefix_actions'};
}
