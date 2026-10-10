// Build only; no gameplay command, environment admission or neural training.
import { copyFileSync, mkdirSync, writeFileSync } from "node:fs";
import { execFile } from "node:child_process";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";

let input = "";
for await (const chunk of process.stdin) input += chunk.toString();
const spec = JSON.parse(input);
const source = (file) => pathToFileURL(path.join(spec.headless_root, "src", file)).href;
let result;
try {
  const { resolveInstallation, readDiskIdentity } = await import(source("game-installation.mjs"));
  const { assertManagedCandidateGame, auditManagedCandidateSource,
    inspectManagedCandidateBuild, loadManagedCandidateManifest, resolveDotnet } =
    await import(source("managed-candidate.mjs"));
  const { manifest } = loadManagedCandidateManifest(spec.headless_root);
  const disk = readDiskIdentity(resolveInstallation(spec.game));
  assertManagedCandidateGame(manifest, disk);
  const run = async (command, args, cwd = spec.attempt) => {
    try {
      const output = await promisify(execFile)(command, args,
        { cwd, env: process.env, timeout: 180_000, maxBuffer: 16 * 1024 * 1024 });
      writeFileSync(path.join(spec.attempt, `step-${step++}.log`), output.stdout + output.stderr);
      return output;
    } catch (error) {
      writeFileSync(path.join(spec.attempt, `step-${step++}.log`),
        (error.stdout ?? "") + (error.stderr ?? "") + `\n${error.message}\n`);
      throw error;
    }
  };
  let step = 0;
  const candidate = path.join(spec.attempt, "candidate");
  await run("git", ["clone", "--no-checkout", manifest.upstream.url, candidate]);
  await run("git", ["checkout", "--detach", manifest.upstream.revision], candidate);
  // Initialize the index explicitly after a --no-checkout clone. Preserve the failed
  // upstream attempt rather than weakening its exact source-diff comparison.
  await run("git", ["read-tree", "HEAD"], candidate);
  await run("git", ["apply", "--whitespace=error-all",
    path.join(spec.headless_root, "experiments/managed-exact", manifest.source_patch)], candidate);
  await run("git", ["add", "-N", "--", "src/Sts2Headless/PerformanceLab.cs"], candidate);
  await auditManagedCandidateSource({ root: spec.headless_root, candidateDirectory: candidate, manifest });
  const dotnet = await resolveDotnet();
  const data = path.dirname(disk.sts2_assembly.path);
  mkdirSync(path.join(candidate, "lib"), { recursive: true });
  for (const name of manifest.required_game_files) copyFileSync(path.join(data, name), path.join(candidate, "lib", name));
  await run("bash", ["setup.sh", data], candidate);
  await run(dotnet.command, ["build", manifest.setup_contract.managed_project, "-c", "Release", "--nologo"], candidate);
  const build = await inspectManagedCandidateBuild({ root: spec.headless_root, candidateDirectory: candidate, manifest });
  result = { status: "candidate_built_unqualified", build, dotnet,
    index_initialization: "read_tree_HEAD_plain_apply_explicit_new_file_intent", manifest };
} catch (error) {
  result = { status: "candidate_build_failed", error: error.message };
}
writeFileSync(path.join(spec.attempt, "candidate-build.json"), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
if (result.status !== "candidate_built_unqualified") process.exitCode = 1;
