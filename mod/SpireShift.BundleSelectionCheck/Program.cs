// Privileged local synchronization/lifecycle checks, not gameplay or shipped parity.
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using Sts2Headless;

internal static class Program
{
    private static readonly Dictionary<string, bool> Checks = new();
    private static int Main(string[] args)
    {
        if (args.Length != 3) throw new ArgumentException("Expected candidate directory, seed and private output");
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
        var sim = new RunSimulator();
        var cases = new List<object>();
        try
        {
            for (int selected = 0; selected < 2; selected++)
            {
                Check($"start_{selected}", sim.StartRun("Ironclad", 8, args[1], "en", "native_all_unlocked")["type"] as string == "decision");
                var run = (RunState)typeof(RunSimulator).GetField("_runState", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(sim)!;
                var player = run.Players.Single();
                var sync = RunManager.Instance.PlayerChoiceSynchronizer;
                int notifications = 0, receivedIndex = -1; uint receivedId = uint.MaxValue;
                sync.PlayerChoiceReceived += (owner, id, data) =>
                {
                    Check($"sync_owner_{selected}", ReferenceEquals(owner, player));
                    notifications++; receivedId = id;
                    receivedIndex = PlayerChoiceResult.FromNetData(player, run, data).AsIndex();
                };
                var beforeIds = sync.ChoiceIds.ToArray();
                CardModel Make(string id) => run.CreateCard(ModelDb.GetById<CardModel>(new ModelId("CARD", id)), player);
                IReadOnlyList<IReadOnlyList<CardModel>> bundles = new IReadOnlyList<CardModel>[]
                {
                    new[] { Make("STRIKE_IRONCLAD"), Make("DEFEND_IRONCLAD") },
                    new[] { Make("WHIRLWIND"), Make("STRIKE_IRONCLAD") }
                };
                var task = CardSelectCmd.FromChooseABundleScreen(player, bundles);
                var reserved = sync.ChoiceIds.ToArray();
                var expectedId = beforeIds.Length == 0 ? 0u : beforeIds[0];
                Check($"reservation_{selected}", reserved.Length == 1 && reserved[0] == expectedId + 1);
                Check($"pending_{selected}", !task.IsCompleted && notifications == 0);
                ExpectFailure($"overlap_{selected}", () => CardSelectCmd.FromChooseABundleScreen(player, bundles));
                Check($"overlap_preserves_reservation_{selected}", sync.ChoiceIds.SequenceEqual(reserved));
                var snapshot = (Dictionary<string, object?>)typeof(RunSimulator).GetMethod("DetectDecisionPoint", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(sim, null)!;
                var json = JsonSerializer.SerializeToElement(snapshot);
                var operands = new Dictionary<string, object?>
                {
                    ["selection_ref"] = json.GetProperty("selection_ref").GetString(),
                    ["bundle_index"] = selected,
                    ["bundle_ref"] = json.GetProperty("bundles")[selected].GetProperty("native_ref").GetString()
                };
                var beforeInvalid = JsonSerializer.SerializeToElement(new { rng = player.PlayerRng.ToSerializable(), pool = player.RelicGrabBag.ToSerializable() }, new JsonSerializerOptions { IncludeFields = true });
                var bad = new Dictionary<string, object?>(operands) { ["bundle_index"] = true };
                Check($"invalid_{selected}", sim.ExecuteAction("select_bundle", bad)["type"] as string == "error");
                var afterInvalid = JsonSerializer.SerializeToElement(new { rng = player.PlayerRng.ToSerializable(), pool = player.RelicGrabBag.ToSerializable() }, new JsonSerializerOptions { IncludeFields = true });
                Check($"invalid_no_side_effects_{selected}", !task.IsCompleted && notifications == 0
                    && sync.ChoiceIds.SequenceEqual(reserved) && beforeInvalid.GetRawText() == afterInvalid.GetRawText());
                sim.ExecuteAction("select_bundle", operands);
                Check($"selected_exact_objects_{selected}", task.IsCompletedSuccessfully && ReferenceEquals(task.Result, bundles[selected]));
                Check($"sync_once_{selected}", notifications == 1 && receivedId == expectedId && receivedIndex == selected);
                Check($"reservation_not_duplicated_{selected}", sync.ChoiceIds.SequenceEqual(reserved));
                Check($"duplicate_rejected_{selected}", sim.ExecuteAction("select_bundle", operands)["type"] as string == "error" && notifications == 1);
                var abandoned = CardSelectCmd.FromChooseABundleScreen(player, bundles);
                sim.CleanUp();
                Check($"cleanup_cancels_{selected}", abandoned.IsCanceled && notifications == 1);
                ExpectFailure($"missing_binding_{selected}", () => CardSelectCmd.FromChooseABundleScreen(player, bundles));
                cases.Add(new { selected_index = selected, expected_choice_id = expectedId, actual_choice_id = receivedId,
                    notifications, chosen_card_ids = bundles[selected].Select(card => card.Id.Entry).ToArray() });
            }
            Check("global_test_mode_retained", TestMode.IsOn);
            var result = new
            {
                schema_version = "native-bundle-synchronization-check-v1", seed = args[1], checks = Checks, cases,
                wrapper_sha256 = Hash(typeof(RunSimulator).Assembly.Location), game_sha256 = Hash(typeof(TestMode).Assembly.Location),
                managed_runtime_version = Environment.Version.ToString(), native_fixture_starts = 2,
                privileged_fixture = true, shipped_game_compared = false, full_run_attempts = 0, training_allowed = false
            };
            File.WriteAllText(args[2], JsonSerializer.Serialize(result) + "\n");
            Console.WriteLine($"Bundle synchronization checks pass: {Checks.Count} subchecks, two native starts.");
            return 0;
        }
        finally { sim.CleanUp(); }
    }

    private static void Check(string name, bool value)
    {
        Checks.Add(name, value);
        if (!value) throw new InvalidOperationException("Bundle synchronization check failed: " + name);
    }
    private static void ExpectFailure(string name, Action operation)
    {
        bool rejected = false;
        try { operation(); } catch (InvalidOperationException) { rejected = true; }
        Check(name, rejected);
    }
    private static string Hash(string file) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))).ToLowerInvariant();
}
