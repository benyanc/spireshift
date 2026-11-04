// Privileged save setup only. Never ordinary learning/evaluation experience.
import { NativeWorker } from "./engine-native-worker-v24.mjs";
import { createInterface } from "node:readline";
import path from "node:path";
import { readFileSync, writeFileSync } from "node:fs";
import { preparePotionSave } from "./engine-lifecycle-fixture-save-v1.mjs";
import { newDiagnosticNavigation } from "./engine-run-policy-v7.mjs";
import { projectSelectionFlows, selectionFlowReads } from "./engine-chest-surface-v1.mjs";
const worker=new NativeWorker();
try {
  for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
    let request;
    try {
      request=JSON.parse(line);let value;
      if(request.command==="initialize") {
        if(request.spec.coverage_diagnostic!==true)throw Error("Diagnostic-only entry point");
        value=await worker.initialize(request.spec);
      } else if(request.command==="prepare") {
        await worker.mount(request.seed);
        await worker.raw({cmd:"coverage_fixture",fixture:{card_id:"DRAMATIC_ENTRANCE",upgrade:1,copies:5,funded:false}});
        await worker.raw({cmd:"set_player",max_hp:80,hp:48,gold:0,potions:["BLOOD_POTION"],obtain_relics:["BAG_OF_MARBLES","AKABEKO","VAJRA"]});
        const file=path.join(worker.spec.profile,"diagnostic-current-run.save");
        const save=await worker.raw({cmd:"write_continue_save",path:file,preserve_current_room:true});
        if(save.success!==true)throw Error("Native save setup failed");
        const prepared=path.join(worker.spec.profile,"diagnostic-potion-combat.save");
        writeFileSync(prepared,JSON.stringify(preparePotionSave(JSON.parse(readFileSync(file,"utf8")))));
        const fixtureSave={...save,path:prepared};
        value={save:fixtureSave,native_save:save,privileged_fixture:true,training_allowed:false};
      } else if(request.command==="load") {
        if(worker.session)throw Error("Load a diagnostic save only into a fresh native process");
        worker.navigation=newDiagnosticNavigation();worker.index=0;
        let pending=true;
        worker.session=new worker.prepared.module.ManagedPlayerEnvironmentSession({
          process:{request:payload=>{
            if(payload.cmd==="start_run") {
              if(!pending)throw Error("Diagnostic load cannot be retried");pending=false;
              return worker.raw({cmd:"load_save",json:request.save_json});
            }
            return worker.raw(payload);
          }},character:"Ironclad",ascension:8,runtimeInstanceId:worker.runtimeId,
          environmentFingerprint:worker.spec.environment_fingerprint,
          surfaceProjector:projectSelectionFlows,readProjector:selectionFlowReads,validateSdk:true});
        worker.snapshot=await worker.session.mount({seed:request.seed});
        const identity=await worker.raw({cmd:"run_identity"});
        if(!identity.active||identity.seed!==request.seed||identity.ascension!==8)
          throw Error("Wrong native diagnostic save identity");
        worker.episodes++;value={...await worker.observe(),privileged_fixture:true};
      } else if(request.command==="mount")value=await worker.mount(request.seed);
      else if(request.command==="step")value=await worker.step(request);
      else if(request.command==="close")value=await worker.close();
      else throw Error("Undeclared diagnostic command");
      console.log(JSON.stringify({request_id:request.request_id,ok:true,value}));
      if(request.command==="close"){process.stdin.destroy();break;}
    }catch(error){console.log(JSON.stringify({request_id:request?.request_id,ok:false,error:error.message}));process.exitCode=1;break;}
  }
}finally{await worker.stop();}
