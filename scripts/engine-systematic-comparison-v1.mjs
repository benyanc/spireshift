// Differential interface checks. Artificial probes and actual game effects stay separate.
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { createHash } from "node:crypto";
import { fixture, POLICY, PRESENTATION } from "./engine-interface-case-bank-v1.mjs";
import { projectExactRestSurface } from "./engine-rest-surface.mjs";
import { sharedDecision, deliveredAction } from "./engine-shared-input-v15.mjs";
import { restoreLayout } from "./engine-input-layout-v12.mjs";
import { stableJson } from "./engine-public-input-v1.mjs";

export const SURFACES = [...PRESENTATION,...POLICY,"game_over"].sort();
const digest = value => createHash("sha256").update(stableJson(value)).digest("hex");
export function inspect(snapshot,reads) {
  const original=stableJson({snapshot,reads}), frame=sharedDecision(snapshot,reads);
  if(original !== stableJson({snapshot,reads}))throw Error("Comparison mutated source evidence");
  if(digest(restoreLayout(frame.layout_evidence)) !== frame.layout_evidence.original_digest)
    throw Error("Irreversible public layout");
  if(frame.actions.length !== snapshot.bound_actions.actions.length)throw Error("Incomplete action menu");
  if(!frame.terminal)for(const [index,binding] of frame.actions.entries()) {
    const action=deliveredAction(frame,{binding_id:frame.binding_id,action_index:index},snapshot);
    if(action.bound_action_id !== binding.bound_action_id)throw Error("Changed original action binding");
  }
  const fields=[];
  function walk(value,at="") {
    fields.push(`${at.replace(/\/\d+(?=\/|$)/gu,"/*")}:${value===null?"null":Array.isArray(value)?"array":typeof value}`);
    if(Array.isArray(value))value.forEach((v,i)=>walk(v,`${at}/${i}`));
    else if(value&&typeof value==="object")for(const [key,item] of Object.entries(value))walk(item,`${at}/${key}`);
  }
  walk(frame.public_input);
  return {frame,fields:[...new Set(fields)].sort()};
}

export function differences(left,right,at="",result=[]) {
  if(stableJson(left)===stableJson(right))return result;
  if(left&&right&&typeof left==="object"&&typeof right==="object"
    &&!Array.isArray(left)&&!Array.isArray(right)) {
    for(const key of [...new Set([...Object.keys(left),...Object.keys(right)])].sort()) {
      const next=`${at}/${key}`;
      if(!Object.hasOwn(left,key)||!Object.hasOwn(right,key))result.push(next);
      else differences(left[key],right[key],next,result);
    }
  } else if(Array.isArray(left)&&Array.isArray(right)&&left.length===right.length)
    left.forEach((value,index)=>differences(value,right[index],`${at}/${index}`,result));
  else result.push(at);
  return result;
}

// Both fixtures use actual producer code: the native rest projector and vectors
// serialized by the compiled official ProjectVisibleFacts/DescribeCommands methods.
export function restProducerPair(vector) {
  const original=structuredClone(vector);
  const make=()=>{
    const row=fixture("rest_site","systematic");row.snapshot.referents=[];
    row.snapshot.bound_actions.actions=[];return row;
  };
  const native=make(), official=make(), options=vector.projection.surface.options;
  const refs=[],actions=[];
  const ctx={referent(value){
    const referent_id=options[value.occurrence].entity_id;
    const item={...value,referent_id,properties:{...value.properties,entity_id:referent_id},
      state:{enabled:value.enabled,visible:true}};
    refs.push(item);return item;
  },action(value){actions.push(value);}};
  const state={decision:"rest_site",room_ref:"private-room",can_leave:vector.proceed,
    options:options.map(row=>({index:row.index,native_ref:`private-${row.index}`,option_id:row.option_id,
      name:row.name,description:row.description,is_enabled:row.enabled}))};
  const projected=projectExactRestSurface(state,ctx,{withoutDeck:value=>value,visibleText:value=>value,
    defaultProjector:()=>{throw Error("Unexpected producer delegation");}});
  if(!projected.complete)throw Error("Incomplete native rest producer");
  native.snapshot.interaction.content={context:{kind:"rest"},surface:projected.surface};
  native.snapshot.referents=refs.map(row=>({referent_id:row.referent_id,role:row.role,label:row.label,
    properties:row.properties,state:row.state}));
  native.snapshot.bound_actions.actions=actions.map((action,index)=>({bound_action_id:`native-${index}`,
    interaction_id:native.snapshot.interaction.interaction_id,verb:action.verb,label:action.label,
    ...(action.subject?{subject_referent_id:action.subject.referent_id}:{}),arguments:[]}));
  official.snapshot.interaction.content=structuredClone(vector.projection);
  official.snapshot.referents=options.map(row=>({referent_id:row.entity_id,role:"option",label:row.name,
    properties:structuredClone(row),state:{visible:true,enabled:row.enabled}}));
  official.snapshot.bound_actions.actions=vector.commands.map((command,index)=>({bound_action_id:`official-${index}`,
    interaction_id:official.snapshot.interaction.interaction_id,verb:"activate",label:command.label,
    ...(command.kind==="choose_rest_option"?{subject_referent_id:
      command.entity_bindings.find(row=>row.role==="rest_option").entity_id}:{}),arguments:[]}));
  for(const row of [native,official])row.snapshot.bound_actions.total_count=
    row.snapshot.bound_actions.materialized_count=row.snapshot.bound_actions.actions.length;
  if(stableJson(original)!==stableJson(vector))throw Error("Mutated official producer vector");
  return {native,official};
}

