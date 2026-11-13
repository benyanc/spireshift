using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;

var candidate = Path.GetFullPath(args[0]);
var output = Path.Combine(candidate, "src/Sts2Headless/bin/Release/net9.0");
var hostPath = Path.Combine(output, "Sts2Headless.dll");
var gamePath = Path.Combine(candidate, "lib/sts2.dll");
var context = new AssemblyLoadContext("isolated_canvas_item_probe", true);
context.Resolving += (loadContext, name) =>
{
    foreach (var directory in new[] { output, Path.Combine(candidate, "lib") })
    {
        var path = Path.Combine(directory, name.Name + ".dll");
        if (File.Exists(path))
            return loadContext.LoadFromAssemblyPath(path);
    }
    return null;
};
var stub = context.LoadFromAssemblyPath(Path.Combine(output, "GodotSharp.dll"));
var game = context.LoadFromAssemblyPath(gamePath);
var item = stub.GetType("Godot.CanvasItem", true)!;
var color = stub.GetType("Godot.Color", true)!;
var setter = item.GetMethod("SetSelfModulate", new[] { color });
var setterSemantics = false;
if (setter is not null)
{
    var instance = Activator.CreateInstance(item)!;
    var sibling = Activator.CreateInstance(item)!;
    var tint = Activator.CreateInstance(color, 0.25f, 0.5f, 0.75f, 0.5f)!;
    var localColor = item.GetProperty("SelfModulate")!;
    var inheritedColor = item.GetProperty("Modulate")!;
    var initial = localColor.GetValue(instance);
    setter.Invoke(instance, new[] { tint });
    setterSemantics = setter.ReturnType == typeof(void) && !setter.IsStatic
        && Equals(localColor.GetValue(instance), tint)
        && Equals(inheritedColor.GetValue(instance), initial)
        && Equals(localColor.GetValue(sibling), initial);
    if (!setterSemantics)
        throw new InvalidOperationException("CanvasItem setter semantics differ from the local tint contract");
}

var subject = game.GetType("MegaCrit.Sts2.Core.Models.Monsters.TestSubject", true)!;
var methods = new[] { "SetColor", "AfterPowerApplied", "AfterPowerRemoved", "BeforeDeath" };
var prepared = new Dictionary<string, string?>();
foreach (var name in methods)
{
    var method = subject.GetMethod(name, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
    if (method is null || method.DeclaringType != subject)
        continue;
    try
    {
        RuntimeHelpers.PrepareMethod(method.MethodHandle);
        prepared[name] = null;
    }
    catch (MissingMethodException error)
    {
        prepared[name] = error.Message;
    }
}

// A member-reference table scan does not execute native hooks or claim scene behavior.
// Generic TypeSpec targets and late-bound calls are outside this measured scope.
using var gameStream = File.OpenRead(gamePath);
using var gamePe = new PEReader(gameStream);
var metadata = gamePe.GetMetadataReader();
bool GodotScope(EntityHandle handle)
{
    while (handle.Kind == HandleKind.TypeReference)
        handle = metadata.GetTypeReference((TypeReferenceHandle)handle).ResolutionScope;
    return handle.Kind == HandleKind.AssemblyReference
        && metadata.GetString(metadata.GetAssemblyReference((AssemblyReferenceHandle)handle).Name) == "GodotSharp";
}
var checkedMethods = 0;
var unresolved = new SortedDictionary<string, string>();
foreach (var handle in metadata.MemberReferences)
{
    var member = metadata.GetMemberReference(handle);
    if (member.GetKind() != MemberReferenceKind.Method || member.Parent.Kind != HandleKind.TypeReference
        || !GodotScope(member.Parent))
        continue;
    checkedMethods++;
    var token = MetadataTokens.GetToken(handle);
    try
    {
        game.ManifestModule.ResolveMethod(token);
    }
    catch (Exception error) when (error is MissingMethodException or TypeLoadException or FileNotFoundException or ArgumentException)
    {
        unresolved.Add(token.ToString("X8"), error.Message);
    }
}
using var hostStream = File.OpenRead(hostPath);
using var hostPe = new PEReader(hostStream);
var hostMetadata = hostPe.GetMetadataReader();
Console.WriteLine(JsonSerializer.Serialize(new
{
    artifact_sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(hostPath))).ToLowerInvariant(),
    artifact_mvid = hostMetadata.GetGuid(hostMetadata.GetModuleDefinition().Mvid).ToString(),
    setter_present = setter is not null,
    setter_semantics = setterSemantics,
    test_subject_jit = prepared,
    godot_method_references_checked = checkedMethods,
    unresolved,
    game_commands = 0,
}));
