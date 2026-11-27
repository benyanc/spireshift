import assert from "node:assert/strict";
import test from "node:test";
import { rewardTutorialAction, verifyRewardTutorial } from "./engine-reward-tutorial-v2.mjs";
const snapshot=(id,kind)=>({snapshot_id:id,status:"interactive",session:{runtime_instance_id:"runtime"},
  information_policy:{includes_hidden_information:false},completeness:{status:"complete"},
  interaction:{kind,content:{surface:{tutorial_id:"obtain_relic_ftue",stage:"confirmation",title:"Synthetic tutorial",
    body:"Synthetic visible text",options:[{semantic_id:"dismiss_tutorial",label:"Continue",enabled:true}]}}},
  bound_actions:{status:"complete",total_count:1,materialized_count:1,actions:[{bound_action_id:id,verb:"activate",label:"Continue",arguments:[],subject_referent_id:null}]},
  persistent:{content:{run:{act:1,act_definition_id:"SYNTHETIC_ACT",floor:1,ascension:8},
    player:{character_definition_id:"IRONCLAD",hp:64,max_hp:80,gold:1000,max_potion_slots:2,relics:[],potions:[]}}}});
const deck=(id)=>({kind:"run_deck",expected_snapshot_id:id,observed_snapshot_id:id,completeness:{status:"complete"},
  information_policy:{includes_hidden_information:false},ordering_semantics:"unordered_multiset",content:{kind:"run_deck",card_count:0,cards:[]}});
test("only the exact enabled current relic/potion confirmation is accepted",()=>{
  for(const id of ["obtain_relic_ftue","obtain_potion_ftue"]) {
    const before=snapshot("before","tutorial"); before.interaction.content.surface.tutorial_id=id;
    assert.equal(rewardTutorialAction(before,id).bound_action_id,"before");
    assert.equal(verifyRewardTutorial(before,deck("before"),snapshot("after","reward_claim"),deck("after"),id),true);
  }
  const before=snapshot("before","tutorial");
  assert.throws(()=>rewardTutorialAction(before,"unknown_ftue"));
  assert.throws(()=>rewardTutorialAction(before,"obtain_potion_ftue"));
  before.interaction.content.surface.options[0].enabled=false;
  assert.throws(()=>rewardTutorialAction(before,"obtain_relic_ftue"));
});
test("tutorial dismissal cannot hide changed ownership, capacity, owner or snapshot identity",()=>{
  const before=snapshot("before","tutorial");
  for(const change of [(row)=>{row.persistent.content.player.gold++;},
    (row)=>{row.persistent.content.player.max_potion_slots++;},
    (row)=>{row.interaction.kind="shop_inventory";},(row)=>{row.snapshot_id="before";},
    (row)=>{row.session.runtime_instance_id="other";}]) {
    const after=snapshot("after","reward_claim"); change(after);
    assert.throws(()=>verifyRewardTutorial(before,deck("before"),after,deck(after.snapshot_id),"obtain_relic_ftue"));
  }
});
