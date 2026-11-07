// Reconstruct a saved privileged shipped action chain; never launches or plays a game.
import { readFileSync } from "node:fs";
import { verifyProgressionTrace } from "./engine-progression-contract-v1.mjs";

let input = ""; for await (const chunk of process.stdin) input += chunk.toString();
const spec = JSON.parse(input);
const shipped = JSON.parse(readFileSync(spec.shipped, "utf8"));
const control = JSON.parse(readFileSync(spec.control, "utf8"));
const fixture = JSON.parse(readFileSync(spec.fixture, "utf8"));
if (JSON.stringify(shipped.probe) !== JSON.stringify(control)
    || shipped.verdict?.status !== "shipped_checkpoint_input_pass"
    || shipped.training_allowed !== false || shipped.full_run_attempts !== 0
    || Object.values(shipped.checks).some(value => value !== true)) throw Error("Changed saved shipped progression evidence");
process.stdout.write(JSON.stringify(verifyProgressionTrace(control, fixture)) + "\n");
