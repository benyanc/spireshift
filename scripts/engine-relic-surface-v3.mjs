// Bind the noncombat belt to the same owned public potion/player instances as
// the persistent HUD. Private native operands and permissions are unchanged.
import { projectRelicSurface as previous, INVENTORY_CONTRACT } from './engine-relic-surface-v2.mjs';
export { INVENTORY_CONTRACT };
export function ownedBeltContext(state,ctx) {
  const rows=state.player?.potions??[],needsPlayer=rows.some(p=>p.can_use&&p.target_type==='AnyPlayer'),
    needsMerchant=rows.some(p=>p.can_use&&p.target_type==='TargetedNoCreature');
  const scoped={...ctx,referent(value){
    if(value.role==='potion') {
      const index=rows.findIndex(p=>value.id===ctx.id('belt_potion',ctx.snapshotId,p.native_ref));
      if(index>=0)value={...value,id:ctx.id('potion',ctx.snapshotId,rows[index].native_ref,index)};
    } else if(value.role==='player'&&value.id===ctx.id('potion_player',ctx.snapshotId,state.player?.native_ref)) {
      value={...value,id:ctx.id('player',ctx.snapshotId,state.player.native_ref)};
      if(!needsPlayer)return {...value,referent_id:value.id,properties:{...value.properties,entity_id:value.id}};
    } else if(value.role==='merchant'&&!needsMerchant)
      return {...value,referent_id:value.id,properties:{...value.properties,entity_id:value.id}};
    return ctx.referent(value);
  }};
  return scoped;
}

export function projectRelicSurface(state,ctx,helpers) {
  return previous(state,state.decision==='combat_play'||state.decision==='game_over'?ctx:ownedBeltContext(state,ctx),helpers);
}
