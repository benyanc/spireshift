using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;

// The linked, unchanged StartupHook retains the qualified card-frame cleanup.
// This module adds only the real merchant room's target lifetime under the map.
internal static class MerchantOverlay
{
    private const BindingFlags Fields = BindingFlags.Instance | BindingFlags.NonPublic;
    private const BindingFlags Static = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    private const string GameHash = "9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4";
    private const string HostHash = "8e0aba9e9c1f0e9eebfcf8238ba01a274a0c7d4920ae345d9efcd281615b1665";
    private static Type Simulator = null!;
    private static FieldInfo Run = null!, Selector = null!, Bundles = null!, Pending = null!;
    private static PropertyInfo MapOpen = null!;
    private static MethodInfo Refresh = null!, Target = null!, NativeId = null!, OriginalBinding = null!;
    private static string OwnHash = "";

    [ModuleInitializer]
    internal static void Install()
    {
        var host = Assembly.GetEntryAssembly() ?? throw new InvalidOperationException("Missing native host");
        string Hash(Assembly assembly) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(assembly.Location)));
        if (Hash(host) != HostHash || Hash(typeof(CardModel).Assembly) != GameHash)
            throw new InvalidOperationException("Merchant overlay requires the frozen host60 and original game");
        OwnHash = Hash(typeof(MerchantOverlay).Assembly);
        Simulator = host.GetType("Sts2Headless.RunSimulator", true)!;
        FieldInfo Field(string name) => Simulator.GetField(name, Fields) ?? throw new MissingFieldException(name);
        MethodInfo Method(string name) => Simulator.GetMethod(name, Fields | BindingFlags.Public) ?? throw new MissingMethodException(name);
        Run = Field("_runState");
        MapOpen = Simulator.GetProperty("_mapPresentationOpen", Fields) ?? throw new MissingMemberException("_mapPresentationOpen");
        Selector = Field("_cardSelector");
        Bundles = Field("_pendingBundles"); Pending = Field("_pendingHostOperation");
        if (MapOpen.PropertyType != typeof(bool) || Run.FieldType != typeof(RunState))
            throw new InvalidOperationException("Merchant host field types changed");
        var presentation = Simulator.GetNestedType("HeadlessMerchantPresentation", BindingFlags.NonPublic)!;
        Refresh = presentation.GetMethod("Refresh", Static)!;
        Target = presentation.GetMethod("CurrentTarget", Static)!;
        NativeId = host.GetType("Sts2Headless.NativeObjectIdentity", true)!.GetMethod("Get", Static)!;
        OriginalBinding = Method("CurrentMerchantBinding");
        var harmony = new Harmony("spireshift.headless.merchant-overlay.v2");
        HarmonyMethod Hook(string name) => new(typeof(MerchantOverlay).GetMethod(name, Static)!);
        harmony.Patch(Method("MapSelectState"), prefix: Hook(nameof(BeforeMap)), postfix: Hook(nameof(ExportMap)));
        harmony.Patch(Method("DoUsePotion"), transpiler: Hook(nameof(PotionBinding)));
        harmony.Patch(Method("GetRunIdentity"), postfix: Hook(nameof(Identify)));
    }

    private static bool Eligible(object simulator, out MerchantRoom? room)
    {
        room = (Run.GetValue(simulator) as RunState)?.CurrentRoom as MerchantRoom;
        if (room == null || MapOpen.GetValue(simulator) is not true
            || RunManager.Instance.IsGameOver || CombatManager.Instance.IsInProgress) return false;
        var selector = Selector.GetValue(simulator) ?? throw new InvalidOperationException("Missing native selector");
        bool Flag(string name) => (bool)(selector.GetType().GetProperty(name) ?? throw new MissingMemberException(name)).GetValue(selector)!;
        return !Flag("HasPending") && !Flag("HasPendingReward") && Bundles.GetValue(simulator) == null
            && Pending.GetValue(simulator) is not Task { IsCompleted: false };
    }

    private static void BeforeMap(object __instance)
    {
        if (Eligible(__instance, out var room)) Refresh.Invoke(null, new object?[] { room, true });
    }

    private static string Id(object value) => (string)NativeId.Invoke(null, new[] { value })!;

    private static void ExportMap(object __instance, Dictionary<string, object?> __result)
    {
        if (!Eligible(__instance, out var room) || __result.GetValueOrDefault("decision") is not "map_select") return;
        var target = (ITuple)Target.Invoke(null, new object?[] { room })!;
        if (target[0] == null) return; // An open inventory still forbids this target.
        __result["merchant_map_target"] = new Dictionary<string, object?> {
            ["contract"] = "native_current_merchant_room_under_map_v1",
            ["room_ref"] = Id(room!), ["merchant_ref"] = Id(target[0]!), ["inventory_open"] = false };
    }

    private static bool PotionRoomBinding(object simulator, Dictionary<string, object?>? args)
    {
        if ((bool)OriginalBinding.Invoke(simulator, new object?[] { args })!) return true;
        return Eligible(simulator, out var room) && args?.GetValueOrDefault("room_ref") is string expected
            && Id(room!) == expected && ((ITuple)Target.Invoke(null, new object?[] { room })!)[0] != null;
    }

    private static IEnumerable<CodeInstruction> PotionBinding(IEnumerable<CodeInstruction> instructions)
    {
        var body = instructions.ToList();
        if (body.Count(code => code.Calls(OriginalBinding)) != 1)
            throw new InvalidOperationException("Native potion room-binding call changed");
        var replacement = typeof(MerchantOverlay).GetMethod(nameof(PotionRoomBinding), Static)!;
        foreach (var code in body)
        {
            if (code.Calls(OriginalBinding)) { code.opcode = System.Reflection.Emit.OpCodes.Call; code.operand = replacement; }
            yield return code;
        }
    }

    private static void Identify(Dictionary<string, object?> __result) => __result["merchant_overlay_adapter_sha256"] = OwnHash;
}
