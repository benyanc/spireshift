import test from "node:test";
import assert from "node:assert/strict";
import {runtimeErrors} from "./engine-native-runtime-errors-v1.mjs";
test("native missing methods and asynchronous exceptions remain fatal",()=>{
  for(const line of ["[ERROR] Missing method", "System.MissingMethodException: GetIndex(Boolean)",
    "[WARN] Unobserved task exception: engine callback failed", "Unhandled exception: bad state"])
    assert.equal(runtimeErrors([{line}]).length,1);
});
test("startup information remains distinct from a runtime error",()=>{
  assert.deepEqual(runtimeErrors([{line:"[INFO] ModelDb: 1660 registered, 0 failed"},
    {line:"[WARN] No release metadata"}]),[]);
});
test("unrecognized ERROR lines cannot be whitelisted by the support fix",()=>{
  const row={line:"[ERROR] Future unknown effect failure"};
  assert.deepEqual(runtimeErrors([row]),[row]);
});
