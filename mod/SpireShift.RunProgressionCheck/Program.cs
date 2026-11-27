// Privileged transition/ending fixture. Forced boss deaths are never player wins or learning data.
using System.Diagnostics;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using Sts2Headless;

internal static class Program
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
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
        var states = new List<object>();
        var checkpoints = new List<object>();
        var delivered = new List<object>();
        var forcedBossDefeats = 0;
        Dictionary<string, object?>? cleanupIdentity = null;
        string? error = null;
        try
        {
            var state = simulator.StartRun("Ironclad", 8, args[1], "en", "native_benchmark_full_v1");
            RequireDecision(state);
            var run = (RunState)typeof(RunSimulator).GetField("_runState", Private)!.GetValue(simulator)!;
            Check("fixed_A8", run.AscensionLevel == 8);
            Check("three_native_acts", run.Acts.Count == 3);
            var profile = Path.Combine(Path.GetDirectoryName(args[2])!, "benchmark-progress.save");
            simulator.ExportBenchmarkProfile(profile);
            Record("initial", state);

            for (int act = 1; act <= 3; act++)
            {
                Check($"act_{act}_current", run.CurrentActIndex + 1 == act);
                // Debug EnterRoom bypasses DoMapSelect's wrapper presentation reset.
                // Reset only presentation flags; native rules and combat state remain untouched.
                typeof(RunSimulator).GetField("_combatRewardsStarted", Private)!.SetValue(simulator, false);
                typeof(RunSimulator).GetField("_rewardsProcessed", Private)!.SetValue(simulator, false);
                typeof(RunSimulator).GetField("_mapPresentationOpen", Private)!.SetValue(simulator, false);
                // The native debug command records a real boss coordinate/history. A bare
                // EnterRoom save lacks visited coordinates and shipped Continue opens the map.
                Pump(RunManager.Instance.EnterMapCoordDebug(run.Map.BossMapPoint.coord,
                    RoomType.Boss, model: run.Act.BossEncounter.ToMutable(), showTransition: false));
                Check($"act_{act}_native_boss_map_coordinate", run.CurrentMapCoord == run.Map.BossMapPoint.coord);
                state = simulator.Observe();
                RequireDecision(state);
                Check($"act_{act}_native_boss_room", run.CurrentRoom is CombatRoom room && room.RoomType.ToString() == "Boss");
                Check($"act_{act}_not_ended_before_fixture", !RunManager.Instance.IsGameOver);
                Record($"act_{act}_boss_before_force_kill", state);

                // Use the native death command solely to reach the transition fixture. No
                // combat policy, legitimate boss defeat or naturally achieved victory is claimed.
                var enemies = CombatManager.Instance.DebugOnlyGetState()!.Enemies.ToArray();
                Check($"act_{act}_enemies_present", enemies.Length > 0);
                Pump(CreatureCmd.Kill(enemies, force: true));
                forcedBossDefeats++;
                state = simulator.Observe(); RequireDecision(state);
                if (CombatManager.Instance.IsInProgress)
                {
                    var observedPlayer = (Dictionary<string, object?>)state["player"]!;
                    state = simulator.ExecuteAction("end_turn", new() { ["player_ref"] = observedPlayer["native_ref"] });
                    RequireDecision(state);
                    delivered.Add(new { action = "end_turn_after_fixture_removal", act, result = state });
                }
                Record($"act_{act}_after_force_kill", state);
                Check($"act_{act}_boss_defeat_not_run_victory", !RunManager.Instance.IsGameOver);

                for (int skip = 0; state.GetValueOrDefault("decision") as string == "reward_set" && skip < 4; skip++)
                {
                    state = simulator.ExecuteAction("skip_rewards", null); RequireDecision(state);
                    delivered.Add(new { action = "skip_rewards", act, result = state });
                }
                Check($"act_{act}_explicit_proceed", state.GetValueOrDefault("decision") as string == "combat_rewards_complete");
                Check($"act_{act}_pre_finished_native_room", ((CombatRoom)run.CurrentRoom!).IsPreFinished);
                Record($"act_{act}_before_proceed", state);
                var savePath = Path.Combine(Path.GetDirectoryName(args[2])!, $"act-{act}-before-proceed.save");
                var saved = simulator.SaveCheckpoint(savePath, preserveCurrentRoom: true);
                Check($"act_{act}_checkpoint_saved", saved.GetValueOrDefault("success") as bool? == true);
                checkpoints.Add(new { act, path = savePath, sha256 = Hash(savePath), state });

                state = simulator.ExecuteAction("proceed", new() { ["room_ref"] = state["room_ref"] });
                RequireDecision(state);
                delivered.Add(new { action = "proceed", act, result = state });
                Record($"act_{act}_after_proceed", state);
                Check($"act_{act}_proceed_is_not_immediate_victory", !RunManager.Instance.IsGameOver);
                if (act < 3) Check($"act_{act}_advanced_once", run.CurrentActIndex == act);
                else
                {
                    Check("third_act_stays_third_until_architect", run.CurrentActIndex == 2);
                    Check("architect_requires_another_decision", state.GetValueOrDefault("decision") as string == "event_choice");
                    for (int step = 0; !RunManager.Instance.IsGameOver && step < 12; step++)
                    {
                        state = simulator.ExecuteAction("choose_option", new() { ["option_index"] = 0 });
                        RequireDecision(state);
                        delivered.Add(new { action = "choose_option", act, step, result = state });
                    }
                }
            }
            state = simulator.Observe(); RequireDecision(state); Record("terminal", state);
            Check("native_game_over", RunManager.Instance.IsGameOver);
            Check("native_victory_room", run.CurrentRoom?.IsVictoryRoom == true);
            Check("wrapper_explicit_victory", state.GetValueOrDefault("decision") as string == "game_over"
                && state.GetValueOrDefault("victory") is true);
            Check("victory_despite_zero_hp", run.Players.Single().Creature.IsDead
                && run.Players.Single().Creature.CurrentHp == 0);
            Check("global_test_mode_retained", TestMode.IsOn);
            simulator.CleanUp();
            cleanupIdentity = simulator.GetRunIdentity();
            Check("native_cleanup_completed", cleanupIdentity.GetValueOrDefault("active") is false);

            void Record(string stage, Dictionary<string, object?> value) => states.Add(new
            {
                stage, state = value, native = simulator.GetRunIdentity(),
                current_room_type = run.CurrentRoom?.GetType().FullName,
                is_victory_room = run.CurrentRoom?.IsVictoryRoom,
                native_game_over = RunManager.Instance.IsGameOver,
                native_player_dead = run.Players.Single().Creature.IsDead,
                native_player_hp = run.Players.Single().Creature.CurrentHp,
            });

            void Pump(Task task)
            {
                var context = typeof(RunSimulator).GetField("_syncCtx", BindingFlags.Static | BindingFlags.NonPublic)!.GetValue(null)!;
                var pump = context.GetType().GetMethod("Pump")!;
                var watch = Stopwatch.StartNew();
                while (!task.IsCompleted && watch.Elapsed.TotalSeconds < 8)
                {
                    pump.Invoke(context, null); Thread.Sleep(1);
                }
                if (!task.IsCompleted) throw new TimeoutException("Native fixture command exceeded eight seconds");
                task.GetAwaiter().GetResult(); pump.Invoke(context, null);
            }
        }
        catch (Exception ex) { error = ex.ToString(); }
        var result = new
        {
            schema_version = "native-run-progression-check-v3", process_id = Environment.ProcessId,
            seed = args[1], status = error == null ? "native_progression_fixture_pass" : "native_progression_fixture_incomplete",
            checks = Checks, error, states, checkpoints, delivered, cleanup_identity = cleanupIdentity,
            managed_runtime_version = Environment.Version.ToString(),
            wrapper_sha256 = Hash(typeof(RunSimulator).Assembly.Location),
            game_sha256 = Hash(typeof(TestMode).Assembly.Location),
            godot_stub_sha256 = Hash(typeof(Godot.OS).Assembly.Location),
            privileged_fixture = true, planned_forced_boss_defeats = 3,
            fixture_forced_boss_defeats = forcedBossDefeats, native_fixture_starts = 1,
            natural_victories = 0, full_run_attempts = 0, optimizer_steps = 0, training_allowed = false,
        };
        File.WriteAllText(args[2], JsonSerializer.Serialize(result, Json) + "\n");
        return error == null ? 0 : 1;
    }

    private static void RequireDecision(Dictionary<string, object?> state)
    {
        if (state.GetValueOrDefault("type") as string != "decision")
            throw new InvalidOperationException("Native fixture did not return a decision: " + JsonSerializer.Serialize(state, Json));
    }
    private static void Check(string name, bool value)
    {
        Checks[name] = value;
        if (!value) throw new InvalidOperationException("Progression check failed: " + name);
    }
    private static string Hash(string path) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));
}
