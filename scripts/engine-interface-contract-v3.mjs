// Current merchant ownership and read checks shared by both selector formats.
import { assertPublicBoundary } from "./engine-run-contract-v1.mjs";
import { selectorFormat } from "./engine-card-answer-v1.mjs";

export function publicShopSlots(snapshot, reads) {
  assertPublicBoundary({ snapshot, reads });
  const result = structuredClone({ snapshot, reads });
  if (snapshot.interaction.kind === "event_option") {
    for (const option of result.snapshot.interaction.content.surface.options ?? []) {
      const refs = result.snapshot.referents.filter(r => r.referent_id === option.entity_id && r.role === "option");
      const enabled = refs.length === 1 ? refs[0].state?.enabled : undefined;
      if (typeof option.is_enabled !== "boolean") {
        if (Object.hasOwn(option, "is_enabled") || typeof enabled !== "boolean")
          throw Error("Unknown current event-option enablement; no default flag");
        option.is_enabled = enabled;
      } else if (typeof enabled === "boolean" && enabled !== option.is_enabled)
        throw Error("Conflicting current event-option enablement");
      if (refs.length === 1) {
        if (Object.hasOwn(refs[0].properties, "is_enabled") && refs[0].properties.is_enabled !== option.is_enabled)
          throw Error("Conflicting current event-option properties");
        refs[0].properties.is_enabled = option.is_enabled;
      }
    }
  }
  for (const read of result.reads) {
    if (read.kind === "surface_card") {
      const descriptor = snapshot.reads.find(r => r.read_id === read.read_id);
      if (typeof read.target_referent_id !== "string" || !read.target_referent_id
          || descriptor?.target_referent_id !== read.target_referent_id
          || read.content?.entity_id !== read.target_referent_id)
        throw Error("Surface-card detail is bound to a different current card");
    }
    if (read.kind !== "shop_catalog") continue;
    const interaction = snapshot.interaction;
    if (interaction.content.context?.kind !== "shop" ||
        !(["shop_room", "shop_inventory"].includes(interaction.kind)
          && interaction.content.surface?.kind === interaction.kind || selectorFormat(interaction)))
      throw Error("Shop catalog is outside its declared current owner");
    const descriptors = snapshot.reads.filter(row => row.read_id === read.read_id);
    if (descriptors.length !== 1 || descriptors[0].kind !== "shop_catalog"
        || read.expected_snapshot_id !== snapshot.snapshot_id || read.observed_snapshot_id !== snapshot.snapshot_id
        || read.session?.runtime_instance_id !== snapshot.session?.runtime_instance_id
        || read.completeness?.status !== "complete" || read.information_policy?.includes_hidden_information !== false)
      throw Error("Missing, stale, partial, cross-runtime or hidden shop catalog");
    const content = read.content, slots = [], owners = new Set(), ids = new Set();
    for (const group of ["cards", "relics", "potions", "card_removal"]) {
      // CardRemoval is nullable in the pinned SDK record; its serializer omits
      // nulls. That exception does not apply to arrays, booleans or other fields.
      if (!Object.hasOwn(content, group) && group === "card_removal") continue;
      if (!Object.hasOwn(content, group)) throw Error(`Incomplete shop catalog: ${group}`);
      const rows = group === "card_removal" ? (content[group] == null ? [] : [content[group]]) : content[group];
      if (!Array.isArray(rows)) throw Error("Invalid public shop catalog group");
      for (const [position, offer] of rows.entries()) {
        // The official typed read declares this precise offer-slot relation even
        // while the inventory is closed. A slot is not an action referent.
        if (typeof offer?.entity_id !== "string" || !offer.entity_id
            || typeof offer.slot_entity_id !== "string" || !offer.slot_entity_id
            || offer.entity_id === offer.slot_entity_id || ids.has(offer.slot_entity_id)
            || owners.has(offer.entity_id)) throw Error("Ambiguous public offer-slot ownership");
        ids.add(offer.slot_entity_id); owners.add(offer.entity_id);
        slots.push({ entity_id: offer.slot_entity_id, role: "shop_slot",
          offer_entity_id: offer.entity_id, group, position });
      }
    }
    if (Object.hasOwn(content, "declared_shop_slots"))
      throw Error("Producer already supplied a reserved slot-declaration field");
    content.declared_shop_slots = slots;
  }
  return result;
}
