// A committed card answer is one model action. UI staging remains in the host.
// No missing boolean is supplied by this converter: these are new source facts.
import {projectExactCombatSurface,projectExactCombatReads} from './engine-combat-surface-v5.mjs';
export const ATOMIC_SELECTION='atomic_public_card_choice_v1';
export const ATOMIC_ACTION_LIMIT=512;
export function orderedChoices(items,min,max,cancelable,limit=ATOMIC_ACTION_LIMIT){
  if(!Array.isArray(items)||new Set(items).size!==items.length||!Number.isSafeInteger(min)||!Number.isSafeInteger(max)
    ||min<0||max<min||min>items.length||typeof cancelable!=='boolean')throw Error('Invalid exact atomic selection domain');
  const out=[];
  function visit(chosen,n){if(chosen.length===n){out.push([...chosen]);if(out.length+Number(cancelable)>limit)throw Error('atomic_selection_domain_exceeds_bound');return;}
    for(const item of items)if(!chosen.includes(item)){chosen.push(item);visit(chosen,n);chosen.pop();}}
  for(let n=min;n<=Math.min(max,items.length);n++)visit([],n);return out;
}
export class AtomicSelectionCursor {
  constructor(){this.active=null;}
  observe(state){return state;}
  handle(request){if(String(request.action).startsWith('selection_cursor_'))throw Error('The atomic contract cannot resume an older partial selection');return null;}
}
export function contextReference(value){
  if(typeof value.id!=='string'||!value.id)throw Error('Context view has no exact public identity');
  // Context is inspectable data; only the selector surface declares action referents.
  return {...value,referent_id:value.id,properties:{...value.properties,
    ...(value.includeEntityId===false?{}:{entity_id:value.id})}};
}
function identity(state,card,ctx){
  const permanent=state.player?.deck?.find(c=>c.native_ref===card.native_ref);
  if(permanent)return ctx.id('deck_card',permanent.native_ref,permanent.id,permanent.upgraded);
  const combat=state.selection_combat;
  for(const zone of combat?.combat_piles??[])if(zone.cards.some(c=>c.native_ref===card.native_ref))return ctx.id('pile_card',ctx.snapshotId,zone.pile,card.native_ref);
  return ctx.id('card',ctx.snapshotId,card.native_ref);
}
function cardFacts(state,card,ctx,helpers){
  if(typeof card.native_ref!=='string'||!card.native_ref||typeof card.upgraded!=='boolean')throw Error('Missing exact selectable card identity/upgrade');
  return {...helpers.cardProperties(card),entity_id:identity(state,card,ctx),is_selected:false};
}
export function projectAtomicSelection(state,ctx,helpers){
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
  for(const value of contextRefs)if(!selectedIds.has(value.id))ctx.referent({...value,
    // These are inspectable context operands while a selector owns input.
    ...(value.role==='playable_card'?{role:'hand',selected:false}:{})});
  const choices=orderedChoices(refs,state.min_select,state.max_select,state.cancelable);
  for(const chosen of choices)ctx.action({verb:'confirm',arguments:chosen.map(referent=>({role:'selected_card',referent})),
    label:chosen.length?'Confirm '+chosen.map(r=>r.label).join(', '):'Confirm empty selection',
    raw:{cmd:'action',action:'select_cards',args:{selection_ref:state.selection_ref,indices:chosen.map(r=>refs.indexOf(r)).join(',')}}});
  if(state.cancelable)ctx.action({verb:'cancel',label:'Cancel selection',raw:{cmd:'action',action:'skip_select',args:{selection_ref:state.selection_ref}}});
  return {kind:'card_selection',stage:'choosing',prompt:helpers.visibleText(state.prompt),context,
    surface:{kind:'card_selection',stage:'choosing',cards:refs.map(r=>r.properties),min_select:state.min_select,max_select:state.max_select,
      cancelable:state.cancelable,require_manual_confirmation:state.require_manual_confirmation,unpowered_previews:state.unpowered_previews,
      pretend_cards_can_be_played:state.pretend_cards_can_be_played,selection_contract:ATOMIC_SELECTION},
    complete:true,missing:[],visibleInformation:ATOMIC_SELECTION,interactionDiscovery:'native_exact_preferences_and_committed_ordered_card_answer'};
}
export function atomicSelectionReads(state,reads,ctx,helpers){
  const offered=[...reads];
  if(state.decision==='card_select'&&state.selection_combat){
    if(!Array.isArray(state.selection_combat.combat_piles))throw Error('Missing public piles under combat selection');
    // The base projector sees card_select, so it does not advertise its nested
    // combat's openable piles. Retain these actual public facts during selection;
    // otherwise the same discard card acquires an unrelated graph identity.
    if(!offered.some(read=>read.descriptor.kind==='combat_piles'))offered.push({
      descriptor:{read_id:ctx.id('read',ctx.snapshotId,'combat_piles'),kind:'combat_piles',target_referent_id:null,
        content_schema:'sts2.player-environment/read/combat_piles-1',visibility_basis:'player_openable_draw_discard_exhaust_pile_views',
        snapshot_bound:true,ordering_semantics:'unordered_multiset',hidden_by_policy:['draw_pile_true_order']},
      content:{kind:'combat_piles',zones:[]},completeness:{status:'complete',
        visible_information:'complete_for_player_visible_combat_pile_contents_without_draw_order',interaction_discovery:'read_only',
        missing:[],hidden_by_policy:['draw_pile_true_order']}});
  }
  const result=projectExactCombatReads(state.selection_combat??state,offered,ctx,helpers);
  if(state.decision!=='card_select')return result;
  for(const card of state.cards){const content=cardFacts(state,card,ctx,helpers);
    result.push({descriptor:{read_id:ctx.id('selection_detail',ctx.snapshotId,content.entity_id),kind:'surface_card',target_referent_id:content.entity_id,
      content_schema:'sts2.player-environment/read/surface_card-1',visibility_basis:'normal_player_visible_surface_card',snapshot_bound:true,ordering_semantics:'single_entity',hidden_by_policy:[]},
      content,completeness:{status:'complete',visible_information:'complete_current_player_visible_card_detail',interaction_discovery:'read_only',missing:[],hidden_by_policy:[]}});
  }
  return result;
}
