// The frozen game's SeedHelper.CanonicalizeSeed replaces O/I, uppercases, trims.
// Reject ambiguous recipe seeds; never replay a historical differently keyed world.
export function canonicalSeed(seed) {
  if(typeof seed!=="string"||!/^[A-Za-z0-9\s]+$/u.test(seed))throw Error("Seed must contain ASCII letters or digits");
  const canonical=seed.toUpperCase().replaceAll("O","0").replaceAll("I","1").trim();
  if(!/^[A-Z0-9]{1,64}$/u.test(canonical))throw Error("Seed is outside the native contract");
  return canonical;
}
export function requireCanonicalSeed(seed) {
  if(canonicalSeed(seed)!==seed)throw Error("Use an already canonical game seed without O or I");
  return seed;
}
export function verifyEpisodeSeed(provenance,seed,runtime) {
  requireCanonicalSeed(seed);
  if(provenance?.status!=="seed_observed"||provenance.runtime_instance_id!==runtime
    ||provenance.requested_seed!==seed||provenance.actual_seed!==seed||provenance.seed_matches!==true)
    throw Error("Actual official seed differs from the declared comparison world");
  return {seed,status:"exact_episode_seed_verified",runtime_instance_id:runtime};
}
