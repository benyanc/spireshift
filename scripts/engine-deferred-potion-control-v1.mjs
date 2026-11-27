// Isolated controls only. The production learner has no prepare or raw-probe command.
import {createInterface} from "node:readline";
import {appendFileSync} from "node:fs";
import path from "node:path";
import {NativeWorker} from "./engine-native-worker-v24.mjs";
import {InventoryLifecycleWorker} from "./engine-inventory-lifecycle-worker-v1.mjs";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {projectSelectionFlows,selectionFlowReads} from "./engine-merchant-overlay-surface-v1.mjs";

class QueueControl extends InventoryLifecycleWorker {
  async raw(request) {return NativeWorker.prototype.raw.call(this,request);}
  async initialize(spec) {
    if(spec.lifecycle_fixture!==true)throw Error("Require a disposable queue diagnostic");
    const result=await super.initialize(spec);
    if(result.initial_identity.potion_queue_adapter_sha256!==spec.lifecycle_adapter.sha256 || result.initial_identity.deferred_potions_adapter_sha256!==spec.lifecycle_adapter.sha256)
      throw Error("The exact queue adapter did not initialize");
    const Session=Object.getPrototypeOf(this.prepared.module.ManagedPlayerEnvironmentSession);
    this.prepared={...this.prepared,module:{...this.prepared.module,
      ManagedPlayerEnvironmentSession:class extends Session {
        constructor(options){super({...options,surfaceProjector:projectSelectionFlows,readProjector:selectionFlowReads});}
      }}};
    this.cursor=new ExecutableCardAnswerPlanner();
    return result;
  }
  async prepare(case_) {
    if(this.session)throw Error("Never reuse a queue-control world");
    await this.mount(case_.seed);
    await this.raw({cmd:"set_player",max_hp:80,hp:50,
      deck:["STAMPEDE","HEADBUTT","DEFEND_IRONCLAD","BLOODLETTING"],potions:["BLOOD_POTION","SPEED_POTION"]});
    if(case_.opening)await this.raw({cmd:"set_player",obtain_relics:["TOOLBOX"]});
    const state=case_.combat?await this.raw({cmd:"enter_room",type:"combat",encounter:"SPINY_TOAD_NORMAL"}):await this.raw({cmd:"observe"});
    this.snapshot=await this.session.acceptNativeObservation(state,15000);
    return this.observe();
  }
  async inspectBuffer() {return this.raw({cmd:"run_identity"});}
  async rejectDuplicate() {
    const before=await this.raw({cmd:"observe"});
    const player=before.selection_combat?.player??before.player;
    const bottle=player.potions.find(p=>p.id==="SPEED_POTION");
    if(!bottle || bottle.can_discard!==false)throw Error("Missing tracked deferred discard");
    for(const stale of [false,true]) {
      const request={cmd:"action",action:"discard_potion",args:{potion_slot:stale?0:bottle.slot,potion_ref:bottle.native_ref}};
      const response=await this.child.request(request,15000);
      appendFileSync(path.join(this.spec.attempt,"private-transcript.jsonl"),JSON.stringify({request,response})+"\n");
      const expected=stale?"The observed potion is no longer in the bound belt slot":"no longer natively discardable";
      if(response.type!=="error" || !response.message.includes(expected))throw Error("Duplicate or stale deferred discard accepted");
    }
    const after=await this.raw({cmd:"observe"});
    if(JSON.stringify(before)!==JSON.stringify(after))throw Error("Rejected deferred requests changed state");
    return {rejected:2,state_unchanged:true};
  }
  async guardedProbe() {
    const before=await this.raw({cmd:"observe"});
    const p=before.player.potions[0];
    if(p.can_discard!==false)throw Error("Guard probe requires a natively disallowed queue");
    for(const action of ["discard_potion","use_potion"]) {
      const request={cmd:"action",action,args:{potion_slot:p.slot,potion_ref:p.native_ref}};
      const result=await this.child.request(request,15000);
      appendFileSync(path.join(this.spec.attempt,"private-transcript.jsonl"),JSON.stringify({request,response:result})+"\n");
      if(result.type!=="error" || result.message!=="Potion action is not accepted by the current native queue")
        throw Error("An invalid potion request was not rejected before native enqueue");
    }
    const after=await this.raw({cmd:"observe"});
    if(JSON.stringify(before)!==JSON.stringify(after))throw Error("Rejected requests changed native state");
    return {requests_rejected_before_enqueue:2,native_state_unchanged:true};
  }
}
const worker=new QueueControl();
try {
  for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
    let request;
    try {
      request=JSON.parse(line);let value;
      if(request.command==="initialize")value=await worker.initialize(request.spec);
      else if(request.command==="prepare")value=await worker.prepare(request.case);
      else if(request.command==="step")value=await worker.step(request);
      else if(request.command==="inspect_buffer")value=await worker.inspectBuffer();
      else if(request.command==="reject_duplicate")value=await worker.rejectDuplicate();
      else if(request.command==="guarded_probe")value=await worker.guardedProbe();
      else if(request.command==="close")value=await worker.close();
      else throw Error("Undeclared queue control operation");
      console.log(JSON.stringify({request_id:request.request_id,ok:true,value}));
      if(request.command==="close"){process.stdin.destroy();break;}
    }catch(error){console.log(JSON.stringify({request_id:request?.request_id,ok:false,error:error.message}));process.exitCode=1;break;}
  }
}finally{if(worker.child&&!worker.closed)await worker.stop();}
