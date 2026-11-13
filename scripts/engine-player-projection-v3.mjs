// Production workers load already verified, immutable local code. No clone, patch or build here.
import { createHash } from "node:crypto";
import { lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const hash = file => createHash("sha256").update(readFileSync(file)).digest("hex");
const canonical = value => Array.isArray(value) ? value.map(canonical)
  : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])])) : value;
export async function preparePlayerProjection(spec) {
  const ref = spec.shared_projection;
  if (ref?.policy !== "immutable_shared_local_projection_v2") throw Error("Missing qualified local projection reference");
  const directory = ref.directory, marker = path.join(directory, "identity.json");
  if (hash(marker) !== ref.identity_sha256) throw Error("Shared projection identity changed before worker startup");
  const identity = JSON.parse(readFileSync(marker, "utf8")), pin = spec.projection;
  if (JSON.stringify(canonical(identity.projection)) !== JSON.stringify(canonical(pin))
      || identity.policy !== ref.policy || identity.git_clones !== 0)
    throw Error("Shared projection pin/policy mismatch");
  const staged = path.join(directory, "player-projection"), files = [];
  if (lstatSync(directory).isSymbolicLink() || lstatSync(staged).isSymbolicLink()
      || lstatSync(path.join(staged, "src")).isSymbolicLink()
      || JSON.stringify(readdirSync(directory).sort()) !== JSON.stringify(["identity.json", "player-projection"])
      || JSON.stringify(readdirSync(staged).sort()) !== JSON.stringify(["node_modules", "package.json", "src"]))
    throw Error("Unexpected shared projection root entries or links");
  function walk(folder, prefix = "") {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      const relative = prefix + entry.name, target = path.join(folder, entry.name);
      if (entry.isSymbolicLink()) throw Error("Unexpected symlink in shared projection code");
      if (entry.isDirectory()) walk(target, `${relative}/`); else files.push(relative);
    }
  }
  walk(path.join(staged, "src"), "src/"); files.push("package.json");
  if (JSON.stringify(files.sort()) !== JSON.stringify(Object.keys(identity.files).sort())
      || files.some(name => hash(path.join(staged, name)) !== identity.files[name])
      || identity.files["src/managed-player-environment.mjs"] !== pin.patched_source_sha256
      || !lstatSync(path.join(staged, "node_modules")).isSymbolicLink()
      || realpathSync(path.join(staged, "node_modules")) !== realpathSync(pin.node_modules))
    throw Error("Shared projection membership, bytes or SDK link changed");
  return { identity, module: await import(pathToFileURL(path.join(staged, "src/managed-player-environment.mjs")).href),
    transport: await import(pathToFileURL(path.join(staged, "src/json-line-process.mjs")).href) };
}
