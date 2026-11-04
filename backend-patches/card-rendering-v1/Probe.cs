using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
#if !NATIVE_MATRIX
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
#endif
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Runs;
using STS2Connector;
using STS2Connector.LiveHost;
using Sts2Headless;

internal static class Program
{
    private static void Main()
    {
        using var request = JsonDocument.Parse(Console.In.ReadToEnd());
        var spec = request.RootElement;
        string mode = spec.GetProperty("mode").GetString()!;
        if (mode == "text")
        {
            Console.WriteLine(JsonSerializer.Serialize(spec.GetProperty("values").EnumerateArray()
                .Select(v => VisibleText.SingleLine(v.ValueKind == JsonValueKind.Null ? null : v.GetString())).ToArray()));
            return;
        }
#if !NATIVE_MATRIX
        if (mode == "audit")
        {
            Audit(spec.GetProperty("host").GetString()!);
            return;
        }
#endif
        if (mode != "matrix") throw new InvalidOperationException("Unknown source probe mode.");
        string candidate = spec.GetProperty("candidate").GetString()!;
        AssemblyLoadContext.Default.Resolving += (context, name) =>
        {
            string file = Path.Combine(candidate, "lib", name.Name + ".dll");
            return File.Exists(file) ? context.LoadFromAssemblyPath(file) : null;
        };
        Matrix(spec);
    }

#if !NATIVE_MATRIX
    private static void Audit(string host)
    {
        var rows = new List<object>();
        foreach (string file in Directory.EnumerateFiles(host, "*.cs", SearchOption.AllDirectories).Order())
        {
            string relative = Path.GetRelativePath(host, file);
            if (relative.Split(Path.DirectorySeparatorChar).Any(p => p is "bin" or "obj" or "out" or "tests" or "tools")) continue;
            var tree = CSharpSyntaxTree.ParseText(File.ReadAllText(file));
            if (tree.GetDiagnostics().Any(d => d.Severity == Microsoft.CodeAnalysis.DiagnosticSeverity.Error))
                throw new InvalidOperationException("Cannot inventory changed C# source.");
            foreach (var call in tree.GetRoot().DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                string name = call.Expression switch { MemberAccessExpressionSyntax member => member.Name.Identifier.ValueText,
                    IdentifierNameSyntax identifier => identifier.Identifier.ValueText, _ => "" };
                if (name != "BuildCard") continue;
                var pile = call.ArgumentList.Arguments.SingleOrDefault(a => a.NameColon?.Name.Identifier.ValueText == "displayPile");
                if (pile == null) throw new InvalidOperationException($"Implicit card render context: {relative}");
                rows.Add(new { file = relative, line = call.GetLocation().GetLineSpan().StartLinePosition.Line + 1,
                    method = call.Ancestors().OfType<MethodDeclarationSyntax>().First().Identifier.ValueText,
                    display_pile = pile.Expression.ToString(), call = call.ToString() });
            }
        }
        var parameter = typeof(LiveContextReader).GetMethod("BuildCard")!.GetParameters().Single(p => p.Name == "displayPile");
        if (parameter.IsOptional || parameter.HasDefaultValue) throw new InvalidOperationException("Card context default restored.");
        Console.WriteLine(JsonSerializer.Serialize(new { schema_version = "compiled-card-context-inventory-v1", calls = rows,
            display_pile_required_by_compiler = true }));
    }
#endif

    private static void Matrix(JsonElement spec)
    {
        // One new, declared privileged diagnostic world, zero policy/gameplay
        // decisions. Native model/formatter calls are reads on synthetic states.
        var sim = new RunSimulator();
        var started = sim.StartRun("Ironclad", 8, spec.GetProperty("seed").GetString(), "en", "native_benchmark_full_v1");
        if (started.GetValueOrDefault("type") as string == "error") throw new InvalidOperationException(JsonSerializer.Serialize(started));
        var entered = sim.EnterRoom("combat", "SHRINKER_BEETLE_WEAK", null);
        if (entered.GetValueOrDefault("type") as string == "error") throw new InvalidOperationException(JsonSerializer.Serialize(entered));
        var run = RunManager.Instance.DebugOnlyGetState()!;
        var player = LocalContext.GetMe(run)!;
        var cards = new List<object>();
        foreach (int block in new[] { 0, 7 })
        {
            if (block != 0) player.Creature.GainBlockInternal(block);
            foreach (string id in new[] { "BODY_SLAM", "PERFECTED_STRIKE", "STRIKE_IRONCLAD", "DEFEND_IRONCLAD" })
            foreach (bool upgraded in new[] { false, true })
            {
                var model = run.CreateCard(ModelDb.GetById<CardModel>(new ModelId("CARD", id)), player);
                if (upgraded) { model.UpgradeInternal(); model.FinalizeUpgradeInternal(); }
                foreach (PileType pile in new[] { PileType.None, PileType.Hand, PileType.Play, PileType.Deck, PileType.Draw, PileType.Discard, PileType.Exhaust })
                {
                    model.DynamicVars.ClearPreview();
                    model.UpdateDynamicVarPreview(CardPreviewMode.Normal, model.CurrentTarget, model.DynamicVars);
                    string actualWidgetText = VisibleText.SingleLine(ConnectorMod.StripRichTextTags(model.GetDescriptionForPile(pile)));
                    var exported = LiveContextReader.BuildCard(model, "diagnostic-card", displayPile: pile, includeSelectionPreviews: true);
                    if (exported.Description != actualWidgetText) throw new InvalidOperationException($"Native card text mismatch: {id}/{pile}");
                    cards.Add(new { id, upgraded, block = player.Creature.Block, pile = pile.ToString(),
                        native_widget_description = actualWidgetText, production_description = exported.Description,
                        after_upgrade = exported.AfterUpgrade });
                }
            }
        }
        var obtained = sim.SetPlayer(new Dictionary<string, JsonElement> {
            ["hp"] = JsonSerializer.SerializeToElement(8), ["max_hp"] = JsonSerializer.SerializeToElement(80),
            ["obtain_relics"] = JsonSerializer.SerializeToElement(new[] { "REGAL_PILLOW" }) });
        if (obtained.GetValueOrDefault("type") as string == "error") throw new InvalidOperationException(JsonSerializer.Serialize(obtained));
        var heal = new HealRestSiteOption(player);
        string nativeRest = heal.Description.GetFormattedText();
        Console.WriteLine(JsonSerializer.Serialize(new { schema_version = "native-card-render-source-vectors-v1",
            seed = spec.GetProperty("seed").GetString(), privileged = true, policy_decisions = 0, optimizer_updates = 0,
            card_vectors = cards, rest = new { native_formatted = nativeRest,
                production_visible = VisibleText.SingleLine(ConnectorMod.SafeGetText(() => heal.Description)) } }));
    }
}
