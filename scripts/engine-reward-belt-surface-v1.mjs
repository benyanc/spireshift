// A single native-owned belt registration for full-belt potion reward menus.
// Earlier projectors and their strict SDK remain unchanged.
import { projectSelectionFlows as previous, selectionFlowReads } from "./engine-chest-surface-v1.mjs";
import { ownedBeltContext } from "./engine-relic-surface-v3.mjs";
import { appendPotionControls } from "./engine-potion-surface-v1.mjs";
export { selectionFlowReads };
const identity = value => typeof value === "string" && value.length > 0;

export function projectSelectionFlows(state, ctx, helpers) {
  if (state.decision !== "reward_set" || state.potion_slots_full !== true
      || !state.rewards?.some(r => r.kind === "potion")) return previous(state, ctx, helpers);
  const rows = state.player?.potions, capacity = state.player?.max_potion_slots;
  if (!Array.isArray(rows) || !Number.isSafeInteger(capacity) || capacity <= 0
      || rows.length !== capacity || rows.some(r => r == null)
      || !Array.isArray(state.rewards) || typeof state.can_skip !== "boolean"
      || typeof state.is_terminal !== "boolean" || typeof state.can_proceed !== "boolean")
    throw Error("Inconsistent native full-belt reward owner");
  const current = ownedBeltContext(state, ctx);
  const rewards = state.rewards.map((r, index) => {
    if (r.index !== index || !identity(r.native_ref) || !identity(r.kind)
        || !identity(r.name) || !(r.description == null || typeof r.description === "string"))
      throw Error("Incomplete current reward identity or public facts");
    const enabled = r.kind !== "potion", kind = r.kind === "card_choice" ? "card" : r.kind;
    const item = current.referent({role:"reward", id:ctx.id("pending_reward",r.native_ref),
      label:r.name, enabled, occurrence:index,
      properties:{kind,label:r.name,description:r.description??null,enabled}});
    if(enabled)current.action({verb:"activate",subject:item,label:`Claim ${r.name}`,
      raw:{cmd:"action",action:"select_reward",args:{reward_ref:r.native_ref}}});
    return item.properties;
  });
  if(state.is_terminal && state.can_proceed) {
    if(!identity(state.room_ref))throw Error("Missing native terminal reward owner");
    current.action({verb:"activate",label:"Skip remaining rewards and continue",
      raw:{cmd:"action",action:"proceed",args:{room_ref:state.room_ref}}});
  } else if(!state.is_terminal && state.can_skip)
    current.action({verb:"skip",label:"Skip remaining rewards",raw:{cmd:"action",action:"skip_rewards"}});
  const result = appendPotionControls(state,current,helpers,{kind:"reward_claim",stage:"ready",prompt:null,
    context:{kind:"reward_flow",reward_kind:"room_rewards"},
    surface:{kind:"reward_claim",rewards,potion_slots_full:true,discardable_potions:[],
      can_proceed:state.is_terminal&&state.can_proceed,proceed_skips_remaining_rewards:rewards.length>0},
    complete:true,missing:[],visibleInformation:"current_native_rewards_and_single_owned_belt",
    interactionDiscovery:"native_full_belt_claim_discard_use_and_skip"});
  result.surface.discardable_potions=result.surface.potion_states.filter(p=>p.can_discard);
  return result;
}
