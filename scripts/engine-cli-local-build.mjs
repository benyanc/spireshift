// A distinct, unqualified local build. Never relax the upstream binary's pins.
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";

export const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
export const hashFile = (file) => sha(readFileSync(file));
export function canonicalPatch(patch) {
  return String(patch).replaceAll("\r\n", "\n").replace(/\n*$/u, "\n")
    .split("\n").filter((line) => !line.startsWith("index ")).join("\n");
}
export function assertSameBuild(first, second, expected) {
  for (const key of ["artifact_sha256", "artifact_mvid", "godot_stub_sha256",
    "runtime_sts2_sha256", "reference_pack_id", "source_diff_id", "runtime_dependencies_id"]) {
    if (first[key] !== second[key]) throw new Error(`Fresh builds differ: ${key}`);
  }
  for (const [key, value] of Object.entries(expected ?? {})) {
    if (first[key] !== value) throw new Error(`Local build pin changed: ${key}`);
  }
}

export async function buildLocalCandidate(spec) {
  const source = (file) => pathToFileURL(path.join(spec.headless_root, "src", file)).href;
  const { resolveInstallation, readDiskIdentity } = await import(source("game-installation.mjs"));
  const { assertManagedCandidateGame, auditManagedCandidateSource,
    loadManagedCandidateManifest, resolveDotnet } = await import(source("managed-candidate.mjs"));
  const { manifest } = loadManagedCandidateManifest(spec.headless_root);
  const disk = readDiskIdentity(resolveInstallation(spec.game));
  assertManagedCandidateGame(manifest, disk);
  let step = 0;
  const run = async (command, args, cwd = spec.attempt) => {
    try {
      const result = await promisify(execFile)(command, args,
        { cwd, env: process.env, timeout: 45_000, maxBuffer: 20 * 1024 * 1024 });
      writeFileSync(path.join(spec.attempt, `step-${step++}.log`), result.stdout + result.stderr);
      return result.stdout;
    } catch (error) {
      writeFileSync(path.join(spec.attempt, `step-${step++}.log`),
        (error.stdout ?? "") + (error.stderr ?? "") + `\n${error.message}\n`);
      throw error;
    }
  };
  const dotnet = await resolveDotnet();
  if (dotnet.version !== spec.expected_toolchain.sdk_version) throw new Error("Local SDK pin changed");
  const sdkList = await run(dotnet.command, ["--list-sdks"]);
  const sdk = sdkList.split("\n").find((line) => line.startsWith(`${dotnet.version} [`));
  if (!sdk) throw new Error("Selected SDK directory is unknown");
  const sdkDirectory = path.join(sdk.slice(sdk.indexOf("[") + 1, sdk.lastIndexOf("]")), dotnet.version);
  const compiler = hashFile(path.join(sdkDirectory, "Roslyn/bincore/csc.dll"));
  if (compiler !== spec.expected_toolchain.csc_sha256) throw new Error("Local compiler pin changed");
  const fingerprint = async (file) => {
    const raw = await run(dotnet.command, ["run", "--project",
      path.join(spec.headless_root, "tools/dotnet/AssemblyFingerprint"), "--", "--assembly", file]);
    const value = JSON.parse(raw);
    writeFileSync(path.join(spec.attempt, `fingerprint-${step}.json`), raw);
    return value.assembly.module_mvid;
  };
  const oneBuild = async (name, repaired) => {
    const candidate = path.join(spec.attempt, name);
    await run("git", ["clone", "--no-checkout", spec.clone_cache, candidate]);
    // SourceLink embeds the origin URL in the PDB, whose digest contributes to
    // the DLL identity. A local clone cache must retain the real upstream origin.
    await run("git", ["remote", "set-url", "origin", manifest.upstream.url], candidate);
    await run("git", ["checkout", "--detach", manifest.upstream.revision], candidate);
    await run("git", ["read-tree", "HEAD"], candidate);
    await run("git", ["apply", "--whitespace=error-all",
      path.join(spec.headless_root, "experiments/managed-exact", manifest.source_patch)], candidate);
    await run("git", ["add", "-N", "--", "src/Sts2Headless/PerformanceLab.cs"], candidate);
    await auditManagedCandidateSource({ root: spec.headless_root, candidateDirectory: candidate, manifest });
    if (repaired) {
      if (hashFile(spec.local_patch) !== spec.local_patch_sha256) throw new Error("Rest source patch changed");
      await run("git", ["apply", "--whitespace=error-all", spec.local_patch], candidate);
    }
    const diff = await run("git", ["diff", "--binary", "--no-ext-diff"], candidate);
    const sourceDiffId = sha(canonicalPatch(diff));
    if (repaired && sourceDiffId !== spec.expected_source_diff_id) throw new Error("Combined source diff changed");
    writeFileSync(path.join(spec.attempt, `${name}-source.patch`), diff);
    mkdirSync(path.join(candidate, "lib"));
    const data = path.dirname(disk.sts2_assembly.path);
    const dependencies = [];
    for (const file of manifest.required_game_files) {
      copyFileSync(path.join(data, file), path.join(candidate, "lib", file));
      dependencies.push({ path: file, sha256: hashFile(path.join(data, file)) });
    }
    await run("bash", ["setup.sh", data], candidate);
    await run(dotnet.command, ["build", manifest.setup_contract.managed_project, "-c", "Release", "--nologo"], candidate);
    const artifact = path.join(candidate, manifest.setup_contract.managed_artifact);
    const assets = JSON.parse(readFileSync(path.join(candidate, "src/Sts2Headless/obj/project.assets.json")));
    const referenceRoot = Object.keys(assets.packageFolders)[0];
    const referenceVersion = assets.project.frameworks["net9.0"].downloadDependencies
      .find((dep) => dep.name === "Microsoft.NETCore.App.Ref").version.match(/\[([^,]+)/u)?.[1];
    if (referenceVersion !== spec.expected_toolchain.reference_version) throw new Error("Target reference version changed");
    const referencePath = path.join(referenceRoot, "microsoft.netcore.app.ref", referenceVersion, "ref/net9.0");
    const referenceInventory = readdirSync(referencePath).filter((file) => file.endsWith(".dll")).sort()
      .map((file) => ({ path: file, sha256: hashFile(path.join(referencePath, file)) }));
    const referencePackId = sha(JSON.stringify(referenceInventory));
    if (referencePackId !== spec.expected_toolchain.reference_pack_id) throw new Error("Target reference pack changed");
    const output = path.dirname(artifact);
    const runtimeDependencies = readdirSync(output).filter((file) => file.endsWith(".dll") && file !== "Sts2Headless.dll").sort()
      .map((file) => ({ path: file, sha256: hashFile(path.join(output, file)) }));
    const beforeGame = hashFile(path.join(candidate, "lib/sts2.dll.original"));
    const runtimeGame = hashFile(path.join(candidate, "lib/sts2.dll"));
    if (beforeGame !== manifest.exact_game.sts2_dll_sha256 || runtimeGame !== beforeGame)
      throw new Error("Game assembly changed");
    const afterDiff = await run("git", ["diff", "--binary", "--no-ext-diff"], candidate);
    if (sha(canonicalPatch(afterDiff)) !== sourceDiffId) throw new Error("Build altered its source ledger");
    return { candidate_directory: candidate, artifact, artifact_sha256: hashFile(artifact),
      artifact_mvid: await fingerprint(artifact), source_diff_id: sourceDiffId,
      godot_stub_sha256: hashFile(path.join(output, "GodotSharp.dll")),
      original_sts2_sha256: beforeGame, runtime_sts2_sha256: runtimeGame,
      reference_version: referenceVersion, reference_pack_id: referencePackId,
      runtime_dependencies_id: sha(JSON.stringify(runtimeDependencies)),
      game_dependencies: dependencies, runtime_dependencies: runtimeDependencies };
  };
  const baseline = [await oneBuild("baseline-1", false), await oneBuild("baseline-2", false)];
  writeFileSync(path.join(spec.attempt, "build-progress.json"), JSON.stringify({ baseline }));
  assertSameBuild(baseline[0], baseline[1], spec.expected_baseline);
  const repaired = [await oneBuild("candidate", true), await oneBuild("repeat", true)];
  writeFileSync(path.join(spec.attempt, "build-progress.json"), JSON.stringify({ baseline, repaired }));
  assertSameBuild(repaired[0], repaired[1], spec.expected_repaired);
  return { status: "local_candidate_built_unqualified", baseline, repaired,
    toolchain: { sdk_version: dotnet.version, csc_sha256: compiler, dotnet_command: dotnet.command,
      runtime_list: await run(dotnet.command, ["--list-runtimes"]) },
    upstream_binary_reproduced: baseline[0].artifact_sha256 === manifest.expected_build.artifact_sha256,
    upstream_expected_build: manifest.expected_build, training_allowed: false };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  const spec = JSON.parse(input);
  let result;
  try { result = await buildLocalCandidate(spec); }
  catch (error) { result = { status: "local_candidate_build_failed", error: error.message, training_allowed: false }; }
  writeFileSync(path.join(spec.attempt, "candidate-build.json"), `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify({ status: result.status, error: result.error ?? null }));
  if (result.status !== "local_candidate_built_unqualified") process.exitCode = 1;
}
