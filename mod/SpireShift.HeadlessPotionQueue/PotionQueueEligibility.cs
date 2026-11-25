using System.Reflection;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;

// Read the original queue, without enqueueing, assigning an action ID, or changing it.
// Potion use and discard are both CombatPlayPhaseOnly in combat, NonCombat otherwise.
// A paused player-choice queue can still accept a discard; cancellation is different.
public static class PotionQueueEligibility
{
    private const BindingFlags Instance = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    private static readonly MethodInfo GetQueue = typeof(ActionQueueSet).GetMethod("GetQueue", Instance)
        ?? throw new MissingMethodException("ActionQueueSet.GetQueue");

    public static bool Allows(ActionQueueSet queues, ulong playerId, bool inCombat)
    {
        var queue = GetQueue.Invoke(queues, new object[] { playerId })
            ?? throw new InvalidOperationException("Missing native player queue");
        bool Flag(string name) => (bool)(queue.GetType().GetField(name, Instance)
            ?? throw new MissingFieldException(name)).GetValue(queue)!;
        return !inCombat || (!Flag("isCancellingPlayerDrivenCombatActions") && !Flag("isCancellingCombatActions"));
    }
}
