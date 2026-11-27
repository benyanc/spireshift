using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;

var mode = args[0];
if (mode == "fingerprint")
{
    using var stream = File.OpenRead(args[1]);
    using var pe = new PEReader(stream);
    var reader = pe.GetMetadataReader();
    Console.WriteLine(JsonSerializer.Serialize(new { mvid = reader.GetGuid(reader.GetModuleDefinition().Mvid).ToString(), sha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(args[1]))).ToLowerInvariant() }));
    return;
}
var candidate = Path.GetFullPath(args[1]);
var output = Path.Combine(candidate, "src/Sts2Headless/bin/Release/net9.0");
var context = new AssemblyLoadContext("isolated_abi_probe", true);
context.Resolving += (ctx, name) =>
{
    foreach (var dir in new[] { output, Path.Combine(candidate, "lib") })
    {
        var path = Path.Combine(dir, name.Name + ".dll");
        if (File.Exists(path)) return ctx.LoadFromAssemblyPath(path);
    }
    return null;
};
var stub = context.LoadFromAssemblyPath(Path.Combine(output, "GodotSharp.dll"));
var node = stub.GetType("Godot.Node", true)!;
var index = node.GetMethod("GetIndex", new[] { typeof(bool) });
if (mode == "api")
{
    if (index == null) throw new MissingMethodException("Godot.Node.GetIndex(Boolean)");
    if (index.ReturnType != typeof(int) || index.IsStatic || !index.GetParameters()[0].HasDefaultValue || !Equals(index.GetParameters()[0].DefaultValue, false))
        throw new Exception("Godot GetIndex ABI changed");
    var parent = Activator.CreateInstance(node)!;
    var first = Activator.CreateInstance(node)!;
    var second = Activator.CreateInstance(node)!;
    int At(object value, bool includeInternal = false) => (int)index.Invoke(value, new object[] { includeInternal })!;
    if (At(first) != -1) throw new Exception("Detached node index differs");
    var add = node.GetMethod("AddChild")!;
    var defaultMode = Enum.ToObject(node.GetNestedType("InternalMode")!, 0);
    add.Invoke(parent, new[] { first, false, defaultMode });
    add.Invoke(parent, new[] { second, false, defaultMode });
    if (At(first) != 0 || At(second) != 1 || At(second, true) != 1) throw new Exception("Ordered sibling indices differ");
    node.GetMethod("RemoveChild")!.Invoke(parent, new[] { first });
    if (At(first) != -1 || At(second) != 0) throw new Exception("Removal did not update sibling index");
    Console.WriteLine(JsonSerializer.Serialize(new { index_abi_present = true, plain_node_order_checks = 6, gameplay_commands = 0 }));
    return;
}
if (mode == "jit")
{
    var game = context.LoadFromAssemblyPath(Path.Combine(candidate, "lib/sts2.dll"));
    var method = game.GetType("MegaCrit.Sts2.Core.Models.Powers.ReattachPower", true)!.GetMethod("DoFadeOutOnAllSegments", BindingFlags.NonPublic | BindingFlags.Instance)!;
    try
    {
        RuntimeHelpers.PrepareMethod(method.MethodHandle);
        Console.WriteLine(JsonSerializer.Serialize(new { jit_prepared = true, method = method.Name, game_commands = 0 }));
    }
    catch (MissingMethodException e)
    {
        Console.WriteLine(JsonSerializer.Serialize(new { jit_prepared = false, method = method.Name, error = e.Message, game_commands = 0 }));
    }
    return;
}
throw new ArgumentException("Unknown probe mode");
