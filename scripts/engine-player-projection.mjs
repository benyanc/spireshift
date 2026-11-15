// Stage an MIT projection hook in a disposable source copy. Pinned sources stay unchanged.
import { execFileSync } from "node:child_process";
import { symlinkSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { hashFile } from "./engine-cli-local-build.mjs";

export async function preparePlayerProjection(spec) {
  const pin = spec.projection;
  const source = path.join(spec.headless_root, "src/managed-player-environment.mjs");
  if (hashFile(source) !== pin.source_sha256 || hashFile(pin.patch) !== pin.patch_sha256)
    throw new Error("Exact player projection source or patch drifted");
  const git = (args, cwd) => execFileSync("git", args, { cwd, encoding: "utf8", timeout: 10_000 });
  if (git(["rev-parse", "HEAD"], spec.headless_root).trim() !== pin.source_revision
      || git(["status", "--porcelain"], spec.headless_root).trim())
    throw new Error("Player projection requires the clean pinned Headless checkout");
  const staged = path.join(spec.attempt, "player-projection");
  git(["clone", "--quiet", "--local", spec.headless_root, staged], spec.attempt);
  git(["apply", "--check", "--whitespace=error-all", pin.patch], staged);
  git(["apply", "--whitespace=error-all", pin.patch], staged);
  const modulePath = path.join(staged, "src/managed-player-environment.mjs");
  if (hashFile(modulePath) !== pin.patched_source_sha256
      || git(["diff", "--name-only"], staged).trim() !== "src/managed-player-environment.mjs")
    throw new Error("Disposable projection no longer matches the exact hook patch");
  symlinkSync(pin.node_modules, path.join(staged, "node_modules"), "dir");
  const module = await import(pathToFileURL(modulePath).href);
  return { module, identity: { source_revision: pin.source_revision,
    source_sha256: pin.source_sha256, patch_sha256: pin.patch_sha256,
    patched_source_sha256: hashFile(modulePath), sdk_inventory_id: pin.sdk_inventory_id } };
}
