// Bounded public-menu check using the pinned official SDK. No game strategy or rules.
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function validateLoadedIdentity(capabilities, expected) {
  const { target, connector } = expected;
  const implementation = capabilities?.host?.implementation;
  const game = capabilities?.game;
  return capabilities?.protocol_version === connector.protocol
    && capabilities.host.host_kind === "headless"
    && capabilities.host.version === connector.version
    && implementation?.artifact_sha256 === connector.artifact_sha256
    && implementation?.module_version_id === connector.artifact_mvid
    && implementation?.source_revision === connector.source_revision
    && game?.version === target.version && game?.commit === target.commit
    && game?.main_assembly_hash === target.runtime_main_assembly_hash
    && game?.compatibility?.observation_allowed === true
    && game?.modset?.status === "exact_player_environment_only"
    && JSON.stringify(game.modset.loaded_mod_ids) === JSON.stringify(["STS2_MCP"])
    && capabilities.execution_available === true;
}

export function completePublicMenu(snapshot, runtimeId) {
  const menu = snapshot?.bound_actions;
  return snapshot?.status === "interactive"
    && snapshot?.session?.runtime_instance_id === runtimeId
    && snapshot?.information_policy?.includes_hidden_information === false
    && snapshot?.completeness?.status === "complete"
    && menu?.status === "complete" && menu.actions.length > 0
    && menu.actions.length === menu.total_count && menu.actions.length === menu.materialized_count
    && new Set(menu.actions.map((item) => item.bound_action_id)).size === menu.actions.length
    && menu.actions.every((item) => item.interaction_id === snapshot.interaction.interaction_id);
}

export function completedTransition(initial, successor, receipt, runtimeId) {
  return receipt?.delivery === "delivered"
    && receipt?.attribution?.runtime_instance_id === runtimeId
    && completePublicMenu(successor, runtimeId)
    && successor.snapshot_id !== initial.snapshot_id
    && successor.interaction.interaction_id !== initial.interaction.interaction_id
    && successor.interaction.kind !== initial.interaction.kind;
}

function ownedEndpoint(spec) {
  const endpoint = new URL(spec.endpoint);
  if (endpoint.hostname !== "127.0.0.1" || endpoint.protocol !== "http:"
      || endpoint.pathname !== "/" || !endpoint.port || endpoint.username || endpoint.password
      || endpoint.search || endpoint.hash) throw new Error("Expected one explicit loopback endpoint");
  const result = spawnSync("/usr/sbin/lsof", [
    "-nP", `-iTCP:${endpoint.port}`, "-sTCP:LISTEN", "-Fp"
  ], { encoding: "utf8", timeout: 2_000 });
  const pids = result.stdout?.split("\n").filter((item) => /^p\d+$/u.test(item))
    .map((item) => Number(item.slice(1))) ?? [];
  return result.status === 0 && pids.length === 1 && pids[0] === spec.expected_pid;
}

async function readSpec() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  return JSON.parse(input);
}

