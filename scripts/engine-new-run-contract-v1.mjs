import { firstDifference } from "./engine-journey-contract-v2.mjs";
export { firstDifference };

export function chooseStartupAction(snapshot) {
  const kind = snapshot.interaction.kind, actions = snapshot.bound_actions.actions;
  if (kind === "tutorial") {
    const id = snapshot.interaction.content.surface.tutorial_id;
    const enable = snapshot.interaction.content.surface.options?.find(row => row.semantic_id === "enable_tutorials" && row.enabled === true);
    const action = id === "ascension_singleplayer_ftue" ? (actions.length === 1 ? actions[0] : null)
      : id === "accept_tutorials_ftue" && enable ? actions.find(row => row.label === enable.label) : null;
    if (!action) throw Error("Unqualified startup tutorial");
    return action;
  }
  if (actions.some(row => /continue|resume/iu.test(row.label))) throw Error("Fresh profile unexpectedly offers Continue");
  if (kind === "character_select") {
    const surface = snapshot.interaction.content.surface;
    const ironclad = surface.characters?.find(row => /ironclad$/iu.test(row.character_id ?? row.definition_id ?? row.name ?? ""));
    if (!ironclad || ironclad.is_locked === true) throw Error("No unlocked Ironclad in the normal lobby");
    if (!ironclad.is_selected) {
      const action = actions.find(row => /ironclad/iu.test(row.label));
      if (!action) throw Error("No current Ironclad select control");
      return action;
    }
    if (surface.ascension !== 8) {
      if (!Number.isSafeInteger(surface.ascension)) throw Error("Missing visible lobby ascension");
      const action = actions.find(row => (surface.ascension < 8 ? /increase ascension/iu : /decrease ascension/iu).test(row.label));
      if (!action) throw Error("No current control to select A8");
      return action;
    }
    const action = actions.find(row => /^embark$/iu.test(row.label));
    if (!action) throw Error("No current standard-run Embark control");
    return action;
  }
  if (!["main_menu", "singleplayer_menu"].includes(kind)) throw Error(`Unsupported fresh-run startup: ${kind}`);
  const action = actions.find(row => !/custom|daily|multiplayer/iu.test(row.label)
    && /single ?player|standard|new run|^play$/iu.test(row.label));
  if (!action) throw Error("No standard new-run menu action");
  return action;
}

export function startingFacts(snapshot, deckRead) {
  const run = snapshot.persistent.content.run, player = snapshot.persistent.content.player;
  const required = (row, keys) => Object.fromEntries(keys.map(key => {
    if (row?.[key] == null) throw Error(`Missing starting fact: ${key}`);
    return [key, row[key]];
  }));
  const sort = rows => rows.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b), "en"));
  const text = value => {
    if (typeof value !== "string" || !value.trim() || /\{[A-Za-z][^}]*\}/u.test(value))
      throw Error("Incomplete formatted starting text");
    return value.replace(/\[\/?(?:gold|blue|red|green|gray|purple|orange|b|i)\]/giu, "").trim();
  };
  if (snapshot.interaction.kind !== "event_option" || run.ascension !== 8 || run.floor !== 1
      || deckRead.completeness.status !== "complete" || deckRead.observed_snapshot_id !== snapshot.snapshot_id)
    throw Error("New-run comparison requires the complete initial A8 ancient");
  return {
    run: required(run, ["act", "act_definition_id", "ascension", "floor"]),
    player: { ...required(player, ["character_definition_id", "hp", "max_hp", "gold", "max_potion_slots"]),
      deck: sort(deckRead.content.cards.map(row => ({ ...required(row, ["definition_id", "cost", "is_upgraded"]), description: text(row.description) }))),
      relics: sort(player.relics.map(row => ({ ...required(row, ["definition_id"]), description: text(row.description), counter: row.counter ?? null }))),
      potions: sort(player.potions.map(row => ({ ...required(row, ["definition_id", "slot"]), description: text(row.description) }))) },
    options: snapshot.interaction.content.surface.options.map(row => ({ title: text(row.title ?? row.label),
      description: text(row.description), is_locked: typeof row.is_locked === "boolean" ? row.is_locked
        : typeof row.enabled === "boolean" ? !row.enabled : (() => { throw Error("Missing option availability"); })() }))
  };
}
