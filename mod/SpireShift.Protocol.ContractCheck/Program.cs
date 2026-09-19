using System.Text.Json;
using SpireShift.Protocol;

var observation = new ObservationV1(
    "observation-v1",
    "mock-v1",
    "path",
    new Dictionary<string, object?>
    {
        ["floor"] = 0,
        ["strength"] = 0,
        ["terminal"] = false,
        ["victory"] = false,
    },
    "fixture-state-hash");

var action = new LegalActionV1(
    "elite_path",
    "choose_path",
    new Dictionary<string, object?> { ["risk"] = "high" });

AssertKeys(JsonSerializer.Serialize(observation),
    "schema_version", "patch_id", "decision_type", "public_state", "state_hash");
AssertKeys(JsonSerializer.Serialize(action), "action_id", "kind", "payload");

var objective = new ObjectiveSpecV1(
    "terminal-victory-v1",
    "terminal_victory",
    "cpu_time_per_run",
    128,
    ["act_completion", "floor_reached"],
    false);
objective.Validate();
AssertKeys(JsonSerializer.Serialize(objective),
    "id", "primary", "constraint", "whole_run_budget", "auxiliary",
    "auxiliary_reward_allowed");

Console.WriteLine("C# protocol contract verified.");
return;

static void AssertKeys(string json, params string[] requiredKeys)
{
    using var document = JsonDocument.Parse(json);
    var root = document.RootElement;
    foreach (var key in requiredKeys)
    {
        if (!root.TryGetProperty(key, out _))
            throw new InvalidOperationException($"Serialized contract is missing '{key}': {json}");
    }
}
