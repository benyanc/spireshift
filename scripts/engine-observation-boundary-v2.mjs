// Loading assets after Embark has a separately bounded startup window. Policy
// delivery and stale-read refresh retain their original tighter local limits.
export { observationBoundary } from "./engine-observation-boundary-v1.mjs";
export function observationDeadline(now,sessionDeadline,boundary,startup=false) {
  if(![now,sessionDeadline,boundary].every(Number.isFinite)||typeof startup!=="boolean")
    throw Error("Finite observation deadlines required");
  return Math.min(sessionDeadline,boundary,now+(startup?45000:15000));
}
