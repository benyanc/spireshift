import assert from "node:assert/strict";
import test from "node:test";
import { startingOptions } from "./engine-checkpoint-shipped-probe.mjs";

const snapshot = (options, kind = "event_option") => ({
  interaction: { kind, content: { surface: { options } } }
});

test("starting comparison uses visible titles and availability, excluding runtime IDs and internal text keys", () => {
  const managed = snapshot([{ title: "Example", is_locked: false, text_key: "PRIVATE_KEY", entity_id: "managed" }]);
  const shipped = snapshot([{ title: "Example", is_locked: false, entity_id: "shipped", index: 0 }]);
  assert.deepEqual(startingOptions(managed), startingOptions(shipped));
  assert.deepEqual(startingOptions(managed), [{ title: "Example", is_locked: false }]);
});

test("changed offered choices, order or availability remain different", () => {
  const first = snapshot([{ title: "First", is_locked: false }, { title: "Second", is_locked: false }]);
  const changes = [
    [{ title: "Third", is_locked: false }, { title: "Second", is_locked: false }],
    [{ title: "Second", is_locked: false }, { title: "First", is_locked: false }],
    [{ title: "First", is_locked: true }, { title: "Second", is_locked: false }]
  ];
  for (const options of changes) assert.notDeepEqual(startingOptions(first), startingOptions(snapshot(options)));
});

test("missing or ambiguous titles and availability cannot produce an apparent comparison pass", () => {
  for (const options of [[], null, [null], [{}], [{ title: "Example" }],
    [{ title: "", is_locked: false }], [{ title: "Example", is_locked: "false" }]]) {
    assert.equal(startingOptions(snapshot(options)), null);
  }
  assert.equal(startingOptions(snapshot([{ title: "Example", is_locked: false }], "main_menu")), null);
});

test("explicit enabled flags may be translated without guessing absent availability", () => {
  assert.deepEqual(startingOptions(snapshot([{ label: "Example", enabled: false }])),
    [{ title: "Example", is_locked: true }]);
});
