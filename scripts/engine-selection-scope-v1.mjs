import {BUNDLE_CONTRACT} from './engine-bundle-commit-v1.mjs';
export function prepareSelectionViews(snapshot,reads){
 const result=structuredClone({snapshot,reads}),s=result.snapshot.interaction.content.surface;
 if(result.snapshot.interaction.kind==='card_bundle_selection'&&s.stage==='choosing'
    &&Array.isArray(s.bundles)&&s.bundles.length&&s.bundles.every(b=>typeof b.entity_id==='string'&&b.cards?.every(c=>typeof c.entity_id==='string'))){
  const packs=new Map(s.bundles.map(b=>[b.entity_id,b]));
  if(packs.size!==s.bundles.length)throw Error('Duplicate pack owners');
  if(s.selection_contract!==BUNDLE_CONTRACT){
   if(s.selected_bundle_entity_id!=null||s.can_confirm!==false||s.can_cancel_preview!==false
     ||s.selectable_bundle_entity_ids?.length!==packs.size||s.selectable_bundle_entity_ids.some(id=>!packs.has(id)))throw Error('Incomplete fresh pack menu');
   s.selection_contract=BUNDLE_CONTRACT;
  }
  const selected=[];
  for(const a of result.snapshot.bound_actions.actions)if(a.verb==='select'&&packs.has(a.subject_referent_id)){
   const b=packs.get(a.subject_referent_id),names=b.cards.map(c=>c.name).join(', ');
   if(![`Preview bundle: ${names}`,`Take pack: ${names}`].includes(a.label))throw Error('Unexpected pack choice meaning');
   a.label=`Take pack: ${names}`;selected.push(b.entity_id);
  }
  if(new Set(selected).size!==packs.size||selected.length!==packs.size)throw Error('Missing complete pack action');
 }
 return result;
}
