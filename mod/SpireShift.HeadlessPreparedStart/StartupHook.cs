using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using HarmonyLib;

internal static class StartupHook
{
    public static void Initialize()
    {
        var host = Assembly.GetEntryAssembly();
        if (host?.GetName().Name != "Sts2Headless")
            throw new InvalidOperationException("Prepared starts require the frozen headless host");
        // The earlier confirmation startup hook has installed the frozen library resolver.
        PreparedStart.Install(host);
    }
}

internal static class PreparedStart
{
    private static MethodInfo? _installCrystalSphere;
    private static bool _loadInitialized;
    private static readonly string AdapterHash = Convert.ToHexStringLower(
        SHA256.HashData(File.ReadAllBytes(typeof(PreparedStart).Assembly.Location)));

    [MethodImpl(MethodImplOptions.NoInlining)]
    public static void Install(Assembly host)
    {
        var simulator = host.GetType("Sts2Headless.RunSimulator", throwOnError: true)!;
        var sphere = host.GetType("Sts2Headless.HeadlessCrystalSphere", throwOnError: true)!;
        _installCrystalSphere = sphere.GetMethod("Install", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(sphere.FullName, "Install");
        var load = simulator.GetMethod("LoadSave", new[] { typeof(string), typeof(string) })
            ?? throw new MissingMethodException(simulator.FullName, "LoadSave");
        var identity = simulator.GetMethod("GetRunIdentity")
            ?? throw new MissingMethodException(simulator.FullName, "GetRunIdentity");
        var patches = new Harmony("spireshift.headless.prepared-start.v1");
        patches.Patch(load, prefix: Patch(nameof(InitializeLoad)));
        patches.Patch(identity, postfix: Patch(nameof(Identify)));
    }

    private static HarmonyMethod Patch(string name) =>
        new(typeof(PreparedStart).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingMethodException(typeof(PreparedStart).FullName, name));

    private static void InitializeLoad()
    {
        // StartRun installs this same native minigame bridge. LoadSave omits that call.
        _installCrystalSphere!.Invoke(null, null);
        _loadInitialized = true;
    }

    private static void Identify(Dictionary<string, object?> __result)
    {
        __result["prepared_start_adapter_sha256"] = AdapterHash;
        __result["prepared_load_initialized"] = _loadInitialized;
    }
}
