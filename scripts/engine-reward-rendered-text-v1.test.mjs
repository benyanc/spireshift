import assert from "node:assert/strict";
import test from "node:test";
import { renderedRewardText, renderNativeRewardState } from "./engine-reward-rendered-text-v1.mjs";
test("only gold markup is removed; mechanics, numbers and their relationships remain distinct",()=>{
  assert.equal(renderedRewardText("Gain [gold]2[/gold] Strength and [gold]7[/gold] Dexterity."),"Gain 2 Strength and 7 Dexterity.");
  assert.notEqual(renderedRewardText("Gain [gold]2[/gold] Strength and [gold]7[/gold] Dexterity."),
    renderedRewardText("Gain [gold]7[/gold] Strength and [gold]2[/gold] Dexterity."));
  assert.equal(renderedRewardText("[unknown]gain 7[/unknown]\nLose 2."),"[unknown]gain 7[/unknown]\nLose 2.");
  assert.equal(renderedRewardText(null),null);
});
test("rendering leaves instance bindings, availability, other state and original raw evidence intact",()=>{
  const source={decision:"reward_set",rewards:[{native_ref:"PRIVATE_INSTANCE",description:"[gold]Potions[/gold] appear.",value:"MODEL_A"}],player:{gold:12}};
  const before=structuredClone(source), after=renderNativeRewardState(source);
  assert.deepEqual(source,before); assert.equal(after.rewards[0].native_ref,"PRIVATE_INSTANCE");
  assert.equal(after.rewards[0].value,"MODEL_A"); assert.deepEqual(after.player,before.player);
  assert.equal(after.rewards[0].description,"Potions appear.");
  const other={decision:"event_choice"}; assert.equal(renderNativeRewardState(other),other);
});
