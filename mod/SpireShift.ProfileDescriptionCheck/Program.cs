// Debug-only native API oracle. Registry formatting is not gameplay or reachable-state coverage.
using System.Collections;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using Sts2Headless;

internal static class Program
{
    private static readonly BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
    private static readonly JsonSerializerOptions Json = new() { IncludeFields = true };
    private static readonly Dictionary<string, bool> Checks = new();

    private static int Main(string[] args)
    {
        if (args.Length != 3) throw new ArgumentException("Expected candidate, seed and private output");
        var candidate = Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving += (context, name) =>
        {
            foreach (var directory in new[] { "src/Sts2Headless/bin/Release/net9.0", "lib" })
            {
                var file = Path.Combine(candidate, directory, name.Name + ".dll");
                if (File.Exists(file)) return context.LoadFromAssemblyPath(file);
            }
            return null;
        };
        return Exercise(args);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Exercise(string[] args)
    {
        var simulator = new RunSimulator();
        var rows = new List<object>();
        var errors = new List<object>();
        var excluded = new List<object>();
        try
        {
            var start = simulator.StartRun("Ironclad", 8, args[1], "en", "native_benchmark_full_v1");
            Check("benchmark_start", start.GetValueOrDefault("type") as string == "decision");
            var run = (RunState)typeof(RunSimulator).GetField("_runState", Private)!.GetValue(simulator)!;
            var player = run.Players.Single();
            var expected = UnlockState.all.ToSerializable();
            var actual = run.UnlockState.ToSerializable();
            Check("native_unlock_epochs", actual.UnlockedEpochs.ToHashSet().SetEquals(expected.UnlockedEpochs));
            Check("native_seen_encounters", actual.EncountersSeen.ToHashSet().SetEquals(expected.EncountersSeen));
            Check("native_prior_run_gate", actual.NumberOfRuns == expected.NumberOfRuns);
            Check("all_acts_discovered", SaveManager.Instance.Progress.DiscoveredActs.SetEquals(
                ModelDb.ActsByIndex.SelectMany(group => group).Select(act => act.Id)));
            Check("fresh_tutorial_profile", SaveManager.Instance.Progress.EnableFtues
                && SaveManager.Instance.Progress.FtueCompleted.Count == 0);
            Check("fixed_A8", run.AscensionLevel == 8);
            object ActSelection(bool testMode)
            {
                var rng = new Rng(StringHelper.GetDeterministicHashCode(args[1]), "act_selection");
                try
                {
                    TestMode.IsOn = testMode;
                    return new { acts = ActModel.GetRandomList(rng, run.UnlockState, false)
                        .Select(act => act.Id.ToString()).ToArray(), rng = rng.ToSerializable() };
                }
                finally { TestMode.IsOn = true; }
            }
            var normal = JsonSerializer.SerializeToElement(ActSelection(false), Json);
            var managed = JsonSerializer.SerializeToElement(ActSelection(true), Json);
            Check("normal_act_selection_and_rng", normal.GetRawText() == managed.GetRawText());
            Check("started_with_lobby_act_sequence", run.Acts.Select(act => act.Id.ToString()).SequenceEqual(
                normal.GetProperty("acts").EnumerateArray().Select(value => value.GetString()!)));
            var profile = simulator.ExportBenchmarkProfile(Path.Combine(Path.GetDirectoryName(args[2])!, "benchmark-progress.save"));
            Check("profile_export", profile.GetValueOrDefault("type") as string == "benchmark_profile");
            // Explicit privileged inspection fixture; no potion reward or combat is claimed.
            var fixtureSlots = (IList)typeof(MegaCrit.Sts2.Core.Entities.Players.Player)
                .GetField("_potionSlots", Private)!.GetValue(player)!;
            foreach (var (entry, slot) in new[] { ("SWIFT_POTION", 0), ("STRENGTH_POTION", 1) })
            {
                var potion = ModelDb.GetById<PotionModel>(new ModelId("POTION", entry)).ToMutable();
                potion.Owner = player;
                fixtureSlots[slot] = potion;
            }
            var fixtureState = (Dictionary<string, object?>)typeof(RunSimulator)
                .GetMethod("DetectDecisionPoint", Private)!.Invoke(simulator, null)!;
            File.WriteAllText(Path.Combine(Path.GetDirectoryName(args[2])!, "private-starting-state.json"),
                JsonSerializer.Serialize(fixtureState, Json));
            var checkpoint = simulator.SaveCheckpoint(Path.Combine(Path.GetDirectoryName(args[2])!, "native-checkpoint.save"), true);
            Check("inspection_checkpoint_export", checkpoint.GetValueOrDefault("success") as bool? == true);
            var render = typeof(RunSimulator).GetMethod("StripVisibleText", BindingFlags.Static | BindingFlags.NonPublic)!;
            string Text(string raw) => (string)render.Invoke(null, new object[] { raw })!;
            Check("image_glyph_multiplicity", Text("[img]res://icons/energy.png[/img][img]res://icons/energy.png[/img]") == "[energy.png][energy.png]");
            Check("ordered_named_amounts", Text("[blue]2 Strength[/blue], [gold]7 Dexterity[/gold]") == "2 Strength, 7 Dexterity"
                && Text("[blue]7 Strength[/blue], [gold]2 Dexterity[/gold]") != "2 Strength, 7 Dexterity");
            var summary = typeof(RunSimulator).GetMethod("PlayerSummary", Private)!;
            var hover = typeof(RunSimulator).GetMethod("VisibleHoverCard", Private)!;
            var relics = (IList)typeof(MegaCrit.Sts2.Core.Entities.Players.Player).GetField("_relics", Private)!.GetValue(player)!;
            var potions = (IList)typeof(MegaCrit.Sts2.Core.Entities.Players.Player).GetField("_potionSlots", Private)!.GetValue(player)!;
            var originalRelics = relics.Cast<object>().ToArray();
            var originalPotions = potions.Cast<object?>().ToArray();
            void Record(string kind, AbstractModel model, Func<(string Actual, string Expected)> compare)
            {
                try
                {
                    var facts = compare();
                    if (facts.Actual != facts.Expected || string.IsNullOrWhiteSpace(facts.Actual))
                        throw new InvalidOperationException("Export differs from the native description formatter");
                    rows.Add(new { kind, id = model.Id.ToString(), description = facts.Actual });
                }
                catch (Exception error)
                {
                    errors.Add(new { kind, id = model.Id.ToString(), error = error.GetBaseException().Message });
                }
            }
            var potionModels = UnlockState.all.Potions.DistinctBy(model => model.Id).ToArray();
            foreach (var canonical in potionModels)
            {
                if (canonical.Pool.IsMock)
                {
                    excluded.Add(new { kind = "potion", id = canonical.Id.ToString(), reason = "native_pool_IsMock" });
                    continue;
                }
                var potion = canonical.ToMutable(); potion.Owner = player;
                Record("potion", potion, () =>
                {
                    for (int slot = 0; slot < potions.Count; slot++) potions[slot] = null;
                    potions[0] = potion;
                    var state = JsonSerializer.SerializeToElement(summary.Invoke(simulator, new object[] { player }), Json);
                    return (state.GetProperty("potions")[0].GetProperty("description").GetString()!,
                        Text(potion.DynamicDescription.GetFormattedText()));
                });
            }
            for (int slot = 0; slot < potions.Count; slot++) potions[slot] = originalPotions[slot];
            var relicModels = UnlockState.all.Relics.DistinctBy(model => model.Id).ToArray();
            foreach (var canonical in relicModels)
            {
                var relic = canonical.ToMutable(); relic.Owner = player;
                Record("relic", relic, () =>
                {
                    relics.Clear(); relics.Add(relic);
                    var state = JsonSerializer.SerializeToElement(summary.Invoke(simulator, new object[] { player }), Json);
                    return (state.GetProperty("relics")[0].GetProperty("description").GetString()!,
                        Text(relic.DynamicDescription.GetFormattedText()));
                });
            }
            relics.Clear(); foreach (var relic in originalRelics) relics.Add(relic);
            var cardModels = UnlockState.all.Cards.DistinctBy(model => model.Id).ToArray();
            var plannedUpgradedCards = 0;
            foreach (var canonical in cardModels)
            {
                var card = run.CreateCard(canonical, player);
                Record("card", card, () =>
                {
                    var facts = (Dictionary<string, object?>)hover.Invoke(simulator, new object[] { card })!;
                    return ((string)facts["description"]!, Text(card.GetDescriptionForPile(PileType.None)));
                });
                if (card.IsUpgradable)
                {
                    plannedUpgradedCards++;
                    card.UpgradeInternal(); card.FinalizeUpgradeInternal();
                    Record("upgraded_card", card, () =>
                    {
                        var facts = (Dictionary<string, object?>)hover.Invoke(simulator, new object[] { card })!;
                        return ((string)facts["description"]!, Text(card.GetDescriptionForPile(PileType.None)));
                    });
                }
                run.RemoveCard(card);
            }
            var result = new
            {
                schema_version = "native-profile-description-check-v1", seed = args[1], process_id = Environment.ProcessId, checks = Checks,
                planned_potions = potionModels.Length, planned_relics = relicModels.Length,
                planned_cards = cardModels.Length, planned_upgraded_cards = plannedUpgradedCards,
                successful_descriptions = rows.Count, rows, errors, excluded,
                original_normal_act_selection = normal, managed_act_selection = managed,
                profile_json_sha256 = profile["progress_json_sha256"],
                wrapper_sha256 = Hash(typeof(RunSimulator).Assembly.Location),
                game_sha256 = Hash(typeof(TestMode).Assembly.Location),
                original_act_selection_il_sha256 = Hash(typeof(ActModel).GetMethod("GetRandomList")!.GetMethodBody()!.GetILAsByteArray()!),
                managed_runtime_version = Environment.Version.ToString(), global_test_mode_retained = TestMode.IsOn,
                privileged_fixture = true, shipped_game_compared = false, native_fixture_starts = 1,
                full_run_attempts = 0, optimizer_steps = 0, training_allowed = false
            };
            File.WriteAllText(args[2], JsonSerializer.Serialize(result, Json) + "\n");
            Console.WriteLine($"Profile checks: {Checks.Count}; descriptions: {rows.Count}; failures: {errors.Count}.");
            return errors.Count == 0 ? 0 : 1;
        }
        finally { simulator.CleanUp(); }
    }

    private static void Check(string name, bool ok)
    {
        Checks.Add(name, ok);
        if (!ok) throw new InvalidOperationException("Native profile check failed: " + name);
    }
    private static string Hash(string file) => Hash(File.ReadAllBytes(file));
    private static string Hash(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
}
