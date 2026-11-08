// A native victory can also set the dead flag. Match the completed outcome first.
export function checkNativeEnding(run, identity) {
  if (run.status !== "candidate_terminal") return false;
  if (typeof run.victory !== "boolean" ||
      !["native_game_over", "native_victory_room", "native_player_dead"]
        .every(key => typeof identity?.[key] === "boolean"))
    throw Error("Missing explicit native ending evidence");
  const {native_game_over: ended, native_victory_room: victoryRoom,
    native_player_dead: dead} = identity;
  const nativeOutcome = ended ? victoryRoom : dead && !victoryRoom ? false : null;
  if (run.victory !== nativeOutcome)
    throw Error("Public ending disagrees with the completed native outcome");
  return true;
}
