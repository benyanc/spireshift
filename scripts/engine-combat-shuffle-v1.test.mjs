import assert from "node:assert/strict";
import test from "node:test";
import { shuffleTutorialAction } from "./engine-combat-shuffle-v1.mjs";

function sample() {
  const action={bound_action_id:"a",interaction_id:"i",verb:"activate",subject_referent_id:null,arguments:[],label:"OK"};
  return {status:"interactive",session:{runtime_instance_id:"r"},snapshot_id:"s",completeness:{status:"complete"},information_policy:{includes_hidden_information:false},
    bound_actions:{status:"complete",actions:[action],total_count:1,materialized_count:1},
    interaction:{kind:"tutorial",interaction_id:"i",content:{surface:{tutorial_id:"shuffle_ftue",stage:"confirmation",title:"Shuffle",body:"Your discard pile is shuffled into the draw pile.",current_page:null,total_pages:null,
      options:[{semantic_id:"dismiss_tutorial",label:"OK",enabled:true}]},context:{kind:"combat",round:2,is_play_phase:false,player:{hand:[],draw_pile_count:0,discard_pile_count:2}}}}};
}
test("only the exact enabled pending-draw tutorial offers confirmation",()=>{
  const snapshot=sample();assert.equal(shuffleTutorialAction(snapshot),snapshot.bound_actions.actions[0]);
});
for(const [name,mutate] of [
  ["another modal",s=>s.interaction.content.surface.tutorial_id="other"],
  ["disabled button",s=>s.interaction.content.surface.options[0].enabled=false],
  ["different round",s=>s.interaction.content.context.round=1],
  ["active player phase",s=>s.interaction.content.context.is_play_phase=true],
  ["draw already completed",s=>s.interaction.content.context.player.hand=[{}]],
  ["empty discard",s=>s.interaction.content.context.player.discard_pile_count=0],
  ["extra control",s=>s.bound_actions.actions.push({...s.bound_actions.actions[0],bound_action_id:"b"})],
  ["stale interaction",s=>s.bound_actions.actions[0].interaction_id="old"],
  ["hidden context",s=>s.information_policy.includes_hidden_information=true],
]) test(`refuse ${name}`,()=>{const snapshot=sample();mutate(snapshot);assert.throws(()=>shuffleTutorialAction(snapshot),/Unqualified/);});
