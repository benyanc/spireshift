import test from "node:test";
import assert from "node:assert/strict";
import {executableSelection,ExecutableCardAnswerPlanner} from "./engine-executable-card-answer-v1.mjs";
import {directAnswers,cardAnswerDomain,answerControls} from "./engine-card-answer-v1.mjs";

function source(count=13) {
  return {type:"decision",decision:"card_select",selection_ref:"exact-owner",selection_owner:{kind:"shop"},
    cards:Array.from({length:count},(_,index)=>({index,native_ref:`copy-${index}`,id:"STRIKE",upgraded:false})),
    min_select:0,max_select:3,cancelable:false,require_manual_confirmation:true,unpowered_previews:false,
    pretend_cards_can_be_played:false,selection_preferences_complete:true,
    enchantment:{definition_id:"ADROIT",observation_source:"native_command_enchantment_and_amount"}};
}

test("direct enchant answers preserve every executable order and exclude the unfinishable empty choice",()=>{
  const raw=source(3),fixed=executableSelection(raw),domain=cardAnswerDomain(fixed),answers=directAnswers(domain);
  assert.equal(raw.min_select,0);assert.equal(fixed.min_select,1);assert.equal(answers.length,15);
  assert(answers.every(answer=>answer.length>0));
  assert(answers.some(answer=>JSON.stringify(answer)==="[0]"));
  assert(answers.some(answer=>JSON.stringify(answer)==="[2,1,0]"));
});

test("ordered planning cannot commit an empty enchant and still commits any legal nonempty prefix",()=>{
  const planner=new ExecutableCardAnswerPlanner(),view=planner.observe(source());
  const domain=cardAnswerDomain(view);
  assert.equal(answerControls(domain,[]).confirm,false);
  assert.throws(()=>planner.handle({cmd:"action",action:"ordered_answer_commit",
    args:{selection_ref:"exact-owner",prefix:""}}),/Unadvertised native answer completion/u);
  planner.handle({cmd:"action",action:"ordered_answer_append",args:{selection_ref:"exact-owner",prefix:"",index:12}});
  const committed=planner.handle({cmd:"action",action:"ordered_answer_commit",args:{selection_ref:"exact-owner",prefix:"12"}});
  assert.equal(committed.native.action,"select_cards");assert.equal(committed.native.args.indices,"12");
});

test("independently supported zero-card families and higher native minima remain unchanged",()=>{
  const raw=source();delete raw.enchantment;
  assert.equal(executableSelection(raw),raw);
  const higher={...source(),min_select:2};assert.equal(executableSelection(higher).min_select,2);
  const unknown=source();unknown.enchantment.observation_source="unqualified";
  assert.throws(()=>executableSelection(unknown),/qualified/u);
});
