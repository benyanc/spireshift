namespace Sts2Headless;

// Presentation ownership only. The game's rewards synchronizer still owns every
// reward, effect and skip. A map HUD action must not reopen a dismissed screen.
internal sealed class RewardMapPresentationOwner
{
    private readonly HashSet<object> _backgroundRewards = new(ReferenceEqualityComparer.Instance);
    public bool IsOpen { get; private set; }

    public void Open(object? rewardOwner)
    {
        IsOpen = true;
        if (rewardOwner != null) _backgroundRewards.Add(rewardOwner);
    }

    public void Close()
    {
        IsOpen = false;
        _backgroundRewards.Clear();
    }

    public bool RewardIsForeground(object? rewardOwner) =>
        rewardOwner != null && (!IsOpen || !_backgroundRewards.Contains(rewardOwner));
}
