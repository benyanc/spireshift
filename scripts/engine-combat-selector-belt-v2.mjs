// Card selectors keep native belt permissions from the room that owns them.
import {projectSelectionFlows as other, selectionFlowReads} from "./engine-abandon-confirmation-surface-v1.mjs";
import {projectCardSelector} from "./engine-card-selector-surface-v1.mjs";
export {selectionFlowReads};
const previous = (state, ctx, helpers) => state.decision === "card_select"
  ? projectCardSelector(state, ctx, helpers) : other(state, ctx, helpers);

const combatTargets = new Set(["AllEnemies", "RandomEnemy", "AllAllies", "AnyEnemy"]);
const selectors = new Set(["card_select", "generated_card_choice"]);
const identity = value => typeof value === "string" && value.length > 0;

export function needsCombatSelectorBinding(state) {
  return selectors.has(state?.decision) && state.selection_combat != null
    && !state.answer_plan?.selected?.length
    && Array.isArray(state.player?.potions)
    && state.player.potions.some(row => row.can_use === true && combatTargets.has(row.target_type));
}

export function projectSelectionFlows(state, ctx, helpers) {
  if (!needsCombatSelectorBinding(state)) return previous(state, ctx, helpers);
  const combat = state.selection_combat;
  const belt = state.player.potions;
  const combatBelt = combat.player?.potions;
  if (state.selection_owner?.kind !== "combat" || combat.decision !== "combat_play"
      || !identity(state.player.native_ref) || combat.player?.native_ref !== state.player.native_ref
      || !Array.isArray(combatBelt) || combatBelt.length !== belt.length
      || !Array.isArray(combat.enemies))
    throw Error("Missing current combat selector belt owner");

  const targets = new Map(), bindings = new Map();
  const legacyBelt = belt.map((potion, index) => {
    const native = combatBelt[index];
    if (!identity(potion.native_ref) || !native || ["native_ref", "id", "slot", "can_use",
      "can_discard", "binding_supported", "usage", "target_type"].some(key => native[key] !== potion[key])
      || JSON.stringify(native.valid_target_refs) !== JSON.stringify(potion.valid_target_refs))
      throw Error("Combat selector belt differs from its current combat");
    if (potion.can_use !== true || !combatTargets.has(potion.target_type)) return potion;
    if (potion.binding_supported !== true || potion.usage !== "AnyTime")
      throw Error("Invalid native use permission during card selection");
    let exactTargets = [];
    if (potion.target_type === "AnyEnemy") {
      const refs = potion.valid_target_refs;
      if (!Array.isArray(refs) || !refs.length || new Set(refs).size !== refs.length
          || refs.some(ref => !identity(ref) || !combat.enemies.some(enemy => enemy.native_ref === ref)))
        throw Error("Missing exact combat selector potion targets");
      exactTargets = refs.map(ref => ({native: ref, id: ctx.id("enemy", ctx.snapshotId, ref)}));
      for (const target of exactTargets) targets.set(target.id, null);
    } else if (potion.valid_target_refs !== null) {
      throw Error("Unexpected explicit target for an untargeted combat potion");
    }
    const id = ctx.id("potion", ctx.snapshotId, potion.native_ref, index);
    bindings.set(id, {potion, exactTargets, subject: null});
    // The frozen selector supplies its cards, reads and discard bindings.
    // This adapter owns the additional combat-targeted Use bindings.
    return {...potion, can_use: false};
  });

  const legacy = {...state, player: {...state.player, potions: legacyBelt}};
  const result = previous(legacy, {...ctx, referent(value) {
    const binding = value.role === "potion" ? bindings.get(value.id) : null;
    if (binding) {
      if (binding.subject) throw Error("Duplicate combat selector potion referent");
      const subject = ctx.referent({...value, enabled: true, properties: {
        ...value.properties, can_use: true,
        target_entity_ids: binding.exactTargets.map(target => target.id),
      }});
      binding.subject = subject;
      return subject;
    }
    const reference = ctx.referent(value);
    if (value.role === "enemy" && targets.has(value.id)) targets.set(value.id, reference);
    return reference;
  }}, helpers);
  if (!result.complete) return result;
  for (const {potion, exactTargets, subject} of bindings.values()) {
    if (!subject) throw Error("Missing owned combat selector potion referent");
    const args = {potion_slot: potion.slot, potion_ref: potion.native_ref};
    if (exactTargets.length) {
      for (const target of exactTargets) {
        const referent = targets.get(target.id);
        if (!referent) throw Error("Missing bound enemy for combat selector potion");
        ctx.action({verb: "use", subject, arguments: [{role: "target", referent}],
          label: `Use ${potion.name} on ${referent.label}`,
          raw: {cmd: "action", action: "use_potion", args: {...args, target_ref: target.native}}});
      }
    } else {
      ctx.action({verb: "use", subject, label: `Use ${potion.name}`,
        raw: {cmd: "action", action: "use_potion", args}});
    }
  }
  return result;
}
