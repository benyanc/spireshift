// Streaming replay: a local prefix cannot masquerade as a native commit.
import { createReadStream, existsSync, readFileSync } from "node:fs";
import { createGunzip } from "node:zlib";
import { createInterface } from "node:readline";
import path from "node:path";
import assert from "node:assert/strict";
import { SelectionCursor } from "./engine-selection-cursor-v1.mjs";
async function* rows(file) {
  if (!existsSync(file)) return;
  const lines=createInterface({input:createReadStream(file).pipe(createGunzip()),crlfDelay:Infinity});
  for await(const line of lines)yield JSON.parse(line);
}
const w=process.argv[2], cursor=new SelectionCursor(), ui=rows(path.join(w,"selection-cursor.jsonl.gz"));
let local_steps=0, native_commits=0, native_cancels=0, ui_commands=0;
for await(const row of rows(path.join(w,"private-transcript.jsonl.gz"))) {
  const request=row.request;
  if(row.transport==="local_selection_ui" || cursor.active && request.cmd==="action") {
    const item=(await ui.next()).value;assert.ok(item,"Missing selection UI record");ui_commands++;
    const replay=cursor.handle(item.request);assert.ok(replay,"Unrecognized selection UI request");
    assert.deepEqual(replay,item.local ? {local:item.local,response:item.response,before:item.before,after:item.after}
      : {local:item.local,native:item.native,before:item.before,after:item.after});
    if(row.transport==="local_selection_ui") {
      assert.equal(replay.local,true);assert.deepEqual(request,item.request);assert.deepEqual(row.response,replay.response);local_steps++;
    } else {
      assert.equal(replay.local,false);assert.deepEqual(request,replay.native);
      if(request.action==="select_cards")native_commits++;else native_cancels++;
      cursor.observe(row.response);
    }
  } else {
    assert.ok(!String(request.action).startsWith("selection_cursor_"));cursor.observe(row.response);
  }
}
assert.equal((await ui.next()).done,true,"Unbound selection UI suffix");
if(existsSync(path.join(w,"closed.json")))assert.equal(cursor.active,null,"Closed worker left an uncommitted native selection");
console.log(JSON.stringify({ui_commands,local_steps,native_commits,native_cancels,ordered_stream_replay:true}));