async function menuProbe(spec) {
  const sdkUrl = pathToFileURL(path.join(spec.toolchain,
    "node_modules/@rsgcsg/sts2-connector-client/dist/index.js")).href;
  const { EnvironmentControllerSession, PlayerEnvironmentRestClient } = await import(sdkUrl);
  const client = new PlayerEnvironmentRestClient(spec.endpoint, 2_500);
  const started = Date.now();
  const deadline = started + spec.max_wall_seconds * 1_000;
  const result = { checks: {}, menu_actions_requested: 0, shutdown_requested: false };
  let session = null;
  let runtimeId = null;
  try {
    let capabilities = null;
    while (Date.now() < deadline) {
      try { process.kill(spec.expected_pid, 0); }
      catch { throw new Error("The launched native process exited before publishing capabilities"); }
      try { capabilities = (await client.capabilities()).data; break; }
      catch (error) {
        result.last_connection_error = String(error.message);
        await pause(250);
      }
    }
    if (!capabilities) throw new Error("Connector capabilities were not available before the cap");
    runtimeId = capabilities.host.runtime_instance_id;
    result.capabilities = capabilities;
    result.checks.loaded_identity = validateLoadedIdentity(capabilities, spec);
    result.checks.endpoint_owned_by_child = ownedEndpoint(spec);
    if (!result.checks.loaded_identity || !result.checks.endpoint_owned_by_child) {
      throw new Error("Loaded identity or endpoint ownership failed; no action submitted");
    }
    let initial = null;
    while (Date.now() < deadline) {
      const current = (await client.observe()).data;
      result.latest_snapshot = current;
      if (completePublicMenu(current, runtimeId)) { initial = current; break; }
      await pause(250);
    }
    if (!initial) throw new Error("No complete public interactive menu before the cap");
    result.initial_snapshot = initial;
    result.checks.complete_public_menu = completePublicMenu(initial, runtimeId);
    if (initial.interaction.kind !== "main_menu" || initial.bound_actions.actions.length !== 1) {
      throw new Error("This stage requires exactly one engine-advertised main-menu action");
    }
    const action = initial.bound_actions.actions[0];
    session = new EnvironmentControllerSession(client, {
      productId: "spireshift-native-menu-probe", productName: "SpireShift Menu Qualification",
      productVersion: "1"
    });
    await session.register(capabilities.host, capabilities.control);
    const credentials = await session.credentials();
    const request = {
      requestId: `spireshift-menu-${randomUUID()}`, expectedSnapshotId: initial.snapshot_id,
      boundActionId: action.bound_action_id, ...credentials
    };
    result.menu_actions_requested = 1;
    const receipt = (await client.submit(request)).data;
    result.receipt = receipt;
    if (receipt.delivery !== "delivered") {
      throw new Error(`Menu delivery ${receipt.delivery}; do not retry an uncertain action`);
    }
    const duplicate = (await client.submit(request)).data;
    result.duplicate_receipt = duplicate;
    result.checks.duplicate_idempotent = duplicate.request_id === receipt.request_id
      && duplicate.delivery === receipt.delivery
      && duplicate.action.bound_action_id === receipt.action.bound_action_id
      && duplicate.attribution?.runtime_instance_id === runtimeId;
    let successor = receipt.successor;
    while (Date.now() < deadline && !completedTransition(initial, successor, receipt, runtimeId)) {
      successor = (await client.observe()).data;
      result.latest_snapshot = successor;
      await pause(100);
    }
    result.successor_snapshot = successor;
    result.checks.completed_menu_transition = completedTransition(initial, successor, receipt, runtimeId);
    if (!result.checks.completed_menu_transition) throw new Error("Delivered action has no completed menu transition");
    const stale = (await client.submit({ ...request, requestId: `spireshift-stale-${randomUUID()}` })).data;
    result.stale_receipt = stale;
    result.checks.stale_rejected = stale.delivery === "not_delivered"
      && stale.reason_code === "stale_snapshot" && stale.retry.allowed === true
      && stale.retry.reason === "fresh_snapshot_required";
  } catch (error) {
    result.error = String(error.message);
  } finally {
    if (session) await session.close();
    if (runtimeId) {
      try {
        const response = await fetch(`${spec.endpoint}/api/host-control/shutdown`, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ expected_runtime_instance_id: runtimeId, host_control_token: spec.host_control_token }),
          signal: AbortSignal.timeout(3_000)
        });
        const body = await response.json();
        result.shutdown_requested = response.ok && body.status === "shutdown_requested";
      } catch (error) { result.shutdown_error = String(error.message); }
    }
    result.wall_seconds = (Date.now() - started) / 1_000;
    writeFileSync(path.join(spec.attempt, "menu-control.json"), `${JSON.stringify(result, null, 2)}\n`);
  }
}

async function main() {
  const spec = await readSpec();
  if (process.argv.includes("--install")) {
    const { installRelease } = await import(pathToFileURL(path.join(spec.toolchain,
      "release/tools/install-release.mjs")).href);
    const result = installRelease({ releaseRoot: path.join(spec.toolchain, "release"),
      gameDir: spec.game, backupRoot: path.join(spec.attempt, "connector-installation-backup") });
    console.log(JSON.stringify(result));
    return;
  }
  await menuProbe(spec);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => { console.error(error.message); process.exitCode = 1; });
}
