using Sts2Emulator.Core.Run;
using Xunit;

namespace Sts2Emulator.Tests;

// Synthetic contract checks; not agent victories or full live-game conformance.
public class SpireShiftEventContinuationTests
{
    private static RunEngine AtEvent(int eventId)
    {
        var engine = new RunEngine();
        engine.Reset("100058");
        engine.State.EventId = eventId;
        engine.State.EventPage = 0;
        engine.State.Phase = RunPhase.Event;
        engine.State.CurrentNodeType = RunConstants.NodeEvent;
        engine.State.LastResolvedRoomType = RunConstants.NodeEvent;
        engine.State.NeowAwaitingProceed = false;
        engine.State.EventAwaitingProceed = false;
        engine.State.PlayerHp = 30;
        return engine;
    }

    private static int[] Offered(RunEngine engine)
    {
        var mask = new int[RunConstants.MaxActions];
        engine.WriteActionMask(mask);
        // The original event tests stopped before EventSkipAction and missed slot 3.
        return Enumerable.Range(0, mask.Length).Where(i => mask[i] != 0).ToArray();
    }

    [Theory]
    [InlineData(RunConstants.EventDenseVegetation)]
    [InlineData(RunConstants.EventPunchOff)]
    [InlineData(RunConstants.EventTheLanternKey)]
    public void InitialEventMaskIsPreservedByTheContinuationRepair(int eventId)
    {
        var engine = AtEvent(eventId);
        // Preserve the historical initial-page surface; this is not a live-parity claim.
        Assert.Equal(new[] { 0, 1, RunConstants.EventSkipAction }, Offered(engine));
    }

    [Theory]
    [InlineData(RunConstants.EventDenseVegetation)]
    [InlineData(RunConstants.EventPunchOff)]
    [InlineData(RunConstants.EventTheLanternKey)]
    public void CommittingToTheFightOffersOnlyTheAcceptedContinuation(int eventId)
    {
        var engine = AtEvent(eventId);
        Assert.Equal(0, engine.Step(1, -1, out _, out bool terminal, out _));
        Assert.False(terminal);
        Assert.Equal(RunPhase.Event, engine.State.Phase);
        Assert.Equal(1, engine.State.EventPage);
        Assert.Equal(new[] { 0 }, Offered(engine));

        var before = new int[RunConstants.RunObsSize];
        var after = new int[RunConstants.RunObsSize];
        engine.WriteObservation(before);
        Assert.Equal(-1, engine.Step(RunConstants.EventSkipAction, -1, out _, out _, out _));
        engine.WriteObservation(after);
        Assert.Equal(before, after);
        Assert.Equal(new[] { 0 }, Offered(engine));
    }

    [Theory]
    [InlineData(RunConstants.EventDenseVegetation, RunConstants.DenseVegetationEncounterId)]
    [InlineData(RunConstants.EventPunchOff, RunConstants.PunchOffEncounterId)]
    [InlineData(RunConstants.EventTheLanternKey, RunConstants.MysteriousKnightEncounterId)]
    public void EveryAdvertisedContinuationStartsTheExpectedPlayableFight(int eventId, int encounterId)
    {
        var engine = AtEvent(eventId);
        Assert.Equal(0, engine.Step(1, -1, out _, out _, out _));
        int hp = engine.State.PlayerHp;
        int gold = engine.State.Gold;
        int deck = engine.State.Deck.Count;
        int[] offered = Offered(engine);
        Assert.Single(offered);
        Assert.Equal(0, engine.Step(offered[0], -1, out float reward, out bool terminal, out _));

        Assert.False(terminal);
        Assert.Equal(0f, reward);
        Assert.Equal(RunPhase.Combat, engine.State.Phase);
        Assert.Equal(encounterId, engine.ActiveEncounterId);
        Assert.NotNull(engine.State.ActiveCombat);
        Assert.NotEmpty(engine.State.ActiveCombat!.Enemies);
        Assert.Equal(hp, engine.State.ActiveCombat.PlayerHp);
        Assert.Equal(gold, engine.State.ActiveCombat.PlayerGold);
        Assert.Equal(deck, engine.State.ActiveCombat.Hand.Count + engine.State.ActiveCombat.DrawPile.Count);
        Assert.NotEmpty(Offered(engine));
    }
}
