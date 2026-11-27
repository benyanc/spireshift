// Separate curriculum constructor; unchanged CLI56 / worker24 / converter16.
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { projectSelectionFlows, selectionFlowReads } from "./engine-reward-belt-surface-v1.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { createInterface } from "node:readline";
import { readFileSync } from "node:fs";
import path from "node:path";
class CurriculumWorker extends NativeWorker {
  async mount(seed) {
    if(this.closed || (this.snapshot && !this.facts.terminal))throw Error("Worker cannot abandon an unfinished episode");
    if(!/^[A-Z0-9]+$/u.test(seed))throw Error("Use a native canonical seed");
    this.navigation=newDiagnosticNavigation();this.index=0;
    this.session=new this.prepared.module.ManagedPlayerEnvironmentSession({process:{request:p=>this.raw(p)},
      character:"Ironclad",ascension:8,runtimeInstanceId:this.runtimeId,
      environmentFingerprint:this.spec.environment_fingerprint,
      surfaceProjector:projectSelectionFlows,readProjector:selectionFlowReads,validateSdk:true});
    this.snapshot=await this.session.mount({seed,reset:this.episodes>0});
    const identity=await this.raw({cmd:"run_identity"});
    if(!identity.active || identity.seed!==seed || identity.ascension!==8
      || identity.content_policy!==this.spec.content_policy || identity.native_unlock_run_count!==999999999
      || identity.started_with_neow!==true || identity.native_game_over || identity.native_player_dead)
      throw Error("Native reset/start has the wrong profile, seed or ending state");
    this.episodes++;return {...await this.observe(),private_start_identity:identity,
      native_process_id:this.child.pid,episode:this.episodes,reset:this.episodes>1};
  }
}
const worker=new CurriculumWorker();
try {
  for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})){
    let request;
    try {
      request=JSON.parse(line);let value;
      if(request.command==="initialize"){
        if(request.spec.win_curriculum!==true)throw Error("Separate curriculum scope required");
        value=await worker.initialize(request.spec);
      }else if(request.command==="seed_save"){
        if(worker.session)throw Error("Never reuse a curriculum preparation process");
        await worker.mount(request.seed);
        await worker.raw({cmd:"coverage_fixture",fixture:{room:"combat",relics:[]}});
        const p=request.profile;
        await worker.raw({cmd:"set_player",hp:p.hp,max_hp:p.max_hp,gold:p.gold,deck:p.deck,
          relics:[],obtain_relics:p.relics,potions:p.potions});
        const file=path.join(worker.spec.profile,"curriculum-seed.save");
        const result=await worker.raw({cmd:"write_continue_save",path:file,preserve_current_room:true});
        if(result.success!==true)throw Error("Native curriculum save failed");
        value={save:JSON.parse(readFileSync(file,"utf8")),privileged_setup:true};
      }else if(request.command==="load"){
        if(worker.session)throw Error("Load only in a fresh isolated native process");
        worker.navigation=newDiagnosticNavigation();worker.index=0;let pending=true;
        worker.session=new worker.prepared.module.ManagedPlayerEnvironmentSession({
          process:{request:payload=>{
            if(payload.cmd==="start_run"){
              if(!pending)throw Error("Curriculum load cannot be retried");pending=false;
              return worker.raw({cmd:"load_save",json:request.save_json});
            }return worker.raw(payload);
          }},character:"Ironclad",ascension:8,runtimeInstanceId:worker.runtimeId,
          environmentFingerprint:worker.spec.environment_fingerprint,
          surfaceProjector:projectSelectionFlows,readProjector:selectionFlowReads,validateSdk:true});
        worker.snapshot=await worker.session.mount({seed:request.seed});
        const identity=await worker.raw({cmd:"run_identity"});
        if(!identity.active || identity.seed!==request.seed || identity.ascension!==8)
          throw Error("Curriculum loaded the wrong native world/difficulty");
        worker.episodes++;value={...await worker.observe(),private_setup_identity:identity};
      }else if(request.command==="save_current"){
        const file=path.join(worker.spec.profile,"curriculum-current-act.save");
        const result=await worker.raw({cmd:"write_continue_save",path:file,preserve_current_room:true});
        if(result.success!==true)throw Error("Native staged save failed");
        value={save:JSON.parse(readFileSync(file,"utf8")),privileged_setup:true};
      }else if(request.command==="mount")value=await worker.mount(request.seed);
      else if(request.command==="step")value=await worker.step(request);
      else if(request.command==="ending")value=await worker.ending();
      else if(request.command==="close")value=await worker.close();
      else throw Error("Undeclared curriculum operation");
      console.log(JSON.stringify({request_id:request.request_id,ok:true,value}));
      if(request.command==="close"){process.stdin.destroy();break;}
    }catch(error){console.log(JSON.stringify({request_id:request?.request_id,ok:false,error:error.message}));process.exitCode=1;break;}
  }
}finally{await worker.stop();}
