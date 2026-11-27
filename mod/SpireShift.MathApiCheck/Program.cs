// Read-only numerical control against the owner's shipped library. Never starts a game.
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;

if (args.Length != 2) throw new ArgumentException("Pass original and candidate GodotSharp assemblies");
var reference = new AssemblyLoadContext("original-math", isCollectible: true)
    .LoadFromAssemblyPath(Path.GetFullPath(args[0])).GetType("Godot.Mathf", throwOnError: true)!;
var candidate = new AssemblyLoadContext("candidate-math", isCollectible: true)
    .LoadFromAssemblyPath(Path.GetFullPath(args[1])).GetType("Godot.Mathf", throwOnError: true)!;
var checks = new List<object>();
var failures = new List<string>();
foreach (var (name, type) in new[] { ("Log", typeof(float)), ("Log", typeof(double)), ("Sign", typeof(float)) })
{
    var expected = reference.GetMethod(name, BindingFlags.Static | BindingFlags.Public, new[] { type })!;
    var actual = candidate.GetMethod(name, BindingFlags.Static | BindingFlags.Public, new[] { type });
    if (actual == null || actual.ReturnType != expected.ReturnType)
    {
        failures.Add($"Signature mismatch: {type.Name} {name}");
        continue;
    }
    foreach (var input in new[] { double.NegativeInfinity, -10d, -1d, -0d, 0d, double.Epsilon,
        0.001d, 0.1d, 1d, Math.E, 10d, 1000d, 1000000d, double.PositiveInfinity, double.NaN })
    {
        object value = type == typeof(float) ? (object)(float)input : input;
        object Observe(MethodInfo method)
        {
            try
            {
                return method.Invoke(null, new[] { value }) switch
                {
                    float number => float.IsNaN(number) ? "nan" : "single:" + BitConverter.SingleToInt32Bits(number),
                    double number => double.IsNaN(number) ? "nan" : "double:" + BitConverter.DoubleToInt64Bits(number),
                    int number => "int:" + number,
                    _ => throw new InvalidOperationException("Unknown math return type")
                };
            }
            catch (TargetInvocationException error) { return "throws:" + error.InnerException!.GetType().FullName; }
        }
        var left = Observe(expected);
        var right = Observe(actual);
        var equal = Equals(left, right);
        checks.Add(new { method = name, argument = type.Name, input = value.ToString(), expected = left, actual = right, equal });
        if (!equal) failures.Add($"Numerical mismatch: {name} {value}");
    }
}
Console.WriteLine(JsonSerializer.Serialize(new { checks, failures, games_launched = 0, training_allowed = false }));
Environment.ExitCode = failures.Count == 0 ? 0 : 1;
