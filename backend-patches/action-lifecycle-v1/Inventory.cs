using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

using JsonDocument input = JsonDocument.Parse(Console.In.ReadToEnd());
var result = new List<object>();
string Sha(string value) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();
string Name(InvocationExpressionSyntax call) => call.Expression switch
{
    MemberAccessExpressionSyntax m => m.Name.Identifier.ValueText,
    IdentifierNameSyntax i => i.Identifier.ValueText,
    GenericNameSyntax g => g.Identifier.ValueText,
    _ => call.Expression.ToString()
};
foreach (JsonElement source in input.RootElement.GetProperty("sources").EnumerateArray())
{
    string root = source.GetProperty("root").GetString()!;
    string layer = source.GetProperty("layer").GetString()!;
    var files = new List<object>();
    foreach (string file in Directory.EnumerateFiles(root, "*.cs", SearchOption.AllDirectories).Order(StringComparer.Ordinal))
    {
        string relative = Path.GetRelativePath(root, file);
        if (relative.Split(Path.DirectorySeparatorChar).Any(p => p is "bin" or "obj" or "out" or "tests" or "tools")) continue;
        string text = File.ReadAllText(file);
        var tree = CSharpSyntaxTree.ParseText(text);
        var errors = tree.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error).ToArray();
        if (errors.Length > 0) throw new InvalidDataException($"Cannot inventory {file}: {errors[0]}");
        var methods = new List<object>();
        foreach (MethodDeclarationSyntax method in tree.GetRoot().DescendantNodes().OfType<MethodDeclarationSyntax>())
        {
            string type = string.Join('.', method.Ancestors().OfType<BaseTypeDeclarationSyntax>().Reverse().Select(t => t.Identifier.ValueText));
            var calls = method.DescendantNodes().OfType<InvocationExpressionSyntax>().ToArray();
            var switches = new List<object>();
            foreach (SwitchStatementSyntax sw in method.DescendantNodes().OfType<SwitchStatementSyntax>())
                switches.Add(new { expression = sw.Expression.ToString(), arms = sw.Sections.Select(section => new {
                    labels = section.Labels.Select(l => l.ToString()).ToArray(), body = section.Statements.ToString(),
                    calls = section.DescendantNodes().OfType<InvocationExpressionSyntax>().Select(Name).Distinct().Order().ToArray()
                }).ToArray() });
            foreach (SwitchExpressionSyntax sw in method.DescendantNodes().OfType<SwitchExpressionSyntax>())
                switches.Add(new { expression = sw.GoverningExpression.ToString(), arms = sw.Arms.Select(arm => new {
                    labels = new[] { arm.Pattern.ToString() }, body = arm.Expression.ToString(),
                    calls = arm.DescendantNodes().OfType<InvocationExpressionSyntax>().Select(Name).Distinct().Order().ToArray()
                }).ToArray() });
            methods.Add(new {
                id = $"{relative}:{type}.{method.Identifier}({string.Join(',',method.ParameterList.Parameters.Select(p => p.Type?.ToString()))})",
                name = method.Identifier.ValueText, declaring_type = type,
                return_type = method.ReturnType.ToString(),
                first_line = method.GetLocation().GetLineSpan().StartLinePosition.Line + 1,
                last_line = method.GetLocation().GetLineSpan().EndLinePosition.Line + 1,
                sha256 = Sha(method.ToFullString()),
                calls = calls.Select(Name).Distinct().Order().ToArray(),
                awaits = method.DescendantNodes().OfType<AwaitExpressionSyntax>().Select(a => a.Expression.ToString()).Distinct().ToArray(),
                created_types = method.DescendantNodes().OfType<ObjectCreationExpressionSyntax>().Select(c => c.Type.ToString()).Distinct().ToArray(),
                literals = method.DescendantTokens().Where(t => t.IsKind(SyntaxKind.StringLiteralToken)).Select(t => t.ValueText).Distinct().Order().ToArray(),
                switches, source = method.ToFullString()
            });
        }
        files.Add(new { path = relative, sha256 = Sha(text), methods });
    }
    result.Add(new { layer, root, files });
}
Console.WriteLine(JsonSerializer.Serialize(new { schema_version = "compiled-action-source-inventory-v1", layers = result }));
