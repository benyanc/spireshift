using System.Diagnostics;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using HarmonyLib;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using Sts2Headless;

internal static class StartupHook
{
    public static void Initialize()
    {
        var host = Assembly.GetEntryAssembly()
            ?? throw new InvalidOperationException("Headless entry assembly is missing");
        if (host.GetName().Name != "Sts2Headless")
            throw new InvalidOperationException("This adapter requires the frozen headless host");
        var lib = Environment.GetEnvironmentVariable("STS2_LIB")
            ?? throw new InvalidOperationException("Frozen library directory is missing");
        AssemblyLoadContext.Default.Resolving += (context, name) =>
        {
            var path = Path.Combine(lib, name.Name + ".dll");
            return File.Exists(path) ? context.LoadFromAssemblyPath(Path.GetFullPath(path)) : null;
        };
        Install();
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void Install() => AbandonConfirmation.Install();
}

internal static class AbandonConfirmation
{
    private sealed record Pending(RunState Run, Trial Owner, string Reference);

    private const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;
    private static readonly MethodInfo Abandon = RequireMethod(typeof(RunManager), "AbandonInternal");
    private static readonly MethodInfo CloseCapstone = RequireMethod(typeof(NCapstoneContainer), "Close");
    private static readonly MethodInfo CloseMap = RequireMethod(typeof(NMapScreen), "Close", typeof(bool));
    private static readonly string AdapterHash = Convert.ToHexStringLower(
        SHA256.HashData(File.ReadAllBytes(typeof(AbandonConfirmation).Assembly.Location)));
    private static Pending? _pending;
    private static long _serial;

    public static void Install()
    {
        var patches = new Harmony("spireshift.headless.abandon-confirmation.v1");
        var abandonStateMachine = Abandon.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Native abandon task shape changed");
        patches.Patch(RequireMethod(abandonStateMachine, "MoveNext"), transpiler: Patch(nameof(SkipMissingScreens)));
        patches.Patch(RequireMethod(typeof(Trial), "DoubleDown"), prefix: Patch(nameof(Open)));
        patches.Patch(RequireMethod(typeof(RunSimulator), "DetectDecisionPoint"), postfix: Patch(nameof(Show)));
        patches.Patch(RequireMethod(typeof(RunSimulator), "ExecuteAction", typeof(string), typeof(Dictionary<string, object?>)),
            prefix: Patch(nameof(Resolve)));
        patches.Patch(RequireMethod(typeof(RunSimulator), "GetRunIdentity"), postfix: Patch(nameof(Identify)));
        patches.Patch(RequireMethod(typeof(RunSimulator), "CleanUp"), prefix: Patch(nameof(Clear)));
    }

    private static MethodInfo RequireMethod(Type owner, string name, params Type[] arguments) =>
        owner.GetMethod(name, BindingFlags.Public | Private, null, arguments, null)
        ?? throw new MissingMethodException(owner.FullName, name);

    private static HarmonyMethod Patch(string name) =>
        new(typeof(AbandonConfirmation).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingMethodException(typeof(AbandonConfirmation).FullName, name));

    private static bool Open(Trial __instance, ref Task __result)
    {
        if (!TestMode.IsOn) return true;
        var manager = RunManager.Instance;
        var state = manager.DebugOnlyGetState();
        if (_pending != null || state == null || manager.IsGameOver
            || manager.NetService.Type != NetGameType.Singleplayer
            || !ReferenceEquals(manager.EventSynchronizer.GetLocalEvent(), __instance))
            throw new InvalidOperationException("Abandon confirmation needs its current event and run");

        _pending = new Pending(state, __instance, $"abandon-{Interlocked.Increment(ref _serial)}");
        __result = Task.CompletedTask;
        return false;
    }

    private static bool Current(Pending pending, RunManager manager) =>
        ReferenceEquals(pending.Run, manager.DebugOnlyGetState()) && !manager.IsGameOver
        && ReferenceEquals(pending.Owner, manager.EventSynchronizer.GetLocalEvent());

    private static void Show(Dictionary<string, object?> __result)
    {
        if (_pending is not { } pending || __result.GetValueOrDefault("type") as string == "error") return;
        if (!Current(pending, RunManager.Instance)
            || __result.GetValueOrDefault("decision") as string != "event_choice"
            || __result.GetValueOrDefault("event_id") as string != "TRIAL")
            throw new InvalidOperationException("Abandon confirmation lost its event owner");

        __result["event_id"] = "ABANDON_RUN_CONFIRMATION";
        __result["event_name"] = Text("ABANDON_RUN_CONFIRMATION.header");
        __result["description"] = Text("ABANDON_RUN_CONFIRMATION.body");
        __result["abandon_confirmation_ref"] = pending.Reference;
        __result["options"] = new[] { Option(0, "confirm"), Option(1, "cancel") };
    }

