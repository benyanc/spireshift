// Native-only privileged reward-generation fixture. No reward selection or full run.
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using Sts2Headless;

internal static class Program
{
    private static readonly JsonSerializerOptions Json = new() { IncludeFields = true };

    private static int Main(string[] args)
    {
        if (args.Length != 5 || args[3] is not ("test" or "original_normal"))
            throw new ArgumentException("Expected candidate directory, seed, relic, mode and private output path");
        var candidate = Path.GetFullPath(args[0]);
        AssemblyLoadContext.Default.Resolving += (context, name) =>
        {
            foreach (var directory in new[] { "src/Sts2Headless/bin/Release/net9.0", "lib" })
            {
                var path = Path.Combine(candidate, directory, name.Name + ".dll");
                if (File.Exists(path)) return context.LoadFromAssemblyPath(path);
            }
            return null;
        };
        return Exercise(args);
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Exercise(string[] args)
    {
        var sim = new RunSimulator();
        try
        {
            var started = sim.StartRun("Ironclad", 8, args[1], "en", "native_all_unlocked");
            if (started.GetValueOrDefault("type") as string != "decision")
                throw new InvalidOperationException("Native fixture start failed: " + JsonSerializer.Serialize(started, Json));
            if (!TestMode.IsOn) throw new InvalidOperationException("Fixture initialization lost test mode");
            var run = (RunState)(typeof(RunSimulator).GetField("_runState", BindingFlags.Instance | BindingFlags.NonPublic)
                ?.GetValue(sim) ?? throw new InvalidOperationException("Native run missing"));
            var player = run.Players.Single();
            RelicModel relic = args[2] switch
            {
                "CallingBell" => ModelDb.Relic<CallingBell>().ToMutable(),
                "Cauldron" => ModelDb.Relic<Cauldron>().ToMutable(),
                _ => throw new ArgumentException("Unknown reward fixture")
            };
            relic.Owner = player;
            var method = relic.GetType().GetMethod("GenerateRewards", BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new MissingMethodException("Original reward-generation method missing");
            object State() => new
            {
                run_rng = run.Rng.ToSerializable(),
                player_rng = player.PlayerRng.ToSerializable(),
                relic_grab_bag = player.RelicGrabBag.ToSerializable()
            };
            var before = JsonSerializer.SerializeToElement(State(), Json);
            List<Reward> rewards;
            // The reference disables the mode only for this original method call.
            // It shares the same native initialization, stub and later Populate path.
            try
            {
                TestMode.IsOn = args[3] == "test";
                rewards = (List<Reward>)(method.Invoke(relic, null)
                    ?? throw new InvalidOperationException("Native rewards missing"));
            }
            finally { TestMode.IsOn = true; }
            var populatedAtConstruction = rewards.Select(reward => reward.IsPopulated).ToArray();
            foreach (var reward in rewards) reward.Populate();
            var facts = rewards.Select(reward => reward switch
            {
                RelicReward r => new { kind = "relic", id = r.Relic?.Id.Entry, rarity = r.Rarity.ToString() },
                PotionReward p => new { kind = "potion", id = p.Potion?.Id.Entry, rarity = p.Potion?.Rarity.ToString() ?? "unknown" },
                _ => throw new InvalidOperationException("Unexpected generated reward type")
            }).ToArray();
            if (facts.Any(row => row.id == null) || rewards.Count != (args[2] == "CallingBell" ? 3 : 5))
                throw new InvalidOperationException("Incomplete populated reward fixture");
            var hook = typeof(RunSimulator).GetNestedType("NativeRewardGeneration", BindingFlags.NonPublic);
            var result = new
            {
                schema_version = "native-reward-generation-fixture-v1",
                seed = args[1], relic = args[2], mode = args[3],
                wrapper_sha256 = FileHash(typeof(RunSimulator).Assembly.Location),
                game_sha256 = FileHash(typeof(TestMode).Assembly.Location),
                stub_sha256 = FileHash(typeof(Godot.OS).Assembly.Location),
                managed_runtime_version = Environment.Version.ToString(),
                original_method_il_sha256 = Convert.ToHexString(SHA256.HashData(method.GetMethodBody()!.GetILAsByteArray()!)).ToLowerInvariant(),
                hook_installed = hook?.GetProperty("Installed", BindingFlags.Static | BindingFlags.NonPublic)?.GetValue(null) as bool? ?? false,
                hook_methods = hook?.GetProperty("InstalledMethods", BindingFlags.Static | BindingFlags.NonPublic)?.GetValue(null) as int? ?? 0,
                global_test_mode_retained = TestMode.IsOn,
                populated_at_construction = populatedAtConstruction,
                generated_rewards = facts,
                private_before = before,
                private_after = JsonSerializer.SerializeToElement(State(), Json),
                privileged_fixture = true, full_run_attempts = 0, reward_selections = 0,
                training_allowed = false, shipped_game_compared = false
            };
            File.WriteAllText(args[4], JsonSerializer.Serialize(result, Json) + "\n");
            Console.WriteLine("Native reward-generation fixture saved; no reward claim or full run.");
            return 0;
        }
        finally { sim.CleanUp(); }
    }

    private static string FileHash(string file) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))).ToLowerInvariant();
}
