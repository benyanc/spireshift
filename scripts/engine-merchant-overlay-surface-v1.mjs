// A map is an overlay; the native current room still owns the merchant target.
import {projectSelectionFlows as previous,selectionFlowReads} from "./engine-owned-inventory-identity-v1.mjs";
import {appendPotionControls} from "./engine-potion-surface-v1.mjs";
import {ownedBeltContext} from "./engine-relic-surface-v3.mjs";
export {selectionFlowReads};
const id=value=>typeof value==="string" && value.length>0;

export function merchantMapTarget(state) {
  const proof=state.merchant_map_target;
  if (proof==null) return null;
  if (state.decision!=="map_select" || state.context?.room_type!=="Shop"
      || proof.contract!=="native_current_merchant_room_under_map_v1"
      || !id(proof.room_ref) || !id(proof.merchant_ref) || proof.inventory_open!==false)
    throw Error("Unqualified current merchant/map target");
  for (const row of state.player?.potions??[]) {
    if (row.can_use && row.target_type==="TargetedNoCreature"
        && (row.id!=="FOUL_POTION" || row.valid_target_refs?.length!==1
          || row.valid_target_refs[0]!==proof.merchant_ref))
      throw Error("The current merchant target differs from the native potion operand");
  }
  return proof;
}

export function projectSelectionFlows(state,ctx,helpers) {
  const proof=merchantMapTarget(state);
  if (proof===null) return previous(state,ctx,helpers);
  // Keep the existing map/options/context. Register the belt once using the
  // room-qualified target instead of its former approach-only restriction.
  const baseCtx={...ctx,referent(value) {
    if (["potion","player","merchant"].includes(value.role))
      return {...value,referent_id:value.id,properties:{...value.properties,entity_id:value.id}};
    return ctx.referent(value);
  },action(value) {
    if (value.subject?.role!=="potion") ctx.action(value);
  }};
  const result=previous(state,baseCtx,helpers);
  const missing=(result.missing??[]).filter(reason=>reason!=="native_potion_merchant_target");
  const qualifiedMissing=result.complete===false && result.missing?.length===1
    && result.missing[0]==="native_potion_merchant_target";
  if (missing.length || result.kind!=="map_navigation" || (!result.complete && !qualifiedMissing))
    throw Error("Incomplete merchant map basis");
  const targetState={...state,decision:"merchant_approach",room_ref:proof.room_ref,
    merchant_ref:proof.merchant_ref,inventory_open:false};
  return appendPotionControls(targetState,ownedBeltContext(state,ctx),helpers,
    {...result,complete:true,missing:[]});
}
