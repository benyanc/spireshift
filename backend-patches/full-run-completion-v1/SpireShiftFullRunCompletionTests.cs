using Sts2Emulator.Core.Run;
using Xunit;

namespace Sts2Emulator.Tests;

// Synthetic engine fixtures, never evidence of an agent win or game conformance.
public class SpireShiftFullRunCompletionTests
{
    private static RunEngine InAct(int actIndex)
    {
        var engine = new RunEngine();
        engine.Reset("100035");
        for (int i = 0; i < actIndex; i++)
        {
            Assert.True(engine.EnterNextAct());
        }
        engine.State.NeowAwaitingProceed = false;
        engine.State.EventAwaitingProceed = false;
        return engine;
    }

    [Theory]
    [InlineData(0, 19)]
    [InlineData(1, 19)]
    [InlineData(2, 35)]
    public void TotalFloorDoesNotEndAnEarlyRoomInTheCurrentAct(int actIndex, int totalFloor)
    {
        var engine = InAct(actIndex);
        var node = engine.State.MapNodes.Values.First(n => n.Row == 2);
        engine.State.CurrentMapCoord = (node.Col, node.Row);
        engine.State.CurrentNodeType = RunConstants.NodeRelic;
        engine.State.Floor = totalFloor;
        engine.State.Phase = RunPhase.Treasure;
        engine.State.LastPlayerWon = true;

        Assert.Equal(0, engine.Step(RunConstants.RewardSkipAction, -1, out _, out bool terminal, out _));
        Assert.False(terminal);
        Assert.Equal(RunPhase.Map, engine.State.Phase);
        Assert.Equal(actIndex, engine.State.CurrentActIndex);
        Assert.Equal(totalFloor, engine.State.Floor);
    }

    [Fact]
    public void DefensiveEndingCannotReuseThePreviousCombatWin()
    {
        var engine = InAct(1);
        engine.State.CurrentMapCoord = (3, RunMapGenerator.BossRow(engine.State));
        engine.State.CurrentNodeType = RunConstants.NodeRelic;
        engine.State.Phase = RunPhase.Treasure;
        engine.State.Floor = 100;
        engine.State.LastPlayerWon = true;

        Assert.Equal(0, engine.Step(RunConstants.RewardSkipAction, -1, out _, out bool terminal, out _));
        Assert.True(terminal);
        Assert.Equal(RunPhase.Complete, engine.State.Phase);
        Assert.False(engine.State.LastPlayerWon);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    public void EarlierBossRewardsEnterTheNextAct(int actIndex)
    {
        var engine = InAct(actIndex);
        engine.State.CurrentNodeType = RunConstants.NodeBoss;
        engine.State.Phase = RunPhase.RelicReward;
        engine.State.LastPlayerWon = true;

        Assert.Equal(0, engine.Step(RunConstants.RewardSkipAction, -1, out _, out bool terminal, out _));
        Assert.False(terminal);
        Assert.Equal(RunPhase.Map, engine.State.Phase);
        Assert.Equal(actIndex + 1, engine.State.CurrentActIndex);
    }

    [Fact]
    public void OnlyTheLastBossRewardCompletesTheRunAsAVictory()
    {
        var engine = InAct(2);
        engine.State.CurrentNodeType = RunConstants.NodeBoss;
        engine.State.Phase = RunPhase.RelicReward;
        engine.State.LastPlayerWon = true;

        Assert.Equal(0, engine.Step(RunConstants.RewardSkipAction, -1, out _, out bool terminal, out _));
        Assert.True(terminal);
        Assert.Equal(RunPhase.Complete, engine.State.Phase);
        Assert.True(engine.State.LastPlayerWon);
        Assert.Equal(2, engine.State.CurrentActIndex);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void FourthRewardLivesAfterTheCombatAndRunBlocks(bool upgraded)
    {
        var engine = InAct(0);
        engine.State.Phase = RunPhase.CardReward;
        int cardId = engine.State.Deck[0].DefId;
        engine.State.LastingCandyRewardCard = cardId;
        engine.State.LastingCandyRewardUpgraded = upgraded;
        var observation = new int[RunConstants.RunObsSize];

        engine.WriteObservation(observation);

        int fourth = RunConstants.CombatObsSize + RunConstants.FourthRewardObsOffset;
        Assert.Equal(cardId, observation[fourth]);
        Assert.Equal(upgraded ? 1 : 0, observation[fourth + 1]);
        for (int i = 0; i < engine.State.Deck.Count; i++)
        {
            int at = RunConstants.CombatObsSize + RunConstants.DeckObsOffset + i * RunConstants.DeckSlotSize;
            Assert.Equal(engine.State.Deck[i].DefId, observation[at]);
        }
    }
}
