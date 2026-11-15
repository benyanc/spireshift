// Authenticated host evidence is transport verification, never a policy feature.
export function requireAtomicCompletion(body,snapshot,action,requestId,runtime){
 const p=body?.selection,chosen=(action.arguments??[]).filter(a=>a.role==='selected_card').map(a=>a.referent_id);
 const cancel=action.verb==='cancel';
 if(body?.runtime_instance_id!==runtime||p?.request_id!==requestId||p.root_snapshot_id!==snapshot.snapshot_id
   ||p.status!==(cancel?'canceled':'committed')||p.game_committed!==!cancel
   ||JSON.stringify(p.chosen_card_ids)!==JSON.stringify(chosen)||!Array.isArray(p.steps)||!p.steps.length)
   throw Error('Atomic selection completion is missing, stale, cross-runtime or uncertain; no retry');
 for(const step of p.steps)if(step.accepted!==true||typeof step.candidate_id!=='string'||!step.candidate_id
   ||!['select','preview','confirm','cancel'].includes(step.kind))throw Error('Unverified semantic selection primitive');
 if(JSON.stringify(p.steps.filter(s=>s.kind==='select').map(s=>s.card_id))!==JSON.stringify(chosen)
    ||p.steps.length>chosen.length+3)throw Error('Semantic selection delivered a different ordered card choice');
 const final=p.steps.at(-1).kind;
 if(cancel?final!=='cancel':final!=='confirm'&&!(final==='select'&&p.automatic_commit_allowed===true&&p.maximum_selection===chosen.length))
   throw Error('Selection left its owner without a qualified commit');
 return p;
}
