using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using Sts2Emulator.Core.Run;
using Xunit;

namespace Sts2Emulator.Tests;

// Expectations come directly from pinned real-game captures. Direct event entry
// is privileged test setup and never supplies an agent with hidden game state.
public class SpireShiftEventChoiceParityTests
{
    public static IEnumerable<object[]> Captures()
    {
        string inventory = Environment.GetEnvironmentVariable("SPIRESHIFT_EVENT_FIXTURE_INVENTORY")
            ?? throw new InvalidOperationException("A pinned fixture inventory is required");
        using var document = JsonDocument.Parse(File.ReadAllText(inventory));
        foreach (var entry in document.RootElement.GetProperty("files").EnumerateArray())
        {
            string comparison = entry.GetProperty("comparison").GetString()!;
            if (comparison is "initial" or "settled_event_after")
            {
                yield return new object[]
                {
                    entry.GetProperty("path").GetString()!,
                    entry.GetProperty("sha256").GetString()!,
                    comparison,
                };
            }
        }
    }

    private static int[] Offered(RunEngine engine)
    {
        var mask = new int[RunConstants.MaxActions];
        engine.WriteActionMask(mask);
        return Enumerable.Range(0, mask.Length).Where(i => mask[i] != 0).ToArray();
    }

    [Theory]
    [MemberData(nameof(Captures))]
    public void TheCompleteMaskMatchesTheCapturedEnabledChoices(
        string filename, string digest, string comparison
    )
    {
        string root = Environment.GetEnvironmentVariable("SPIRESHIFT_EVENT_FIXTURE_ROOT")
            ?? throw new InvalidOperationException("A pinned fixture directory is required");
        byte[] bytes = File.ReadAllBytes(Path.Combine(root, filename));
        Assert.Equal(digest, Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
        using var document = JsonDocument.Parse(bytes);
        var capture = document.RootElement;
        Assert.Equal("v0.107.1", capture.GetProperty("game").GetProperty("release").GetString());
        Assert.Equal("23811903", capture.GetProperty("game").GetProperty("steam_buildid").GetString());
        Assert.Equal(8, capture.GetProperty("ascension").GetInt32());
        Assert.Equal(1, capture.GetProperty("floor").GetInt32());
        Assert.Equal("ABCDEF", capture.GetProperty("seed").GetString());

        var engine = new RunEngine();
        engine.Reset(capture.GetProperty("seed").GetString()!);
        var before = capture.GetProperty("before").GetProperty("player");
        Assert.Equal(before.GetProperty("hp").GetInt32(), engine.State.PlayerHp);
        Assert.Equal(before.GetProperty("max_hp").GetInt32(), engine.State.PlayerMaxHp);
        Assert.Equal(before.GetProperty("gold").GetInt32(), engine.State.Gold);
        Assert.Equal(capture.GetProperty("floor").GetInt32(), engine.State.Floor);
        var field = typeof(RunConstants).GetField(
            "Event" + capture.GetProperty("event").GetString(), BindingFlags.Public | BindingFlags.Static
        ) ?? throw new InvalidOperationException("Captured event has no matching engine constant");
        RunNonCombatEffects.BeginEvent(engine.State, (int)field.GetRawConstantValue()!);

        JsonElement options;
        if (comparison == "settled_event_after")
        {
            Assert.Equal(0, engine.Step(capture.GetProperty("chosen").GetInt32(), -1,
                out _, out bool terminal, out bool truncated));
            Assert.False(terminal);
            Assert.False(truncated);
            Assert.Equal(RunPhase.Event, engine.State.Phase);
            var after = capture.GetProperty("after");
            Assert.Equal("event", after.GetProperty("state_type").GetString());
            options = after.GetProperty("event").GetProperty("options");
        }
        else
        {
            options = capture.GetProperty("options");
        }

        int[] expected = options.EnumerateArray()
            .Where(o => !o.GetProperty("is_locked").GetBoolean())
            .Select(o => o.GetProperty("index").GetInt32()).Order().ToArray();
        Assert.Equal(expected, Offered(engine));

        // Reject both locked options and nonexistent extra slots without spending
        // resources, advancing the event, or returning a reward.
        var observation = new int[RunConstants.RunObsSize];
        engine.WriteObservation(observation);
        foreach (int action in Enumerable.Range(0, 5).Append(-1).Append(RunConstants.MaxActions)
            .Where(a => !expected.Contains(a)))
        {
            Assert.Equal(-1, engine.Step(action, -1, out float reward,
                out bool terminal, out bool truncated));
            Assert.Equal(0f, reward);
            Assert.False(terminal);
            Assert.False(truncated);
            var unchanged = new int[RunConstants.RunObsSize];
            engine.WriteObservation(unchanged);
            Assert.Equal(observation, unchanged);
            Assert.Equal(expected, Offered(engine));
        }
    }
}
