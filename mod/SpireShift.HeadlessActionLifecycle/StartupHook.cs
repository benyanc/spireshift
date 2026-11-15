using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using HarmonyLib;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

internal static class StartupHook
{
    public static void Initialize()
    {
        var host = Assembly.GetEntryAssembly();
        if (host?.GetName().Name != "Sts2Headless")
            throw new InvalidOperationException("Card choice cleanup requires the frozen headless host");
        // The confirmation startup hook installs the frozen library resolver first.
        CardChoiceCleanup.Install(host);
    }
}

internal static class CardChoiceCleanup
{
    private const string GameSha256 = "9cb4f1ad8c9f284aa8fec3122ffd6d780bbf543d875c817abdd12ff63fbf12b4";
    private const BindingFlags Instance = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
    private static readonly string AdapterHash = HashAssembly(typeof(CardChoiceCleanup).Assembly);

    [MethodImpl(MethodImplOptions.NoInlining)]
    public static void Install(Assembly host)
    {
        if (HashAssembly(typeof(CardModel).Assembly) != GameSha256)
            throw new InvalidOperationException("Card choice cleanup requires the original v0.111.0 assembly");
        var method = AccessTools.DeclaredMethod(typeof(CardModel), nameof(CardModel.OnPlayWrapper));
        var machine = method?.GetCustomAttribute<AsyncStateMachineAttribute>()?.StateMachineType
            ?? throw new InvalidOperationException("Native card wrapper state machine changed");
        var moveNext = machine.GetMethod("MoveNext", Instance)
            ?? throw new InvalidOperationException("Native card wrapper has no MoveNext method");
        var simulator = host.GetType("Sts2Headless.RunSimulator", throwOnError: true)!;
        var identity = simulator.GetMethod("GetRunIdentity")
            ?? throw new MissingMethodException(simulator.FullName, "GetRunIdentity");
        var harmony = new Harmony("spireshift.headless.card-choice-cleanup.v1");
        harmony.Patch(moveNext, transpiler: Hook(nameof(CompleteChoiceFrame)));
        harmony.Patch(identity, postfix: Hook(nameof(Identify)));
    }

    private static HarmonyMethod Hook(string name) =>
        new(typeof(CardChoiceCleanup).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)!);

    private static string HashAssembly(Assembly assembly) =>
        Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(assembly.Location)));

    private static void Identify(Dictionary<string, object?> __result) =>
        __result["lifecycle_adapter_sha256"] = AdapterHash;

    private static IEnumerable<CodeInstruction> CompleteChoiceFrame(
        IEnumerable<CodeInstruction> instructions, MethodBase original)
    {
        var machine = original.DeclaringType!;
        var context = machine.GetField("choiceContext", Instance);
        var card = machine.GetField("<>4__this", Instance);
        var builder = machine.GetField("<>t__builder", Instance);
        var release = AccessTools.DeclaredMethod(typeof(PlayerChoiceContext), nameof(PlayerChoiceContext.PopModel));
        var push = AccessTools.DeclaredMethod(typeof(PlayerChoiceContext), nameof(PlayerChoiceContext.PushModel));
        var complete = AccessTools.DeclaredMethod(typeof(AsyncTaskMethodBuilder), nameof(AsyncTaskMethodBuilder.SetResult));
        var body = instructions.ToList();
        int pop = UniqueCall(body, release);
        int finish = UniqueCall(body, complete);
        if (context?.FieldType != typeof(PlayerChoiceContext) || card?.FieldType != typeof(CardModel)
            || builder?.FieldType != typeof(AsyncTaskMethodBuilder) || pop < 3 || finish <= pop + 2
            || body.Count(code => code.Calls(push)) != 2
            || body[pop - 3].opcode != OpCodes.Ldarg_0
            || !body[pop - 2].LoadsField(context) || body[pop - 1].opcode != OpCodes.Ldloc_1
            || body[finish - 2].opcode != OpCodes.Ldarg_0 || !body[finish - 1].LoadsField(builder, byAddress: true)
            || body.Skip(pop - 2).Take(3).Any(IsBranchOrExceptionBoundary)
            || IsBranchOrExceptionBoundary(body[finish - 2]) || IsBranchOrExceptionBoundary(body[finish - 1])
            || IsBranchOrExceptionBoundary(body[finish]))
            throw new InvalidOperationException("Native card choice completion shape changed");

        // Successful early returns join the same task completion as ordinary card
        // plays, after EndCardOrPotionEffect has unwound. Release exactly the card
        // this invocation pushed. Await suspensions and the exception path stay native.
        body.InsertRange(finish - 2, new CodeInstruction[]
        {
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, context),
            new(OpCodes.Ldarg_0), new(OpCodes.Ldfld, card),
            new(OpCodes.Callvirt, release),
        });
        // The native optional Played callback branches to the original first load.
        body[pop - 3].opcode = OpCodes.Nop;
        body.RemoveRange(pop - 2, 3);
        return body;
    }

    private static int UniqueCall(List<CodeInstruction> body, MethodInfo method)
    {
        int index = body.FindIndex(code => code.Calls(method));
        if (index < 0 || body.FindLastIndex(code => code.Calls(method)) != index)
            throw new InvalidOperationException($"Expected one native {method.Name} call");
        return index;
    }

    private static bool IsBranchOrExceptionBoundary(CodeInstruction code) =>
        code.labels.Count != 0 || code.blocks.Count != 0;
}
