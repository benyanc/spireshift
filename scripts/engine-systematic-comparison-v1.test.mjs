import assert from "node:assert/strict";
import test from "node:test";
import { generatedChecks, differences } from "./engine-systematic-comparison-v1.mjs";
import { chooseFixtureEntry } from "./engine-systematic-entry-v1.mjs";

// Test data for the checker. The audit separately consumes actual C# producer output.
const vectors=[];
for(const heal of [false,true])for(const smith of [false,true])for(const proceed of [false,true]) {
  const options=[{entity_id:"heal",index:0,option_id:"HEAL",name:"Rest",description:"Heal",enabled:heal},
    {entity_id:"smith",index:1,option_id:"SMITH",name:"Smith",description:"Upgrade",enabled:smith}];
  const commands=options.filter(row=>row.enabled).map(row=>({kind:"choose_rest_option",label:row.name,
    entity_bindings:[{role:"rest_option",entity_id:row.entity_id}]}));
  if(proceed)commands.push({kind:"proceed_rest_site",label:"Proceed to map",entity_bindings:[]});
  vectors.push({heal,smith,proceed,projection:{context:{kind:"rest"},
    surface:{kind:"rest_site",options,can_proceed:proceed}},commands});
}
for(const row of generatedChecks(vectors))test(row.key,()=>assert.equal(row.passed,true,row.error));
test("all independent fields differ even when one path is absent",()=>assert.deepEqual(
  differences({a:1,b:{x:2}},{a:2,b:{y:3}}),["/a","/b/x","/b/y"]));
test("save entry uses the actual current control and cannot start a new run",()=>{
  const action={label:"Continue the saved run",bound_action_id:"current"};
  const snapshot={interaction:{kind:"main_menu"},bound_actions:{actions:[action]}};
  assert.equal(chooseFixtureEntry(snapshot),action);
  assert.throws(()=>chooseFixtureEntry({...snapshot,bound_actions:{actions:[{label:"New run"}]}}));
  assert.throws(()=>chooseFixtureEntry({...snapshot,bound_actions:{actions:[action,action]}}));
});