    private static Dictionary<string, object?> Option(int index, string option)
    {
        var key = "GENERIC_POPUP." + option;
        return new Dictionary<string, object?>
        {
            ["index"] = index,
            ["title"] = Text(key),
            ["text_key"] = key,
            ["is_locked"] = false,
            ["is_proceed"] = false,
            ["was_chosen"] = false,
            ["will_kill_player"] = index == 0,
            ["relic_name"] = null,
            ["relic_description"] = null,
            ["tooltips"] = Array.Empty<object>(),
        };
    }

    private static string Text(string key) => new LocString("main_menu_ui", key).GetFormattedText();

    private static bool Resolve(RunSimulator __instance, string action, Dictionary<string, object?>? args,
        ref Dictionary<string, object?> __result)
    {
        const string resolve = "resolve_abandon_confirmation";
        if (_pending == null && action != resolve) return true;
        var manager = RunManager.Instance;
        if (_pending is not { } pending || action != resolve || !Current(pending, manager)
            || args?.GetValueOrDefault("confirmation_ref") as string != pending.Reference
            || args.GetValueOrDefault("confirm") is not bool confirm)
        {
            __result = new() { ["type"] = "error", ["message"] = "Stale or unrelated abandon confirmation action" };
            return false;
        }

        _pending = null;
        if (confirm)
        {
            // The native single-player popup calls RunManager.Abandon, which starts
            // this task. Observe the task itself so a partial abandonment cannot settle.
            var task = (Task)(Abandon.Invoke(manager, null)
                ?? throw new InvalidOperationException("Native abandon task is missing"));
            var sync = typeof(RunSimulator).GetField("_syncCtx", BindingFlags.NonPublic | BindingFlags.Static)
                ?.GetValue(null) ?? throw new InvalidOperationException("Headless synchronization context is missing");
            var pump = RequireMethod(sync.GetType(), "Pump");
            var watch = Stopwatch.StartNew();
            while (!task.IsCompleted && watch.Elapsed.TotalSeconds < 5)
            {
                pump.Invoke(sync, null);
                Thread.Sleep(1);
            }
            if (!task.IsCompleted) throw new TimeoutException("Native abandon did not finish");
            task.GetAwaiter().GetResult();
            if (!manager.IsAbandoned || !manager.IsGameOver
                || pending.Run.CurrentRoom?.IsVictoryRoom == true)
                throw new InvalidOperationException("Native abandon did not reach a confirmed loss");
        }

        __result = __instance.Observe();
        return false;
    }

    private static void Identify(Dictionary<string, object?> __result)
    {
        __result["confirmation_adapter_sha256"] = AdapterHash;
        __result["pending_abandon_confirmation"] = _pending != null;
        __result["native_abandoned"] = RunManager.Instance.IsAbandoned;
    }

    private static void Clear() => _pending = null;

    private static IEnumerable<CodeInstruction> SkipMissingScreens(IEnumerable<CodeInstruction> instructions)
    {
        int capstone = 0, map = 0;
        foreach (var code in instructions)
        {
            if (code.opcode == OpCodes.Callvirt && Equals(code.operand, CloseCapstone))
            {
                code.opcode = OpCodes.Call;
                code.operand = Patch(nameof(CloseCapstoneIfPresent)).method;
                capstone++;
            }
            else if (code.opcode == OpCodes.Callvirt && Equals(code.operand, CloseMap))
            {
                code.opcode = OpCodes.Call;
                code.operand = Patch(nameof(CloseMapIfPresent)).method;
                map++;
            }
            yield return code;
        }
        if (capstone != 1 || map != 1) throw new InvalidOperationException("Native abandon screen calls changed");
    }

    private static void CloseCapstoneIfPresent(NCapstoneContainer? screen)
    {
        if (screen != null || !TestMode.IsOn) screen!.Close();
    }

    private static void CloseMapIfPresent(NMapScreen? screen, bool animateOut)
    {
        if (screen != null || !TestMode.IsOn) screen!.Close(animateOut);
    }
}
