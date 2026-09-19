namespace SpireShift.Protocol;

public sealed record ObservationV1(
    string SchemaVersion,
    string PatchId,
    string DecisionType,
    IReadOnlyDictionary<string, object?> PublicState,
    string StateHash);

public sealed record LegalActionV1(
    string ActionId,
    string Kind,
    IReadOnlyDictionary<string, object?> Payload);

public sealed record ObjectiveSpecV1(
    string Id,
    string Primary,
    string Constraint,
    long WholeRunBudget,
    IReadOnlyList<string> Auxiliary,
    bool AuxiliaryRewardAllowed)
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
