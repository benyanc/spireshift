using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using HarmonyLib;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Runs;
using Sts2Headless;

internal static class BossMapTravel
{
    [ModuleInitializer]
    internal static void Initialize()
    {
        if (Assembly.GetEntryAssembly()?.GetName().Name != "Sts2Headless")
            throw new InvalidOperationException("Boss map adapter requires the frozen headless host");
        var library = Environment.GetEnvironmentVariable("STS2_LIB")
            ?? throw new InvalidOperationException("Frozen library directory is missing");
        AssemblyLoadContext.Default.Resolving += (context, name) =>
        {
            var path = Path.Combine(library, name.Name + ".dll");
            return File.Exists(path) ? context.LoadFromAssemblyPath(Path.GetFullPath(path)) : null;
        };
        Install();
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void Install()
    {
        const BindingFlags instance = BindingFlags.Instance | BindingFlags.NonPublic;
        var mapChoices = typeof(RunSimulator).GetMethod("CurrentTravelableMapPoints", instance)
            ?? throw new MissingMethodException(nameof(RunSimulator), "CurrentTravelableMapPoints");
        var prefix = AccessTools.Method(typeof(BossMapTravel), nameof(TravelableBoss));
        new Harmony("spireshift.headless.boss-map.v1").Patch(mapChoices, prefix: new(prefix));
    }

    private static bool TravelableBoss(RunState? ____runState, ref IReadOnlyList<MapPoint> __result)
    {
        if (____runState?.Map is not { } map || ____runState.CurrentMapCoord is not { } current)
            return true;

        // The shipped NMapScreen resolves these destinations before free travel.
        if (map.SecondBossMapPoint is { } secondBoss && current == map.BossMapPoint.coord)
        {
            __result = [secondBoss];
            return false;
        }
        if (current.row == map.GetRowCount() - 1)
        {
            __result = [map.BossMapPoint];
            return false;
        }
        return true;
    }
}
