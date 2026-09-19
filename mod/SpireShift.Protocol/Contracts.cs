using System.Text.Json.Serialization;

namespace SpireShift.Protocol;

public sealed record ObservationV1(
    [property: JsonPropertyName("schema_version")] string SchemaVersion,
    [property: JsonPropertyName("patch_id")] string PatchId,
    [property: JsonPropertyName("decision_type")] string DecisionType,
    [property: JsonPropertyName("public_state")] IReadOnlyDictionary<string, object?> PublicState,
    [property: JsonPropertyName("state_hash")] string StateHash);

public sealed record LegalActionV1(
    [property: JsonPropertyName("action_id")] string ActionId,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("payload")] IReadOnlyDictionary<string, object?> Payload);

public sealed record ObjectiveSpecV1(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("primary")] string Primary,
    [property: JsonPropertyName("constraint")] string Constraint,
    [property: JsonPropertyName("whole_run_budget")] long WholeRunBudget,
    [property: JsonPropertyName("auxiliary")] IReadOnlyList<string> Auxiliary,
    [property: JsonPropertyName("auxiliary_reward_allowed")] bool AuxiliaryRewardAllowed)
{
    public void Validate()
    {
        if (Primary != "terminal_victory")
            throw new InvalidOperationException("Primary objective must be terminal_victory.");
        if (Constraint != "cpu_time_per_run")
            throw new InvalidOperationException("A whole-run compute constraint is required.");
        if (WholeRunBudget <= 0)
            throw new InvalidOperationException("Whole-run budget must be positive.");
        if (AuxiliaryRewardAllowed)
            throw new InvalidOperationException("Auxiliary metrics cannot contribute to reward.");
    }
}
