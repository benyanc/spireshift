using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;

internal static class PotionQueue
{
    private const BindingFlags Instance = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
    private const BindingFlags Static = BindingFlags.Static | BindingFlags.NonPublic;
    private static string OwnHash = "";

    [ModuleInitializer]
    internal static void Install()
    {
        string Hash(Assembly a) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(a.Location)));
        var host = Assembly.GetEntryAssembly() ?? throw new InvalidOperationException("Missing native host");
        if (Hash(host) != "8e0aba9e9c1f0e9eebfcf8238ba01a274a0c7d4920ae345d9efcd281615b1665"
            || Hash(typeof(CardModel).Assembly) != "9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4")
            throw new InvalidOperationException("Potion queue requires frozen host60 and original game");
        OwnHash = Hash(typeof(PotionQueue).Assembly);
        var simulator = host.GetType("Sts2Headless.RunSimulator", true)!;
        MethodInfo Method(string name) => simulator.GetMethod(name, Instance) ?? throw new MissingMethodException(name);
        HarmonyMethod Hook(string name) => new(typeof(PotionQueue).GetMethod(name, Static)!);
        var harmony = new Harmony("spireshift.headless.potion-queue.v1");
        harmony.Patch(Method("PlayerSummary"), postfix: Hook(nameof(Export)));
        harmony.Patch(Method("CanUsePotionNow"), postfix: Hook(nameof(UsePermission)));
        harmony.Patch(Method("DoUsePotion"), prefix: Hook(nameof(Guard)));
        harmony.Patch(Method("DoDiscardPotion"), prefix: Hook(nameof(Guard)));
        harmony.Patch(Method("GetRunIdentity"), postfix: Hook(nameof(Identify)));
    }

    private static bool Allowed(Player player) => PotionQueueEligibility.Allows(
        RunManager.Instance.ActionQueueSet, player.NetId, CombatManager.Instance.IsInProgress);

    private static void Export(Player player, Dictionary<string, object?> __result)
    {
        bool allowed = Allowed(player);
        foreach (var row in (IEnumerable<Dictionary<string, object?>>)__result["potions"]!)
        {
            row["can_use"] = row["can_use"] is true && allowed;
            row["can_discard"] = row["can_discard"] is true && allowed;
        }
    }

    private static void UsePermission(Player player, ref bool __result) => __result &= Allowed(player);

    private static bool Guard(Player player, ref Dictionary<string, object?> __result)
    {
        if (Allowed(player)) return true;
        __result = new() { ["type"] = "error", ["message"] = "Potion action is not accepted by the current native queue" };
        return false;
    }

    private static void Identify(Dictionary<string, object?> __result) => __result["potion_queue_adapter_sha256"] = OwnHash;
}
