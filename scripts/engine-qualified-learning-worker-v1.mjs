// Production learning exposes no fixture, save-load or scripted-choice command.
import {createInterface} from "node:readline";
import path from "node:path";
import {pathToFileURL} from "node:url";
import {NativeWorker} from "./engine-native-worker-v24.mjs";
import {InventoryLifecycleWorker} from "./engine-inventory-lifecycle-worker-v1.mjs";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {projectSelectionFlows,selectionFlowReads} from "./engine-merchant-overlay-surface-v1.mjs";

export const LEARNING_CONTRACT="qualified_full_menu_model_owned_normal_start_v1";
export function requireLearningSpec(spec) {
  if(spec.qualified_learning_contract!==LEARNING_CONTRACT || spec.lifecycle_fixture!==false
    || spec.selector_fixture!==false || spec.mixed_handoff_fixture===true)
    throw Error("Require the normal-start learner without fixture capabilities");
}

export class QualifiedLearningWorker extends InventoryLifecycleWorker {
  // The old refresh helper removed a still-valid merchant target under the map.
  // Target eligibility now comes from the qualified current-room adapter.
  async raw(request) {return NativeWorker.prototype.raw.call(this,request);}
  async initialize(spec) {
    requireLearningSpec(spec);
    const result=await super.initialize(spec);
    if(result.initial_identity.merchant_overlay_adapter_sha256!==spec.lifecycle_adapter.sha256)
      throw Error("Require the paired-qualified merchant overlay adapter");
    const Session=Object.getPrototypeOf(this.prepared.module.ManagedPlayerEnvironmentSession);
    if(!["mount","acceptNativeObservation","read"].every(name=>typeof Session.prototype[name]==="function"))
      throw Error("Unexpected immutable SDK session lineage");
    this.prepared={...this.prepared,module:{...this.prepared.module,
      ManagedPlayerEnvironmentSession:class extends Session {
        constructor(options) {super({...options,surfaceProjector:projectSelectionFlows,readProjector:selectionFlowReads});}
      }}};
    this.cursor=new ExecutableCardAnswerPlanner();
    return {...result,qualified_learning_contract:LEARNING_CONTRACT,fixture_commands_available:false};
  }
}

if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
  const worker=new QualifiedLearningWorker();
  try {
    for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
      let request;
      try {
        request=JSON.parse(line);
        let value;
        if(request.command==="initialize")value=await worker.initialize(request.spec);
        else if(request.command==="mount")value=await worker.mount(request.seed);
        else if(request.command==="step")value=await worker.step(request);
        else if(request.command==="ending")value=await worker.ending();
        else if(request.command==="close")value=await worker.close();
        else throw Error("Only normal-start learning requests are supported");
        console.log(JSON.stringify({request_id:request.request_id,ok:true,value}));
        if(request.command==="close") {process.stdin.destroy();break;}
      } catch(error) {
        console.log(JSON.stringify({request_id:request?.request_id,ok:false,error:error.message}));
        process.exitCode=1;break;
      }
    }
  } finally {if(worker.child && !worker.closed)await worker.stop();}
}
