// Exact public card rewards, committed packs and merchant-owned selection reads.
import {projectRelicSurface as previous, INVENTORY_CONTRACT,ownedBeltContext} from './engine-relic-surface-v3.mjs';
import {projectAtomicSelection,atomicSelectionReads} from './engine-atomic-selection-v2.mjs';
import {appendPotionControls} from './engine-potion-surface-v1.mjs';
export {INVENTORY_CONTRACT};
export const BUNDLE_CONTRACT='committed_public_bundle_choice_v1';
const id=v=>typeof v==='string'&&v.length>0;
function properties(card,ctx,helpers,kind='offered_card'){
 if(!id(card.native_ref)||typeof card.is_selected!=='boolean'||typeof card.is_upgraded!=='boolean')throw Error('Missing source card copy/view flags');
 const p={...helpers.cardProperties(card),entity_id:ctx.id(kind,ctx.snapshotId,card.native_ref),is_selected:card.is_selected};
 if(card.star_cost!=null){if(card.star_cost!=='X'&&(!Number.isSafeInteger(card.star_cost)||card.star_cost<0))throw Error('Unknown current star cost');p.star_cost=String(card.star_cost);}
 return p;
}
const improved=helpers=>({...helpers,cardProperties(c){return {...helpers.cardProperties(c),...(c.star_cost==null?{}:{star_cost:String(c.star_cost)})};}});
function cardRef(c,ctx,helpers,kind){const p=properties(c,ctx,helpers,kind);return ctx.referent({role:'card',id:p.entity_id,label:p.name,selected:p.is_selected,properties:p});}
export function projectSelectionFlows(state,ctx,helpers){
 helpers=improved(helpers);
 if(state.decision==='combat_rewards_complete'){
  if(!id(state.room_ref)||typeof state.is_boss!=='boolean'||!Array.isArray(state.player?.potions)
     ||!Number.isSafeInteger(state.player.max_potion_slots))throw Error('Incomplete native completed-reward owner');
  ctx.action({verb:'activate',label:'Continue from rewards',raw:{cmd:'action',action:'proceed',args:{room_ref:state.room_ref}}});
  return appendPotionControls(state,ownedBeltContext(state,ctx),helpers,{kind:'reward_claim',stage:'ready',prompt:null,
   context:{kind:'reward_flow',reward_kind:'room_rewards',completed_boss_combat:state.is_boss},
   surface:{kind:'reward_claim',rewards:[],potion_slots_full:state.player.potions.filter(Boolean).length>=state.player.max_potion_slots,
    discardable_potions:[],can_proceed:true,proceed_skips_remaining_rewards:false},complete:true,missing:[],
   visibleInformation:'native_completed_combat_empty_reward_list',interactionDiscovery:'current_native_room_proceed_and_owned_belt'});
 }
 if(state.decision==='reward_set'){
  const owner={...ctx,referent(value){
   if(value.role!=='reward')return ctx.referent(value);
   const raw=state.rewards?.[value.occurrence];
   if(!id(raw?.native_ref))throw Error('Missing exact pending reward identity');
   return ctx.referent({...value,id:ctx.id('pending_reward',raw.native_ref)});
  }};
  return previous(state,owner,helpers);
 }
 if(state.decision==='card_select')return appendPotionControls(state,ownedBeltContext(state,ctx),helpers,projectAtomicSelection(state,ctx,helpers));
 if(state.decision==='card_reward'){
  if(!Array.isArray(state.cards)||!Array.isArray(state.alternatives))throw Error('Incomplete native reward alternatives');
  const cards=state.cards.map((c,i)=>{if(c.index!==i)throw Error('Ambiguous reward occurrence');const r=cardRef(c,ctx,helpers);ctx.action({verb:'select',subject:r,label:`Take ${r.label}`,raw:{cmd:'action',action:'select_card_reward',args:{card_index:i,card_ref:c.native_ref}}});return r.properties;});
  const alternatives=state.alternatives.map((a,i)=>{if(a.index!==i||!id(a.native_ref)||!id(a.label)||typeof a.enabled!=='boolean')throw Error('Missing reward alternative binding');
   const r=ctx.referent({role:'option',label:a.label,id:ctx.id('reward_alternative',ctx.snapshotId,a.native_ref),enabled:a.enabled,properties:{index:i,label:a.label,enabled:a.enabled}});
   if(a.enabled)ctx.action({verb:'activate',subject:r,label:a.label,raw:{cmd:'action',action:'select_card_reward_alternative',args:{alternative_ref:a.native_ref}}});return r.properties;});
  return appendPotionControls(state,ownedBeltContext(state,ctx),helpers,{kind:'card_reward_selection',stage:'ready',prompt:null,context:{kind:'reward_flow',reward_kind:'card_reward'},surface:{kind:'card_reward_selection',cards,alternatives,selectable_card_entity_ids:cards.map(c=>c.entity_id)},complete:true,missing:[],visibleInformation:"native_complete_current_reward_cards_and_alternatives",interactionDiscovery:"current_reward_card_or_native_alternative"});
 }
 if(state.decision==='bundle_select'){
  if(!id(state.selection_ref)||!Array.isArray(state.bundles)||!state.bundles.length||!state.selection_owner||!id(state.prompt))throw Error('Incomplete owned pack selection');
  const bundles=state.bundles.map((b,i)=>{if(b.index!==i||!id(b.native_ref)||!Array.isArray(b.cards)||!b.cards.length)throw Error('Incomplete pack item');
   const cards=b.cards.map(c=>cardRef(c,ctx,helpers,'bundle_card').properties);
   const r=ctx.referent({role:'bundle',id:ctx.id('bundle',ctx.snapshotId,b.native_ref),properties:{cards}});
   ctx.action({verb:'select',subject:r,label:`Take pack: ${cards.map(c=>c.name).join(', ')}`,raw:{cmd:'action',action:'select_bundle',args:{selection_ref:state.selection_ref,bundle_ref:b.native_ref,bundle_index:i}}});return r.properties;});
  return appendPotionControls(state,ownedBeltContext(state,ctx),helpers,{kind:'card_bundle_selection',stage:'choosing',prompt:state.prompt,context:{...state.selection_owner,run:state.context,player:helpers.withoutDeck(state.player)},surface:{kind:'card_bundle_selection',stage:'choosing',prompt:state.prompt,bundles,selection_contract:BUNDLE_CONTRACT},complete:true,missing:[],visibleInformation:"native_complete_current_owned_pack_cards",interactionDiscovery:"committed_public_bundle_choice_v1"});
 }
 if(['shop','merchant_approach'].includes(state.decision)&&state.shop_catalog)return shopSurface(state,ctx,helpers);
 return previous(state,ctx,helpers);
}
function catalog(raw,ctx,helpers,refs=false){
 const result={kind:'shop_catalog',access_state:raw.access_state};
 for(const group of ['cards','relics','potions','card_removal']){
  const rows=group==='card_removal'?(raw[group]?[raw[group]]:[]):raw[group];if(!Array.isArray(rows))throw Error('Incomplete native merchant catalog');
  const out=rows.map(e=>{if(!id(e.native_ref)||!Number.isSafeInteger(e.inventory_index))throw Error('Missing merchant entry identity');
   const {native_ref,card,relic,...facts}=e;const row={...facts,entity_id:ctx.id('shop_entry',ctx.snapshotId,native_ref),slot_entity_id:ctx.id('shop_slot',ctx.snapshotId,native_ref)};
   if(Object.hasOwn(e,'card'))row.card=card?(refs?cardRef(card,ctx,helpers,'shop_card').properties:properties(card,ctx,helpers,'shop_card')):null;
   if(Object.hasOwn(e,'relic')){if(relic){const {native_ref:ri,...rp}=relic;row.relic={...rp,entity_id:ctx.id('shop_relic',ctx.snapshotId,ri)};if(refs)ctx.referent({role:'relic',id:row.relic.entity_id,label:rp.name,properties:row.relic});}else row.relic=null;}
   for(const [k,v]of Object.entries(row))if(v===null)delete row[k];return row;});result[group]=group==='card_removal'?(out[0]??null):out;
 }
 return result;
}
function shopSurface(state,ctx,helpers){
 if(state.decision==='merchant_approach')return previous(state,ctx,helpers);
 const cat=catalog(state.shop_catalog,ctx,helpers,true);
 for(const group of ['cards','relics','potions','card_removal'])for(const [i,e] of (group==='card_removal'?(cat[group]?[cat[group]]:[]):cat[group]).entries()){
  const raw=group==='card_removal'?state.shop_catalog[group]:state.shop_catalog[group][i];
  const role=group==='card_removal'?'card_removal':group==='cards'?'card':group==='relics'?'relic':'potion';
  const name=e.card?.name??e.relic?.name??e.name??'Card removal';
  const {slot_entity_id,...owned}=e;const r=ctx.referent({role,id:e.entity_id,...(group==='potions'?{label:name}:{}),properties:owned});
  if(e.can_purchase)ctx.action({verb:group==='card_removal'?'open':'activate',subject:r,label:group==='card_removal'?`Choose a card to remove for ${e.price} gold`:`Buy ${name} for ${e.price} gold`,raw:{cmd:'action',action:group==='cards'?'buy_card':group==='relics'?'buy_relic':group==='potions'?'buy_potion':'remove_card',args:{entry_ref:raw.native_ref,item_ref:state[group==='card_removal'?'card_removal':group]?.[i]?.item_ref,quoted_cost:e.price}}});
 }
 ctx.action({verb:'cancel',label:'Close shop inventory',raw:{cmd:'action',action:'close_shop',args:{room_ref:state.room_ref}}});
 return appendPotionControls(state,ownedBeltContext(state,ctx),helpers,{kind:'shop_inventory',stage:'ready',prompt:null,context:{kind:'shop',run:state.context,player:helpers.withoutDeck(state.player)},surface:{kind:'shop_inventory',cards:cat.cards.map(({slot_entity_id,...e})=>e),relics:cat.relics.map(({slot_entity_id,...e})=>e),potions:cat.potions.map(({slot_entity_id,...e})=>e),card_removal:cat.card_removal?Object.fromEntries(Object.entries(cat.card_removal).filter(([k])=>k!=='slot_entity_id')):null,can_close:true},complete:true,missing:[],visibleInformation:"native_complete_current_merchant_catalog",interactionDiscovery:"current_native_entry_item_and_price"});
}
function detail(card,ctx){return {descriptor:{read_id:ctx.id('surface_detail',ctx.snapshotId,card.entity_id),kind:'surface_card',target_referent_id:card.entity_id,content_schema:'sts2.player-environment/read/surface_card-1',visibility_basis:'normal_player_visible_surface_card',snapshot_bound:true,ordering_semantics:'single_entity',hidden_by_policy:[]},content:card,completeness:{status:'complete',visible_information:'complete_current_player_visible_card_detail',interaction_discovery:'read_only',missing:[],hidden_by_policy:[]}};}
export function selectionFlowReads(state,reads,ctx,helpers){
 helpers=improved(helpers);const out=atomicSelectionReads(state,reads,ctx,helpers);
 const cards=state.decision==='card_reward'?state.cards:state.decision==='bundle_select'?state.bundles.flatMap(b=>b.cards):[];
 for(const c of cards)out.push(detail(properties(c,ctx,helpers,state.decision==='bundle_select'?'bundle_card':'offered_card'),ctx));
 if(state.shop_catalog){const cat=catalog(state.shop_catalog,ctx,helpers);out.push({descriptor:{read_id:ctx.id('shop_catalog',ctx.snapshotId),kind:'shop_catalog',target_referent_id:null,visibility_basis:'player_openable_current_merchant_inventory',content_schema:'sts2.player-environment/read/shop_catalog-1',snapshot_bound:true,ordering_semantics:'fixed_ui_slots',hidden_by_policy:[]},content:cat,completeness:{status:'complete',visible_information:'complete_current_player_visible_card_detail',interaction_discovery:'read_only',missing:[],hidden_by_policy:[]}});if(state.decision==='shop')for(const e of cat.cards)if(e.card)out.push(detail(e.card,ctx));}
 return out;
}
