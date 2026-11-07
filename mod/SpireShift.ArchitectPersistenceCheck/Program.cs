using System.Diagnostics;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Runs.History;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Managers;
using MegaCrit.Sts2.Core.TestSupport;
using Sts2Headless;

internal static class Program
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
    private static readonly Dictionary<string, bool> Checks = new();

    private static int Main(string[] args)
    {
        if (args.Length != 3) throw new ArgumentException("Expected frozen candidate, fresh seed and private output");
        AssemblyLoadContext.Default.Resolving += (context, name) =>
        {
            foreach (var directory in new[] { "src/Sts2Headless/bin/Release/net9.0", "lib" })
            {
                var file = Path.GetFullPath(Path.Combine(args[0], directory, name.Name + ".dll"));
                if (File.Exists(file)) return context.LoadFromAssemblyPath(file);
            }
            return null;
        };
        return Exercise(args[1], Path.GetFullPath(args[2]));
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Exercise(string seed, string output)
    {
        var storePath = Path.Combine(Path.GetDirectoryName(output)!, "profile");
        var store = new DirectorySaveStore(storePath);
        var save = new SaveManager(store, forceSynchronous: true);
        SaveManager.MockInstanceForTesting(save);
        var simulator = new RunSimulator();
        var manager = RunManager.Instance;
        var stages = new List<object>();
        var forcedBossDefeats = 0;
        string? error = null;
        try
        {
            Check("private_profile_empty", !Directory.Exists(storePath));
            var state = simulator.StartRun("Ironclad", 8, seed, "en", "native_benchmark_full_v1");
            RequireDecision(state);
            var run = (RunState)typeof(RunSimulator).GetField("_runState", Private)!.GetValue(simulator)!;
            var character = run.Players.Single().Character.Id;
            var progressPath = store.GetFullPath(ProgressSaveManager.GetProgressPathForProfile(0));
            var historyDir = RunHistorySaveManager.GetHistoryPath(0);
            Check("fixed_ironclad_a8", character.Entry == "IRONCLAD" && run.AscensionLevel == 8 && run.Acts.Count == 3);
            Check("fresh_history", save.GetRunHistoryCount() == 0);
            Check("normal_wrapper_starts_saving_off", !manager.ShouldSave);
            // Enable only the native in-process save flag in this disposable diagnostic.
            typeof(RunManager).GetProperty(nameof(RunManager.ShouldSave))!.SetValue(manager, true);
            save.SaveProgressFile();
            var progressBefore = Hash(progressPath);
            File.Copy(progressPath, Path.Combine(Path.GetDirectoryName(output)!, "progress-before.save"));
            var winsBefore = save.Progress.GetOrCreateCharacterStats(character).TotalWins;
            var runsBefore = save.Progress.NumberOfRuns;

            for (int act = 1; act <= 3; act++)
            {
                Check($"act_{act}_current", run.CurrentActIndex + 1 == act);
                if (act > 1) Pump(manager.EnterMapCoord(run.Map.StartingMapPoint.coord));
                var ancient = run.MapPointHistory[act - 1].Single(point => point.MapPointType == MapPointType.Ancient);
                Check($"act_{act}_native_ancient_event", ancient.FirstRoomOfType(RoomType.Event)?.ModelId != null);
                stages.Add(new { act, ancient = ancient.FirstRoomOfType(RoomType.Event)!.ModelId!.ToString() });

                // Jump to the actual boss map coordinate through native room entry so
                // the game itself writes its history. Only wrapper UI flags need resetting.
                Pump(manager.EnterMapCoord(run.Map.BossMapPoint.coord));
                typeof(RunSimulator).GetProperty("_mapPresentationOpen", Private)!.SetValue(simulator, false);
                foreach (var field in new[] { "_combatRewardsStarted", "_rewardsProcessed" })
                    typeof(RunSimulator).GetField(field, Private)!.SetValue(simulator, false);
                Check($"act_{act}_native_boss_room", run.CurrentRoom is CombatRoom { RoomType: RoomType.Boss }
                    && run.CurrentMapCoord == run.Map.BossMapPoint.coord && !manager.IsGameOver);
                var enemies = CombatManager.Instance.DebugOnlyGetState()!.Enemies.ToArray();
                Check($"act_{act}_enemies_present", enemies.Length > 0);
                // Deliberately privileged boss removal to reach the save endpoint quickly.
                Pump(CreatureCmd.Kill(enemies, force: true));
                forcedBossDefeats++;
                state = simulator.Observe();
                RequireDecision(state);
                if (CombatManager.Instance.IsInProgress)
                {
                    var player = (Dictionary<string, object?>)state["player"]!;
                    state = Act("end_turn", new() { ["player_ref"] = player["native_ref"] });
                }
                for (int skip = 0; Decision(state) == "reward_set" && skip < 4; skip++)
                    state = Act("skip_rewards", null);
                Check($"act_{act}_native_proceed_owner", Decision(state) == "combat_rewards_complete"
                    && run.CurrentRoom is CombatRoom { IsPreFinished: true } && !manager.IsGameOver);
                state = Act("proceed", new() { ["room_ref"] = state["room_ref"] });
                Check($"act_{act}_proceed_not_victory", !manager.IsGameOver);
            }

            Check("architect_option_owner", Decision(state) == "event_choice"
                && state.GetValueOrDefault("event_id") as string == "THE_ARCHITECT");
            Check("all_native_history_valid_before_victory", ValidHistory(run.MapPointHistory));
            Check("save_enabled_with_current_run_before_victory", manager.ShouldSave && save.HasRunSave);
            Check("no_history_written_before_victory", save.GetRunHistoryCount() == 0);
            for (int step = 0; !manager.IsGameOver && step < 16; step++)
            {
                Check($"architect_step_{step}_current_owner", Decision(state) == "event_choice"
                    && state.GetValueOrDefault("event_id") as string == "THE_ARCHITECT" && manager.ShouldSave);
                state = Act("choose_option", new() { ["option_index"] = 0 });
            }
            Check("native_explicit_victory", manager.IsGameOver && run.CurrentRoom?.IsVictoryRoom == true
                && Decision(state) == "game_over" && state.GetValueOrDefault("victory") is true);
            Check("terminal_current_run_removed", !save.HasRunSave);
            Check("progress_bytes_changed", Hash(progressPath) != progressBefore);

            var reloaded = new SaveManager(new DirectorySaveStore(storePath), forceSynchronous: true);
            reloaded.InitProfileId(0);
            Check("progress_reloads_without_repair", reloaded.InitProgressData().Status == ReadSaveStatus.Success);
            var names = reloaded.GetAllRunHistoryNames();
            Check("one_native_run_history", names.Count == 1);
            var loaded = reloaded.LoadRunHistory(names.Single());
            Check("run_history_reloads_without_repair", loaded.Status == ReadSaveStatus.Success);
            var history = loaded.SaveData!;
            Check("persisted_victory_matches_seed_and_difficulty", history.Win && !history.WasAbandoned
                && history.Seed == seed && history.Ascension == 8 && history.Players.Single().Character == character);
            Check("persisted_native_map_history_valid", history.Acts.Count == 3 && ValidHistory(history.MapPointHistory));
            var winsAfter = reloaded.Progress.GetOrCreateCharacterStats(character).TotalWins;
            Check("persisted_profile_win_increments_once", winsAfter == winsBefore + 1
                && reloaded.Progress.NumberOfRuns == runsBefore + 1);
            stages.Add(new
            {
                wins_before = winsBefore, wins_after = winsAfter, runs_before = runsBefore,
                runs_after = reloaded.Progress.NumberOfRuns, history = Path.Combine(historyDir, names.Single()),
                history_sha256 = Hash(store.GetFullPath(Path.Combine(historyDir, names.Single()))),
                progress = Path.GetRelativePath(storePath, progressPath), progress_sha256 = Hash(progressPath),
            });
            simulator.CleanUp();
            Check("clean_native_reset", simulator.GetRunIdentity().GetValueOrDefault("active") is false && !manager.ShouldSave);
        }
        catch (Exception ex) { error = ex.ToString(); }
        finally { SaveManager.ClearInstanceForTesting(); }

        File.WriteAllText(output, JsonSerializer.Serialize(new
        {
            schema_version = "native-architect-save-probe-v1", seed,
            status = error == null ? "architect_persistence_pass" : "architect_persistence_incomplete",
            checks = Checks, error, stages, fixture_forced_boss_defeats = forcedBossDefeats,
            natural_victories = 0, optimizer_updates = 0,
            managed_runtime_version = Environment.Version.ToString(),
            wrapper_sha256 = Hash(typeof(RunSimulator).Assembly.Location),
            game_sha256 = Hash(typeof(TestMode).Assembly.Location),
            godot_stub_sha256 = Hash(typeof(Godot.OS).Assembly.Location),
        }) + "\n");
        return error == null ? 0 : 1;

        Dictionary<string, object?> Act(string action, Dictionary<string, object?>? args)
        {
            var result = simulator.ExecuteAction(action, args);
            stages.Add(new { action, args, decision = Decision(result), result = result.GetValueOrDefault("type") });
            RequireDecision(result);
            return result;
        }
    }

    private static bool ValidHistory(IEnumerable<IEnumerable<MapPointHistoryEntry>> history) => history.Count() == 3
        && history.All(act => act.Any(point => point.MapPointType == MapPointType.Ancient)
            && act.Count(point => point.MapPointType == MapPointType.Boss
                && point.FirstRoomOfType(RoomType.Boss)?.ModelId != null) == 1
            && act.All(point => point.Rooms.Count > 0 && (point.MapPointType != MapPointType.Ancient
                || point.FirstRoomOfType(RoomType.Event)?.ModelId != null)));

    private static void Pump(Task task)
    {
        var context = typeof(RunSimulator).GetField("_syncCtx", BindingFlags.Static | BindingFlags.NonPublic)!.GetValue(null)!;
        var pump = context.GetType().GetMethod("Pump")!;
        var watch = Stopwatch.StartNew();
        while (!task.IsCompleted && watch.Elapsed.TotalSeconds < 8)
        {
            pump.Invoke(context, null);
            Thread.Sleep(1);
        }
        if (!task.IsCompleted) throw new TimeoutException("Native room command exceeded eight seconds");
        task.GetAwaiter().GetResult();
        pump.Invoke(context, null);
    }

    private static string? Decision(Dictionary<string, object?> state) => state.GetValueOrDefault("decision") as string;
    private static void RequireDecision(Dictionary<string, object?> state)
    {
        if (state.GetValueOrDefault("type") as string != "decision")
            throw new InvalidOperationException("Native action did not return a decision: " + JsonSerializer.Serialize(state));
    }

    private static void Check(string name, bool condition)
    {
        Checks.Add(name, condition);
        if (!condition) throw new InvalidOperationException("Architect check failed: " + name);
    }

    private static string Hash(string path) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));
}
