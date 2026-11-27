import {completePublicMenu} from './engine-menu-probe.mjs';
import {stableJson} from './engine-public-input-v1.mjs';
export const BUNDLE_CONTRACT='committed_public_bundle_choice_v1';
export function bundleRoot(snapshot,action){
 if(snapshot.interaction.kind!=='card_bundle_selection'||snapshot.interaction.stage!=='choosing'||action.verb!=='select')throw Error('Not a fresh offered pack choice');
 const s=snapshot.interaction.content.surface,pack=s.bundles?.find(b=>b.entity_id===action.subject_referent_id);
 if(!pack||s.selected_bundle_entity_id!=null||!s.selectable_bundle_entity_ids?.includes(pack.entity_id)
   ||s.can_confirm!==false||s.can_cancel_preview!==false||!completePublicMenu(snapshot,snapshot.session.runtime_instance_id))throw Error('Incomplete current pack root');
 return structuredClone(pack);
}
export function bundleConfirmation(root,pack,preview){
 const s=preview.interaction.content.surface,runtime=root.session.runtime_instance_id;
 if(preview.session.runtime_instance_id!==runtime||preview.snapshot_id===root.snapshot_id
   ||preview.interaction.interaction_id!==root.interaction.interaction_id||preview.interaction.kind!=='card_bundle_selection'
   ||s.stage!=='preview'||s.selected_bundle_entity_id!==pack.entity_id||s.can_confirm!==true
   ||s.bundles?.length!==1||stableJson(s.bundles[0])!==stableJson(pack)||!completePublicMenu(preview,runtime))
   throw Error('Chosen pack or preview owner changed; no retry');
 const confirms=preview.bound_actions.actions.filter(a=>a.verb==='confirm'&&a.subject_referent_id===pack.entity_id);
 if(confirms.length!==1)throw Error('Pack confirmation is ambiguous or unavailable');
 return confirms[0];
}
export function verifyBundleCommit(root,action,preview,confirm,receipt,successor){
 const pack=bundleRoot(root,action),expected=bundleConfirmation(root,pack,preview);
 if(expected.bound_action_id!==confirm.bound_action_id||receipt.delivery!=='delivered'
   ||receipt.action?.bound_action_id!==confirm.bound_action_id||receipt.attribution?.runtime_instance_id!==root.session.runtime_instance_id
   ||successor.session.runtime_instance_id!==root.session.runtime_instance_id||successor.snapshot_id===preview.snapshot_id
   ||successor.interaction.interaction_id===root.interaction.interaction_id)
   throw Error('Pack commit not verified; preserve the attempt');
 return {contract:BUNDLE_CONTRACT,root_snapshot_id:root.snapshot_id,root_bound_action_id:action.bound_action_id,
   selected_bundle_entity_id:pack.entity_id,preview_snapshot:preview,confirm_action:confirm,confirm_receipt:receipt,
   successor_snapshot_id:successor.snapshot_id,game_committed:true};
}