export function generatedChecks(vectors) {
  const results=[];
  const check=(key,body)=>{
    try{body();results.push({key,passed:true});}
    catch(error){results.push({key,passed:false,error:error.message});}
  };
  const require=(condition,message)=>{if(!condition)throw Error(message);};
  for(const vector of vectors) {
    const pair=restProducerPair(vector), key=`rest-${Number(vector.heal)}${Number(vector.smith)}${Number(vector.proceed)}`;
    if(!vector.heal&&!vector.smith&&!vector.proceed) {
      check(`${key}-no-fabricated-action`,()=>{
        for(const row of Object.values(pair)) {
          require(row.snapshot.bound_actions.actions.length===0,"Invented a rest action");
          let rejected=false;try{inspect(row.snapshot,row.reads);}catch{rejected=true;}
          require(rejected,"Empty transient surface admitted as a decision");
        }
      });continue;
    }
    check(`${key}-actual-producer-parity`,()=>require(differences(
      inspect(pair.native.snapshot,pair.native.reads).frame.public_input,
      inspect(pair.official.snapshot,pair.official.reads).frame.public_input).length===0,"Rest producers disagree"));
    for(const side of ["native","official"]) {
      for(const mutation of ["missing-exit","contradictory-exit","missing-enabled","wrong-owner","disabled-action"]) {
        check(`${key}-${side}-${mutation}`,()=>{
          const row=structuredClone(pair[side]),s=row.snapshot.interaction.content.surface;
          if(mutation==="missing-exit"){delete s.can_leave;delete s.can_proceed;}
          if(mutation==="contradictory-exit"){s.can_leave=vector.proceed;s.can_proceed=!vector.proceed;}
          if(mutation==="missing-enabled"){delete s.options[0].enabled;delete s.options[0].is_enabled;
            const p=row.snapshot.referents[0].properties;delete p.enabled;delete p.is_enabled;}
          if(mutation==="wrong-owner")s.options[0].entity_id="foreign";
          if(mutation==="disabled-action")row.snapshot.bound_actions.actions.push({
            bound_action_id:"foreign-disabled",interaction_id:row.snapshot.interaction.interaction_id,
            verb:"activate",label:"Unqualified",subject_referent_id:row.snapshot.referents[0].referent_id,arguments:[]});
          row.snapshot.bound_actions.total_count=row.snapshot.bound_actions.materialized_count=row.snapshot.bound_actions.actions.length;
          let rejected=false;try{inspect(row.snapshot,row.reads);}catch{rejected=true;}
          require(rejected,"Malformed rest authority admitted");
        });
      }
      check(`${key}-${side}-unknown-facts-retained`,()=>{
        const row=structuredClone(pair[side]);row.snapshot.interaction.content.surface.unfamiliar_public_fact=13;
        require(inspect(row.snapshot,row.reads).frame.public_input.context.interaction.content.surface.unfamiliar_public_fact===13,
          "Dropped unknown public fact");
      });
    }
  }
  // These remain explicitly artificial routing probes, with a real rest producer
  // replacing the former empty rest envelope. They do not grant effect coverage.
  for(const kind of [...POLICY,"game_over"].filter(kind=>kind!=="rest_site"))check(`routing-${kind}`,()=>{
    const row=fixture(kind);inspect(row.snapshot,row.reads);
  });
  for(const amount of [0,1,2,3])check(`counter-${amount}-preserved`,()=>{
    const row=fixture();row.snapshot.persistent.content.player.relics[0].counter=amount;
    require(inspect(row.snapshot,row.reads).frame.public_input.context.persistent.player.relics[0].counter===amount,
      "Aliased an actual public counter");
  });
  check("all-independent-differences-retained",()=>require(differences({a:1,b:2},{a:2,b:3}).length===2,"Stopped after first gap"));
  return results;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)
  for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
    let request;
    try {
      request=JSON.parse(line);
      const result=request.command==="generated"?{checks:generatedChecks(request.vectors)}:
        inspect(request.snapshot,request.reads);
      process.stdout.write(`${JSON.stringify({request_id:request.request_id,ok:true,...result})}\n`);
    }catch(error){process.stdout.write(`${JSON.stringify({request_id:request?.request_id,ok:false,error:error.message})}\n`);}
  }
