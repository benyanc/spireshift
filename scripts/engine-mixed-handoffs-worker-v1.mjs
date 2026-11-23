// Privileged serialized states; all subsequent effects use normal public actions.
import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import path from "node:path";
import {createInterface} from "node:readline";
import {InventoryLifecycleWorker} from "./engine-inventory-lifecycle-worker-v1.mjs";
import {ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {mixedFixture} from "./engine-mixed-handoff-fixtures-v1.mjs";

class MixedWorker extends InventoryLifecycleWorker {
  async initialize(spec) {
    const result=await super.initialize(spec);
    if (spec.mixed_handoff_fixture!==true) throw Error("Require the declared mixed fixture worker");
    this.cursor=new ExecutableCardAnswerPlanner();
    return {...result,mixed_fixture_contract:"native_mixed_handoffs_v1"};
  }
  async prepare(case_) {
    if (!this.spec.lifecycle_fixture || this.session) throw Error("Require a fresh private fixture");
    await this.mount(case_.seed);
    await this.raw({cmd:"set_player",max_hp:80,hp:case_.hp,gold:1000,
      deck:case_.deck,potions:case_.belt,obtain_relics:case_.relics});
    const file=path.join(this.spec.profile,"mixed-handoff-source.save");
    const written=await this.raw({cmd:"write_continue_save",path:file,preserve_current_room:true});
    if (written.success!==true) throw Error("Native mixed fixture save failed");
    const bytes=readFileSync(file);
    return {save:mixedFixture(JSON.parse(bytes),case_),original_save_sha256:createHash("sha256").update(bytes).digest("hex"),
      privileged_fixture:true,training_allowed:false};
  }
}

const worker=new MixedWorker();
try {
  for await (const line of createInterface({input:process.stdin,crlfDelay:Infinity})) {
    let request;
    try {
      request=JSON.parse(line);
      let value;
      if (request.command==="initialize") value=await worker.initialize(request.spec);
      else if (request.command==="prepare") value=await worker.prepare(request.case);
      else if (request.command==="load") value=await worker.mount(request.seed,request.save_json);
      else if (request.command==="step") value=await worker.step(request);
      else if (request.command==="inspect") value=await worker.raw({cmd:"run_identity"});
      else if (request.command==="close") value=await worker.close();
      else throw Error("Undeclared mixed handoff request");
      console.log(JSON.stringify({request_id:request.request_id,ok:true,value}));
      if (request.command==="close") {process.stdin.destroy();break;}
    } catch (error) {
      console.log(JSON.stringify({request_id:request?.request_id,ok:false,error:error.message}));
      process.exitCode=1;break;
    }
  }
} finally {if (worker.child && !worker.closed) await worker.stop();}
