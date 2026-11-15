// Typed public layout normalization, not game-rule emulation. Unknown facts stay.
// The reversible journal is evidence outside the learner input.
import { createHash } from "node:crypto";
import { stableJson } from "./engine-public-input-v1.mjs";
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";

export const LAYOUT = "typed_official_public_layout_v7";
const object = v => v !== null && typeof v === "object" && !Array.isArray(v);
const same = (a,b) => stableJson(a) === stableJson(b);
// Treat inputs as JSON trees; shared in-memory references must not relabel twice.
const clone = v => JSON.parse(stableJson(v));
const hash = v => createHash("sha256").update(stableJson(v)).digest("hex");
const esc = v => String(v).replaceAll("~","~0").replaceAll("/","~1");
const pointer = key => /(?:entity|referent)_ids?$/u.test(key);
const playerAliases = { character_id:"character_definition_id",name:"character_name",hp:"hp",max_hp:"max_hp",
  gold:"gold",max_potion_slots:"max_potion_slots" };
const runAliases = {act:"act",act_definition_id:"act_definition_id",act_name:"act_name",total_floor:"floor",
  ascension:"ascension",modifiers:"modifiers"};
const noncombat = new Set(["event","rest","shop","treasure","reward","selection","terminal","map"]);

function valid(value) {
  if (value === null || ["string","boolean"].includes(typeof value)) return;
  if (typeof value === "number" && Number.isFinite(value)) return;
  if (Array.isArray(value)) { value.forEach(valid); return; }
  if (!object(value) || Object.getPrototypeOf(value) !== Object.prototype) throw Error("Finite ordinary public JSON required");
  for (const [key,item] of Object.entries(value)) {
    if (["__proto__","prototype","constructor"].includes(key)) throw Error("Unsafe public property");
    valid(item);
  }
}
function changes(a,b,path="") {
  if (same(a,b)) return [];
  if (object(a) && object(b)) return [...new Set([...Object.keys(a),...Object.keys(b)])].sort().flatMap(key => {
    const next=`${path}/${esc(key)}`;
    if (!Object.hasOwn(a,key)) return [{path:next,operation:"add",after:clone(b[key])}];
    if (!Object.hasOwn(b,key)) return [{path:next,operation:"remove",before:clone(a[key])}];
    return changes(a[key],b[key],next);
  });
  return [{path,operation:"replace",before:clone(a),after:clone(b)}];
}
export function restoreLayout(result) {
  if (result.layout !== LAYOUT || hash(result.public_input) !== result.canonical_digest) throw Error("Changed layout evidence");
  const input=clone(result.public_input);
  for (const change of result.rewrites.toReversed()) {
    const keys=change.path.slice(1).split("/").map(k=>k.replaceAll("~1","/").replaceAll("~0","~"));
    if (keys.some(k=>["__proto__","prototype","constructor"].includes(k))) throw Error("Unsafe layout path");
    const key=keys.pop(), parent=keys.reduce((v,k)=>v[k],input);
    if (change.operation === "add") delete parent[key];
    else if (["remove","replace"].includes(change.operation)) parent[key]=clone(change.before);
    else throw Error("Unknown layout rewrite");
  }
  if (hash(input) !== result.original_digest) throw Error("Layout reconstruction failed");
  return input;
}
function slots(input) {
  const ids=new Map();
  const declare=id=>{
    if (!Number.isSafeInteger(id) || id<0) throw Error("Invalid public slot");
    if (!ids.has(id)) ids.set(id,ids.size);
  };
  function walk(v,fn,path="") {
    if(Array.isArray(v)) {v.forEach((x,i)=>walk(x,fn,`${path}/${i}`));return;}
    if(!object(v))return;fn(v,path);
    for(const k of Object.keys(v).sort())walk(v[k],fn,`${path}/${esc(k)}`);
  }
  const operand=path=>/^\/context\/referents\/\d+$/u.test(path)||/^\/candidates\/\d+\/(?:subject|arguments\/\d+\/entity)$/u.test(path);
  const declarations=(v,path)=>walk(v,(row,at)=>{
    if(object(row.entity_id))declare(row.entity_id.public_slot);
    if(operand(at)&&Object.hasOwn(row,"public_slot"))declare(row.public_slot);
  },path);
  declarations(input.context.persistent,"/context/persistent");
  declarations(input.context.reads,"/context/reads");
  declarations(input.context.interaction,"/context/interaction");
  declarations(input.context.referents,"/context/referents");declarations(input.candidates,"/candidates");
  function replace(v,path="",isPointer=false) {
    if(Array.isArray(v)){v.forEach((x,i)=>replace(x,`${path}/${i}`,isPointer));return;}
    if(!object(v))return;
    if((isPointer||operand(path))&&Object.hasOwn(v,"public_slot")) {
      if(!ids.has(v.public_slot))throw Error("Undeclared canonical slot");v.public_slot=ids.get(v.public_slot);
    }
    for(const k of Object.keys(v))replace(v[k],`${path}/${esc(k)}`,pointer(k));
  }
  replace(input);
  input.context.referents.sort((a,b)=>a.public_slot-b.public_slot);
}
function nativeInventoryMatches(source,target) {
  if(!Array.isArray(source)||!Array.isArray(target)||source.length!==target.length)return false;
  return source.every((row,i)=>{
    if(!object(row))return false;
    const expected=target[i];
    return Object.entries(row).every(([key,v])=>key==="id" ? v===expected.definition_id
      : key==="counter"&&v===null&&!Object.hasOwn(expected,key) ? true
      : Object.hasOwn(expected,key)&&same(v,expected[key]));
  });
}

