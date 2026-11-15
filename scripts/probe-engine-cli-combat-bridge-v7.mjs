// Privileged deck/potion/relic fixtures, followed by only bound player-visible actions.
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";
import { preparePlayerProjection } from "./engine-player-projection.mjs";
import { projectExactCombatSurface, projectExactCombatReads } from "./engine-combat-surface-v2.mjs";
import { combatFixtures, combatPlans, combatBridgeFacts, combatActionKey,
  chooseCombatBridgeAction, verifyCombatSignals } from "./engine-combat-bridge-contract-v7.mjs";

async function main(spec) {
  const gates={};let child;
  const result={status:"combat_bridge_projection_incomplete",gates,privileged_fixture:true,
    full_run_attempts:0,optimizer_steps:0,training_allowed:false,journey:[],receipts:[]};
  const check=(name,ok)=>{gates[name]=ok===true;if(ok!==true)throw Error(`Combat bridge gate failed: ${name}`);};
  try {
    const prepared=await preparePlayerProjection(spec);result.projection_identity=prepared.identity;
    const {startJsonLineProcess}=await import(pathToFileURL(path.join(spec.headless_root,"src/json-line-process.mjs")).href);
    const started=await startJsonLineProcess({command:"/usr/bin/sandbox-exec",
      args:["-f",path.join(spec.attempt,"profile-isolation.sb"),spec.dotnet,spec.artifact],cwd:spec.profile,
      env:{...process.env,STS2_LIB:path.join(spec.candidate,"lib"),STS2_GAME_DIR:spec.game_data},readyTimeoutMs:15000,diagnosticLimit:10000});
    child=started.process;
    const raw=async payload=>{
      if(["start_run","reset_run"].includes(payload.cmd))payload={...payload,content_policy:spec.content_policy};
      const response=await child.request(payload,15000);
      appendFileSync(path.join(spec.attempt,"private-transcript.jsonl"),`${JSON.stringify({request:payload,response})}\n`);
      return response;
    };
    const identity=await raw({cmd:"runtime_identity"});result.runtime_identity=identity;
    check("native_identity_bound",identity.process_id===child.pid && identity.host_assembly_sha256===spec.expected.artifact_sha256
      && identity.host_module_mvid===spec.expected.artifact_mvid && identity.sts2_assembly_sha256===spec.expected.runtime_sts2_sha256
      && identity.godot_stub_assembly_sha256===spec.expected.godot_stub_sha256 && identity.managed_runtime_version===spec.managed_runtime_version);
    const session=new prepared.module.ManagedPlayerEnvironmentSession({process:{request:raw},character:"Ironclad",ascension:8,
      runtimeInstanceId:`combat-bridge-${child.pid}`,environmentFingerprint:spec.environment_fingerprint,
      surfaceProjector:projectExactCombatSurface,readProjector:projectExactCombatReads,validateSdk:true});
    await session.mount({seed:spec.seed});
    const run=await raw({cmd:"run_identity"});
    check("native_benchmark_A8_seed_bound",run.active===true && run.seed===spec.seed && run.ascension===8
      && run.content_policy==="native_benchmark_full_v1" && run.native_unlock_run_count===999999999);
    const fixture=combatFixtures[spec.combat_bridge.scenario];
    if(!fixture)throw Error("Unknown finite combat fixture");
    const setup=await raw({cmd:"set_player",...fixture});
    check("native_fixture_setup_bound",setup.type==="ok" && setup.player.deck.length===fixture.deck.length
      && setup.player.potions.length===fixture.potions.length && setup.player.relics.some(r=>r.id==="PEN_NIB"));
    // This is a native read after setup, not a merge into a stale initial observation.
    const observed=await raw({cmd:"observe"});
    let snapshot=await session.acceptNativeObservation(observed);
    check("native_initial_ancient",snapshot.interaction.kind==="event_option" && snapshot.persistent.content.run.floor===1);
    const save=path.join(spec.attempt,"native-checkpoint.save"),profile=path.join(spec.attempt,"benchmark-progress.save");
    const exported=await raw({cmd:"benchmark_profile",path:profile});
    check("benchmark_progress_export",exported.type==="benchmark_profile" && hashFile(profile)===spec.profile_progress_sha256);
    const saved=await raw({cmd:"write_continue_save",path:save,preserve_current_room:true});
    check("native_fixture_save",saved.success===true && saved.room_type==="EventRoom" && JSON.parse(readFileSync(save,"utf8")).ascension===8);
    result.checkpoint={path:save,sha256:hashFile(save),ascension:8,seed:spec.seed,
      content_policy:"native_benchmark_full_v1",privileged_fixture:true,public_setup_actions:0,
      fixture_mutations:["five_card_native_deck","two_assigned_potions","native_obtained_pen_nib"]};
    result.benchmark_progress_sha256=hashFile(profile);
    writeFileSync(path.join(spec.attempt,"private-starting-snapshot.json"),JSON.stringify(snapshot));
    const plan=combatPlans[spec.combat_bridge.scenario];let operation=0,eventChosen=false,combatStarted=false;
    for(let i=0;i<=spec.combat_bridge.max_actions;i++) {
      const descriptor=snapshot.reads.find(row=>row.kind==="run_deck");
      const deckRead=session.read({readId:descriptor?.read_id,expectedSnapshotId:snapshot.snapshot_id});
      const serialized=JSON.stringify({snapshot,deckRead});
      check(`snapshot_${i}_public_boundary`,!/"(?:native_ref|room_ref|option_ref|selection_ref|raw_request|seed|rng|draw_order|act_sequence)"/u.test(serialized));
      appendFileSync(path.join(spec.attempt,"private-combat-snapshots.jsonl"),`${serialized}\n`);
      const row={facts:combatBridgeFacts(snapshot,deckRead),action:null};result.journey.push(row);
      if(snapshot.interaction.kind==="combat_turn")combatStarted=true;
      if(combatStarted && operation===plan.length)break;
      if(i===spec.combat_bridge.max_actions)throw Error("Finite combat prefix cap reached");
      const action=chooseCombatBridgeAction(snapshot,{startingOption:eventChosen?null:spec.combat_bridge.starting_option,
        operation:snapshot.interaction.kind==="combat_turn"?plan[operation]:null});
      row.action=combatActionKey(snapshot,action);
      if(snapshot.interaction.kind==="event_option" && row.action.subject!=null)eventChosen=true;
      if(snapshot.interaction.kind==="combat_turn")operation++;
      const receipt=await session.submit({requestId:`combat-bridge-${i}`,expectedSnapshotId:snapshot.snapshot_id,
        boundActionId:action.bound_action_id,timeoutMs:15000});
      result.receipts.push(receipt);
      check(`action_${i}_delivered`,receipt.delivery==="delivered");snapshot=receipt.successor;
    }
    check("declared_combat_operations_complete",operation===plan.length);
    result.effect_checks=verifyCombatSignals(result.journey,spec.combat_bridge.scenario);
    result.public_actions_delivered=result.journey.length-1;
    await raw({cmd:"quit"});result.exit=await child.exit;check("natural_exit",result.exit.code===0 && result.exit.signal===null);
    result.status="combat_bridge_public_projection_regression_pass";
  } catch(error){result.error=error.message;}
  finally {
    if(child){result.exit??=await child.stop({timeoutMs:2000});
      writeFileSync(path.join(spec.attempt,"diagnostics.json"),JSON.stringify(child.diagnostics));}
    writeFileSync(path.join(spec.attempt,"combat_bridge-probe.json"),`${JSON.stringify(result,null,2)}\n`);
  }
  console.log(JSON.stringify({status:result.status,error:result.error??null}));
  if(result.status!=="combat_bridge_public_projection_regression_pass")process.exitCode=1;
}
if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href) {
  let input="";for await(const chunk of process.stdin)input+=chunk.toString();await main(JSON.parse(input));
}
