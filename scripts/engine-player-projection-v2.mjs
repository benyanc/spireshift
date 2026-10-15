// Diagnostics share immutable projection code; every worker retains a private ledger/profile.
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { preparePlayerProjection as prepare } from "./engine-player-projection.mjs";
import { hashFile } from "./engine-cli-local-build.mjs";

export async function preparePlayerProjection(spec) {
  if (!spec.projection_cache) return prepare(spec);
  if (spec.coverage_diagnostic !== true) throw Error("Projection cache is restricted to private coverage diagnostics");
  const cache = spec.projection_cache, pin = spec.projection;
  mkdirSync(cache, { recursive: true });
  const marker = path.join(cache, "identity.json"), staged = path.join(cache, "player-projection");
  let prepared;
  if (!existsSync(marker)) {
    // Exclusive clone refuses an interrupted or otherwise unbound cache.
    prepared = await prepare({ ...spec, attempt: cache });
    writeFileSync(marker, JSON.stringify(prepared.identity), { flag: "wx" });
  }
  const identity = JSON.parse(readFileSync(marker, "utf8"));
  const modulePath = path.join(staged, "src/managed-player-environment.mjs");
  const git = args => execFileSync("git", args, { cwd: staged, encoding: "utf8", timeout: 10000 }).trim();
  if (identity.source_revision !== pin.source_revision || identity.source_sha256 !== pin.source_sha256
      || identity.patch_sha256 !== pin.patch_sha256 || identity.sdk_inventory_id !== pin.sdk_inventory_id
      || identity.patched_source_sha256 !== pin.patched_source_sha256
      || hashFile(modulePath) !== pin.patched_source_sha256
      || hashFile(pin.patch) !== pin.patch_sha256 || git(["rev-parse", "HEAD"]) !== pin.source_revision
      || git(["diff", "--name-only"]) !== "src/managed-player-environment.mjs"
      || realpathSync(path.join(staged, "node_modules")) !== realpathSync(pin.node_modules))
    throw Error("Shared diagnostic projection changed; preserve the cache for inspection");
  return prepared ?? { identity, module: await import(pathToFileURL(modulePath).href) };
}
