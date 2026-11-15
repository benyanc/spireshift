// Bind the frozen host's actual Crystal Sphere tool/cell choices.
import { projectSelectionFlows as previous } from "./engine-combat-selector-belt-v2.mjs";
import { appendPotionControls } from "./engine-potion-surface-v1.mjs";
import { ownedBeltContext } from "./engine-relic-surface-v3.mjs";

const name = "Crystal Sphere — grid";
const width = 11;
const cells = width * width;
const tools = ["Small", "Big"];

export function crystalGrid(state) {
  if (state?.decision !== "event_choice" || state.event_id !== "CRYSTAL_SPHERE"
      || state.event_name !== name) return null;
  const board = /^Divinations remaining: ([1-9][0-9]*)\. Visible grid: (.+)$/u.exec(state.description);
  if (!board || !Number.isSafeInteger(Number(board[1])) || state.context?.room_type !== "Event"
      || !Array.isArray(state.options) || state.options.length !== tools.length * cells)
    throw Error("Incomplete current Crystal Sphere grid");
  const visible = board[2].split("; ");
  if (visible.length !== cells || visible.some((entry, index) => {
    const match = /^\((\d+),(\d+)\): ([_A-Za-z][_A-Za-z0-9]*)$/u.exec(entry);
    return !match || match[1] !== String(Math.floor(index / width)) || match[2] !== String(index % width);
  })) throw Error("Crystal Sphere grid coordinates differ from the visible native board");

  const options = state.options.map((row, index) => {
    const tool = tools[Math.floor(index / cells)];
    const x = Math.floor((index % cells) / width), y = index % width;
    const title = `${tool} at (${x},${y})`;
    const description = `Use ${tool} on visible grid coordinate (${x},${y}).`;
    if (row?.index !== index || row.title !== title || row.description !== description
        || row.is_locked !== false)
      throw Error("Crystal Sphere choice differs from the current native tool and coordinate");
    return { index, title, description, is_locked: row.is_locked };
  });
  return { divinations: Number(board[1]), options };
}

export function projectSelectionFlows(state, ctx, helpers) {
  const grid = crystalGrid(state);
  if (grid === null) return previous(state, ctx, helpers);
  const options = grid.options.map(row => {
    const subject = ctx.referent({
      role: "option", label: row.title, enabled: true, occurrence: row.index, properties: row,
    });
    ctx.action({ verb: "activate", subject, label: row.title,
      raw: { cmd: "action", action: "choose_option", args: { option_index: row.index } } });
    return subject.properties;
  });
  const result = {
    kind: "event_option", stage: "choosing", prompt: state.description,
    surface: { kind: "event_option", stage: "choosing", title: name,
      description: state.description, options },
    context: { kind: "event", run: state.context, player: helpers.withoutDeck(state.player),
      event_id: state.event_id, name, ancient: false, in_dialogue: false },
    complete: true, missing: [], visibleInformation: "native_visible_crystal_sphere_board",
    interactionDiscovery: "native_current_crystal_sphere_tool_and_coordinate",
  };
  return appendPotionControls(state, ownedBeltContext(state, ctx), helpers, result);
}
