using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Actions;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;

// Acceptance is either a native assigned ID or this exact object in the original
// synchronizer's deferred list. Never manufacture an ID or bypass RequestEnqueue.
internal static class DeferredPotions
{
    private const BindingFlags Fields = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
    private static FieldInfo Pending = null!, Waiting = null!;
    private static MethodInfo Queued = null!, Wait = null!, Observe = null!, Matches = null!, NativeId = null!;
    private static string OwnHash = "";

    [ModuleInitializer]
    internal static void Install()
    {
        var host = Assembly.GetEntryAssembly() ?? throw new InvalidOperationException("Missing native host");
        string Hash(Assembly a) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(a.Location)));
        if (Hash(host) != "8e0aba9e9c1f0e9eebfcf8238ba01a274a0c7d4920ae345d9efcd281615b1665"
            || Hash(typeof(CardModel).Assembly) != "9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4")
            throw new InvalidOperationException("Deferred potion acknowledgement requires frozen host60/game");
        OwnHash = Hash(typeof(DeferredPotions).Assembly);
        var simulator = host.GetType("Sts2Headless.RunSimulator", true)!;
        MethodInfo Method(string name) => simulator.GetMethod(name, Fields) ?? throw new MissingMethodException(name);
        Pending = simulator.GetField("_queuedPotionDiscards", Fields) ?? throw new MissingFieldException("discard ledger");
        Waiting = typeof(ActionQueueSynchronizer).GetField("_requestedActionsWaitingForPlayerTurn", Fields)
            ?? throw new MissingFieldException("native deferred list");
        Queued = Method("IsPotionDiscardQueued"); Wait = Method("WaitForNativeCommit"); Observe = Method("DetectDecisionPoint");
        var identity = host.GetType("Sts2Headless.NativeObjectIdentity", true)!;
        Matches = identity.GetMethod("Matches", BindingFlags.Public | BindingFlags.Static)!;
        NativeId = identity.GetMethod("Get", BindingFlags.Public | BindingFlags.Static)!;
        HarmonyMethod Hook(string name) => new(typeof(DeferredPotions).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)!);
        var harmony = new Harmony("spireshift.headless.deferred-potions.v1");
        var discard = Hook(nameof(Discard)); discard.priority = Priority.First;
        harmony.Patch(Method("DoDiscardPotion"), prefix: discard);
        harmony.Patch(Method("GetRunIdentity"), postfix: Hook(nameof(Identify)));
    }

    private static List<GameAction> Buffer => (List<GameAction>)Waiting.GetValue(RunManager.Instance.ActionQueueSynchronizer)!;
    private static bool Buffered(GameAction action) => Buffer.Any(item => ReferenceEquals(item, action));
    private static bool Accepted(GameAction action) =>
        action.Id.HasValue && action.State != GameActionState.None && action.State != GameActionState.Canceled
        || !action.Id.HasValue && action.State == GameActionState.None && Buffered(action);

    private static bool Discard(object __instance, Player player, Dictionary<string, object?>? args,
        ref Dictionary<string, object?> __result)
    {
        Dictionary<string, object?> Error(string message) => new() { ["type"] = "error", ["message"] = message };
        if (!PotionQueueEligibility.Allows(RunManager.Instance.ActionQueueSet, player.NetId, CombatManager.Instance.IsInProgress))
        { __result = Error("Potion action is not accepted by the current native queue"); return false; }
        if (args == null || !args.ContainsKey("potion_slot") || !args.ContainsKey("potion_ref"))
        { __result = Error("discard_potion requires 'potion_slot' and 'potion_ref'"); return false; }
        var slot = Convert.ToInt32(args["potion_slot"]);
        PotionModel? potion;
        try { potion = player.GetPotionAtSlotIndex(slot); }
        catch (IndexOutOfRangeException) { __result = Error($"Invalid potion slot {slot}"); return false; }
        if (potion == null || !(bool)Matches.Invoke(null, new[] { potion, args["potion_ref"] })!)
        { __result = Error("The observed potion is no longer in the bound belt slot"); return false; }
        if (!ReferenceEquals(potion.Owner, player) || !player.CanUseOrRemovePotions || potion.IsQueued
            || (bool)Queued.Invoke(__instance, new object[] { potion })!)
        { __result = Error($"Potion {potion.Id.Entry} is no longer natively discardable"); return false; }
        var action = new DiscardPotionGameAction(player, (uint)slot, CombatManager.Instance.IsInProgress);
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(action);
        if (!Accepted(action))
        { __result = Error("Native potion discard acceptance was not confirmed"); return false; }
        var pending = (Dictionary<PotionModel, DiscardPotionGameAction>)Pending.GetValue(__instance)!;
        pending.Add(potion, action);
        Wait.Invoke(__instance, null);
        if (!player.PotionSlots.Contains(potion)) pending.Remove(potion);
        else if (!(bool)Queued.Invoke(__instance, new object[] { potion })!
            || !(Buffered(action) || action.State == GameActionState.WaitingForExecution))
        { __result = Error($"Potion discard delivery is unknown because the exact potion remains in slot {slot}"); return false; }
        __result = (Dictionary<string, object?>)Observe.Invoke(__instance, null)!;
        return false;
    }

    private static void Identify(object __instance, Dictionary<string, object?> __result)
    {
        var pending = (Dictionary<PotionModel, DiscardPotionGameAction>)Pending.GetValue(__instance)!;
        __result["deferred_potions_adapter_sha256"] = OwnHash;
        var synchronizer = RunManager.Instance.ActionQueueSynchronizer;
        __result["deferred_potions"] = new Dictionary<string, object?>
        {
            ["combat_state"] = synchronizer?.CombatState.ToString(),
            ["buffer"] = (synchronizer == null ? new List<GameAction>() : Buffer).Select(action => new Dictionary<string, object?>
            {
                ["kind"] = action.GetType().Name, ["action_id"] = action.Id,
                ["state"] = action.State.ToString(), ["owner_id"] = action.OwnerId,
                ["tracked_discard"] = pending.Any(pair => ReferenceEquals(pair.Value, action)),
            }).ToArray(),
        };
    }
}
