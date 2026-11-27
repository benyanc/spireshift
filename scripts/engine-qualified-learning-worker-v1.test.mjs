import test from "node:test";
import assert from "node:assert/strict";
import {LEARNING_CONTRACT,requireLearningSpec} from "./engine-qualified-learning-worker-v1.mjs";

test("production model-owned play requires a normal-start-only capability declaration",()=>{
  const spec={qualified_learning_contract:LEARNING_CONTRACT,lifecycle_fixture:false,selector_fixture:false};
  assert.doesNotThrow(()=>requireLearningSpec(spec));
  for(const edit of [s=>s.lifecycle_fixture=true,s=>s.selector_fixture=true,
    s=>s.mixed_handoff_fixture=true,s=>delete s.lifecycle_fixture,
    s=>s.qualified_learning_contract="diagnostic"]) {
    const invalid={...spec};edit(invalid);
    assert.throws(()=>requireLearningSpec(invalid),/without fixture capabilities/u);
  }
});
