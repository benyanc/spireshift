import test from "node:test";
import assert from "node:assert/strict";
import { assertSameBuild, canonicalPatch } from "./engine-cli-local-build.mjs";
import { restAction } from "./probe-engine-cli-rest.mjs";

const identity = {
  artifact_sha256: "local-binary", artifact_mvid: "local-mvid", godot_stub_sha256: "stub",
  runtime_sts2_sha256: "game", reference_pack_id: "refs", source_diff_id: "source",
  runtime_dependencies_id: "dependencies"
};

test("repeat builds and frozen pins each refuse compiler, source, or binary drift", () => {
  assert.doesNotThrow(() => assertSameBuild(identity, { ...identity }, identity));
  for (const key of Object.keys(identity)) {
    assert.throws(() => assertSameBuild(identity, { ...identity, [key]: "changed" }, identity), /Fresh builds differ/u);
    assert.throws(() => assertSameBuild(identity, identity, { ...identity, [key]: "changed" }), /Local build pin changed/u);
  }
});

test("patch canonicalization ignores Git abbreviation but retains semantic and mode changes", () => {
  assert.equal(canonicalPatch("index abc..def\n+new\n"), canonicalPatch("index 1234..6789\r\n+new\r\n"));
  assert.notEqual(canonicalPatch("+new\n"), canonicalPatch("+changed\n"));
  assert.notEqual(canonicalPatch("old mode 100644\nnew mode 100755\n"), canonicalPatch(""));
});

test("rest binding uses the refreshed native object and its current index", () => {
  const state = { decision: "rest_site", room_ref: "room", options: [
    { option_id: "SMITH", native_ref: "smith", index: 0 }
  ] };
  assert.deepEqual(restAction(state, "SMITH").args,
    { room_ref: "room", option_index: 0, option_ref: "smith" });
  assert.throws(() => restAction(state, "HEAL"), /Missing bound rest choice/u);
  assert.throws(() => restAction({ ...state, room_ref: undefined }, "SMITH"), /Missing bound rest choice/u);
  assert.throws(() => restAction({ ...state, decision: "map_select" }, "SMITH"), /Missing bound rest choice/u);
});
