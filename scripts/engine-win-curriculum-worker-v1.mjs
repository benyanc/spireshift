// Separate curriculum constructor; unchanged CLI56 / worker24 / converter16.
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { projectSelectionFlows, selectionFlowReads } from "./engine-chest-surface-v1.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { createInterface } from "node:readline";
import { readFileSync } from "node:fs";
import path from "node:path";
const worker=new NativeWorker();
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
