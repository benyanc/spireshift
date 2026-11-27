// Invoke the actual reproduced assemblies without starting a run, UI or game.
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;

using JsonDocument input = JsonDocument.Parse(Console.In.ReadToEnd());
JsonElement spec = input.RootElement;
const BindingFlags StaticMethod = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
var identities = new List<object>();
var texts = new List<object>();
foreach (JsonElement entry in spec.GetProperty("native_assemblies").EnumerateArray())
{
    string path = entry.GetString()!;
    var context = new ProbeContext(path, spec.GetProperty("game_data").GetString()!);
    Assembly assembly = context.LoadFromAssemblyPath(path);
    MethodInfo method = assembly.GetType("Sts2Headless.RunSimulator", true)!
        .GetMethod("StripVisibleText", StaticMethod)!;
    var results = new List<object>();
    foreach (JsonElement value in spec.GetProperty("text_cases").EnumerateArray())
    {
        try
        {
            object? result = method.Invoke(null, new object?[] { value.ValueKind == JsonValueKind.Null ? null : value.GetString() });
            results.Add(new { value = result, error = (string?)null });
        }
        catch (TargetInvocationException error)
        {
            results.Add(new { value = (string?)null, error = error.InnerException!.GetType().FullName });
        }
    }
    identities.Add(new { path, mvid = assembly.ManifestModule.ModuleVersionId.ToString() });
    texts.Add(results);
    context.Unload();
}

string hostPath = spec.GetProperty("host_assembly").GetString()!;
var hostContext = new ProbeContext(hostPath, spec.GetProperty("game_data").GetString()!);
Assembly host = hostContext.LoadFromAssemblyPath(hostPath);
MethodInfo officialTextMethod = host.GetType("STS2Connector.ConnectorMod", true)!
    .GetMethod("StripRichTextTags", StaticMethod)!;
var officialTexts = new List<object?>();
foreach (JsonElement value in spec.GetProperty("text_cases").EnumerateArray())
    officialTexts.Add(value.ValueKind == JsonValueKind.Null ? null :
        officialTextMethod.Invoke(null, new object[] { value.GetString()! }));
Type guard = host.GetType("STS2Connector.NativeUi.NativeTutorialEntryTransition", true)!;
MethodInfo pendingMethod = guard.GetMethod("EntryIsPending", StaticMethod)!;
MethodInfo readinessMethod = guard.GetMethod("ApplyReadiness", StaticMethod)!;
MethodInfo authorityMethod = host.GetType("STS2Connector.PlayerEnvironment.PlayerEnvironmentService", true)!
    .GetMethod("CanPublishMutationAuthority", StaticMethod)!;
MethodInfo statusMethod = host.GetType("STS2Connector.NativeUi.NativeMapTransition", true)!
    .GetMethod("SnapshotStatus", StaticMethod)!;
var entries = new List<object>();
foreach (JsonElement entry in spec.GetProperty("entry_cases").EnumerateArray())
{
    var arguments = new List<object?> { entry.GetProperty("tutorial_id").GetString() };
    foreach (string key in new[] { "traveling", "map_open", "combat_room", "context_known", "starting",
        "in_progress", "has_combat_state", "live_room", "live_hand", "native_play_phase" })
        arguments.Add(entry.GetProperty(key).GetBoolean());
    bool pending = (bool)pendingMethod.Invoke(null, arguments.ToArray())!;
    string readiness = (string)readinessMethod.Invoke(null, new object[] { entry.GetProperty("readiness").GetString()!, pending })!;
    bool authority = (bool)authorityMethod.Invoke(null, new object[] { readiness })!;
    string status = (string)statusMethod.Invoke(null, new object[] { pending, authority, false, readiness })!;
    entries.Add(new { key = entry.GetProperty("key").GetString(), pending, readiness, authority, status });
}
identities.Add(new { path = hostPath, mvid = host.ManifestModule.ModuleVersionId.ToString() });
Console.WriteLine(JsonSerializer.Serialize(new { identities, text_results = texts, official_text_results = officialTexts, entry_results = entries }));

sealed class ProbeContext : AssemblyLoadContext
{
    private readonly string[] directories;
    public ProbeContext(string assembly, string gameData) : base(isCollectible: true)
    {
        directories = new[] { Path.GetDirectoryName(assembly)!, gameData };
    }
    protected override Assembly? Load(AssemblyName name)
    {
        foreach (string directory in directories)
        {
            string path = Path.Combine(directory, name.Name + ".dll");
            if (File.Exists(path)) return LoadFromAssemblyPath(path);
        }
        return null;
    }
}