export function normalizeLayout(input) {
  valid(input);assertPublicBoundary(input);
  if(input.schema_version!=="actual-engine-public-entity-graph-v1"||!object(input.context?.persistent)
    ||!object(input.context?.interaction?.content)||!Array.isArray(input.candidates))throw Error("Expected current public graph");
  const output=clone(input), rules=new Set(), unresolved=[];
  const context=output.context, persistent=context.persistent, interaction=context.interaction;
  const content=interaction.content, current=content.context, surface=content.surface;
  const rule=name=>rules.add(name);
  function equalRemove(row,key,target,name) {
    if(!Object.hasOwn(row,key))return;
    if(!same(row[key],target)){unresolved.push({code:"conflicting_duplicate",field:key,rule:name});return;}
    delete row[key];rule(name);
  }
  // Lifecycle labels describe two transports' ready policy boundary. They are
  // not the intro/summary phases on game-over screens, which remain intact.
  if(["ready","choosing"].includes(interaction.stage)) {interaction.stage="ready";rule("ready_policy_boundary");}
  if(["ready","choosing"].includes(surface.stage)){delete surface.stage;rule("duplicate_ready_surface_phase");}
  if(interaction.prompt===null){delete interaction.prompt;rule("absent_optional_prompt");}
  if(current?.kind==="event"&&surface.kind==="event_option") {
    // New native exports provide these directly; old missing exports are not guessed.
    for(const [key,target] of [["title","name"],["description","description"]])if(Object.hasOwn(surface,key)) {
      if(Object.hasOwn(current,target)&&!same(current[target],surface[key]))throw Error("Conflicting event text owners");
      current[target]=surface[key];delete surface[key];rule("event_text_owner");
    }
    // EventLiveContext.Body and native Event.Description name the same current
    // rendered page. Preserve the string verbatim and reject conflicting views.
    if(Object.hasOwn(current,"description")){
      if(Object.hasOwn(current,"body")&&current.description!==null&&!same(current.body,current.description))
        throw Error("Conflicting current event body and description");
      if(!Object.hasOwn(current,"body"))current.body=current.description;
      delete current.description;rule("current_rendered_event_body_alias");
    }
    if(!Object.hasOwn(current,"body"))current.body=null; // Declared nullable Body.
    if(interaction.prompt!==undefined&&same(interaction.prompt,current.body)){delete interaction.prompt;rule("duplicate_event_prompt");}
    function option(row) {
      if(!object(row)||typeof row.index!=="number"||!Object.hasOwn(row,"title"))return;
      if(typeof row.text_key==="string"||row.text_key===null) {delete row.text_key;rule("localization_lookup_provenance");}
      if(row.variables===null){delete row.variables;rule("absent_native_format_variables");}
      for(const key of ["description","relic_name","relic_description"])if(!Object.hasOwn(row,key))row[key]=null;
      for(const tip of row.tooltips??[])if(["text","card"].includes(tip.kind))
        for(const key of ["name","description","card"])if(!Object.hasOwn(tip,key))tip[key]=null;
    }
    surface.options?.forEach(option);
    context.referents.filter(row=>row.role==="option").forEach(row=>option(row.properties));
    for(const candidate of output.candidates) {
      if(candidate.subject?.role==="option")option(candidate.subject.properties);
      for(const arg of candidate.arguments)if(arg.entity?.role==="option")option(arg.entity.properties);
    }
  }
  if(current?.kind==="selection"&&current.owner_kind==="event"&&!Object.hasOwn(current,"description"))current.description=null;
  if(surface.kind==="card_bundle_selection"&&surface.selection_contract==="committed_public_bundle_choice_v1") {
    // At this contract boundary a root choice includes preview and confirmation.
    // False staging controls and selectable IDs are verified by the scope adapter.
    for(const key of ["selectable_bundle_entity_ids","can_confirm","can_cancel_preview"])
      if(Object.hasOwn(surface,key)){delete surface[key];rule("committed_pack_UI_staging");}
  }

  if(surface.kind==="reward_claim"&&current?.kind==="reward_flow") {
    // The native skip_rewards control and shipped Proceed button both close
    // this pending reward set. Keep the exact raw binding in reversible evidence.
    const skip=output.candidates.filter(c=>c.verb==="skip"&&c.label==="Skip remaining rewards"
      &&c.subject===null&&c.arguments.length===0);
    if(skip.length===1&&surface.proceed_skips_remaining_rewards===true) {
      skip[0].verb="activate";skip[0].label="Skip remaining rewards and continue";
      if(surface.can_proceed===false)surface.can_proceed=true;
      for(const cap of interaction.capabilities??[])if(cap.verb==="skip"&&cap.subject_role===undefined
        &&cap.arguments?.length===0)cap.verb="activate";
      rule("current_reward_skip_control_alias");
    }
    const rewardIds=new Set((surface.rewards??[]).map(r=>r.entity_id?.public_slot));
    function rewardText(row) {
      if(object(row)&&typeof row.description==="string") {
        const text=row.description.replace(/\[\/?(?:blue|gold|red|green|purple|yellow|gray|grey|orange|b|i|u)\]/giu, "").replace(/\n/gu, " ");
        if(text!==row.description){row.description=text;rule("formatted_visible_reward_description");}
      }
    }
    (surface.rewards??[]).forEach(rewardText);
    for(const ref of context.referents)if(ref.role==="reward"&&rewardIds.has(ref.public_slot))rewardText(ref.properties);
    for(const candidate of output.candidates)if(candidate.subject?.role==="reward"
      &&rewardIds.has(candidate.subject.public_slot))rewardText(candidate.subject.properties);
    if(Array.isArray(surface.potion_states)&&surface.potion_states.length===0&&persistent.player.potions?.length===0){
      delete surface.potion_states;rule("duplicate_empty_reward_belt");
    }
  }

  if(surface.kind==="card_reward_selection"&&current?.kind==="reward_flow"
      &&Array.isArray(surface.potion_states)&&surface.potion_states.length===0
      &&persistent.player.potions?.length===0){
    delete surface.potion_states;rule("duplicate_empty_card_reward_belt");
  }

  if(noncombat.has(current?.kind)&&persistent.scope==="active_single_player_run") {
    const player=current.player,run=current.run;
    const samePlayer=object(player)&&[player.entity_id,player.player_entity_id,player.owner_entity_id]
      .filter(v=>v!==undefined).every(v=>same(v,persistent.player.entity_id));
    if(samePlayer) {
      for(const [key,target]of Object.entries(playerAliases))if(Object.hasOwn(persistent.player,target))
        equalRemove(player,key,persistent.player[target],"duplicate_single_player_hud");
      const deck=context.reads.find(row=>row.kind==="run_deck")?.content;
      if(deck&&deck.card_count===deck.cards?.length)equalRemove(player,"deck_size",deck.card_count,"public_deck_count");
      for(const key of["relics","potions"])if(nativeInventoryMatches(player[key],persistent.player[key])) {
        delete player[key];rule("duplicate_owned_inventory");
      }
      // PlayerSummary.Block is not displayed outside combat. Only its inert zero
      // is classified here; any other value remains a visible discrepancy.
      if(player.block===0){delete player.block;rule("noncombat_unrendered_zero_block");}
      if(!Object.keys(player).length)delete current.player;
    }
    if(object(run)) {
      for(const [key,target]of Object.entries(runAliases))if(Object.hasOwn(persistent.run,target))
        equalRemove(run,key,persistent.run[target],"duplicate_current_run");
      equalRemove(run,"act_index",persistent.run.act-1,"derived_zero_based_act");
      // In act one these are the same public coordinate. Later local floor is
      // retained until an explicit visible-map relation can establish it.
      if(persistent.run.act===1)equalRemove(run,"floor",persistent.run.floor,"first_act_floor_alias");
      if(nativeInventoryMatches(run.bosses,persistent.run.bosses)){delete run.bosses;rule("duplicate_public_bosses");}
      if(object(run.boss)&&persistent.run.bosses?.length===1&&nativeInventoryMatches([run.boss],persistent.run.bosses)) {
        delete run.boss;rule("duplicate_single_public_boss");
      }
      const rooms={event:"Event",rest:"RestSite",shop:"Shop",treasure:"Treasure"};
      // A shop UI may also be owned by a merchant event. Only exact room aliases
      // collapse; a different underlying room remains explicit, not contradictory.
      if(rooms[current.kind==="selection"?current.owner_kind:current.kind]&&run.room_type===rooms[current.kind==="selection"?current.owner_kind:current.kind])
        equalRemove(run,"room_type",rooms[current.kind==="selection"?current.owner_kind:current.kind],"typed_current_room");
      if(!Object.keys(run).length)delete current.run;
    }
    if(Array.isArray(surface.potion_states)&&surface.potion_states.length===0&&persistent.player.potions?.length===0) {
      delete surface.potion_states;rule("duplicate_empty_visible_belt");
    }
    // Native's potion projection creates a redundant inspect-only player even
    // with an empty belt. Remove ONLY this exact, unused HUD duplicate.
    const used=new Set();
    function referenced(v,key="") {
      if(Array.isArray(v)){v.forEach(x=>referenced(x,key));return;}
      if(!object(v))return;
      if(pointer(key)&&Number.isSafeInteger(v.public_slot))used.add(v.public_slot);
      for(const [k,x]of Object.entries(v))referenced(x,k);
    }
    referenced(content);referenced(context.reads);referenced(persistent);
    for(const c of output.candidates) {
      if(c.subject)used.add(c.subject.public_slot);
      for(const a of c.arguments)if(a.entity)used.add(a.entity.public_slot);
    }
    context.referents=context.referents.filter(row=>{
      const p=row.properties;
      if(row.role!=="player"||used.has(row.public_slot)||row.label!==persistent.player.character_name
        ||!same(row.state,{visible:true})||!object(p)
        ||!same(Object.keys(p).sort(),["entity_id","hp","max_hp"])
        ||p.hp!==persistent.player.hp||p.max_hp!==persistent.player.max_hp)return true;
      rule("unused_single_player_HUD_alias");return false;
    });
  }
  // Native PlayerSummary repeats owned belt facts in a different layout.
  // Remove that copy only if every field is already public under the same slot
  // and definition in the persistent inventory or the current belt view.
  if(noncombat.has(current?.kind)&&object(current.player)&&Array.isArray(current.player.potions)
      &&Array.isArray(persistent.player.potions)&&Array.isArray(surface.potion_states)) {
    const matches=current.player.potions.every(raw=>{
      const owned=persistent.player.potions.filter(p=>p.slot===raw.slot&&p.definition_id===raw.id),
        belt=surface.potion_states.filter(p=>p.slot===raw.slot&&p.definition_id===raw.id);
      if(owned.length!==1||belt.length!==1)return false;
      return Object.entries(raw).every(([k,v])=>k==='id'?v===owned[0].definition_id:
        Object.hasOwn(owned[0],k)&&same(v,owned[0][k])||Object.hasOwn(belt[0],k)&&same(v,belt[0][k]));
    });
    if(matches&&current.player.potions.length===persistent.player.potions.length) {
      delete current.player.potions;rule('duplicate_owned_belt_facts');
      if(!Object.keys(current.player).length)delete current.player;
    }
  }
  // Scoped nullable card fields are declared by VisibleCard. Do not fill a
  // required boolean, a foreign object or an unrecognized custom record.
  function cards(row) {
    if(Array.isArray(row)){row.forEach(cards);return;}if(!object(row))return;
    if(object(row.entity_id)&&typeof row.definition_id==="string"&&typeof row.cost==="string"
      &&typeof row.type==="string"&&typeof row.rarity==="string"&&typeof row.is_upgraded==="boolean") {
      // VisibleCard.StarCost is a nullable text cost in the official DTO. The
      // CLI supplies an integer or X. Normalize only this declared field; zero
      // remains distinct from X, and unrelated numeric resources stay numeric.
      if(Number.isSafeInteger(row.star_cost)&&row.star_cost>=0){
        row.star_cost=String(row.star_cost);rule("typed_card_star_cost_text");
      }
      for(const key of["name","star_cost","existing_enchantment","keywords"])if(!Object.hasOwn(row,key))row[key]=null;
      if(object(row.public_card_views))for(const view of Object.values(row.public_card_views))
        for(const key of["description","target_type","can_play","unplayable_reason","stats","after_upgrade"])
          if(!Object.hasOwn(view,key))view[key]=null;
      if(row.after_upgrade===null){delete row.after_upgrade;rule("uncomputed_native_upgrade_placeholder");}
      if(object(row.public_card_views))for(const [key,view]of Object.entries(row.public_card_views))
        if(key.startsWith("referent:")&&Object.entries(row.public_card_views).some(([other,facts])=>
          !other.startsWith("referent:")&&same(facts,view))){delete row.public_card_views[key];rule("duplicate_reference_card_view");}
      rule("VisibleCard_declared_nullable_views");
    }
    Object.values(row).forEach(cards);
  }
  cards(output);
  if(Array.isArray(interaction.capabilities)) {
    interaction.capabilities.sort((a,b)=>stableJson(a)<stableJson(b)?-1:stableJson(a)>stableJson(b)?1:0);
    rule("unordered_capability_declarations");
  }
  if((current?.kind==="combat"||current?.kind==="selection"&&current.owner_kind==="combat")&&object(current.player)) {
    const p=current.player;
    if(nativeInventoryMatches(p.relics,persistent.player.relics)){delete p.relics;rule("duplicate_combat_relic_counters");}
    if(!Object.hasOwn(p,"stars"))p.stars=null; // VisibleCombatPlayer.Stars is explicitly nullable.
    for(const ref of context.referents)if(ref.role==="player"&&object(ref.properties)) {
      if(!Object.hasOwn(ref.properties,"stars"))ref.properties.stars=null;
    }
  }
  function playerLabel(entity) {
    if(entity?.role==="player"&&entity.label===null&&same(entity.properties?.entity_id,persistent.player.entity_id)) {
      entity.label=persistent.player.character_name;rule("same_current_player_display_name");
    }
  }
  context.referents.forEach(playerLabel);
  for(const c of output.candidates){playerLabel(c.subject);for(const a of c.arguments)playerLabel(a.entity);}
  slots(output);assertPublicBoundary(output);
  const result={layout:LAYOUT,public_input:output,original_digest:hash(input),canonical_digest:hash(output),
    rewrites:changes(input,output),rules:[...rules].sort(),unresolved};
  if(!same(restoreLayout(result),input))throw Error("Layout conversion is not reversible");
  return result;
}
