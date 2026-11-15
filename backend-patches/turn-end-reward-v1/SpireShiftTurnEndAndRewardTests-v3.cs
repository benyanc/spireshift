using Sts2Emulator.Core;
using Sts2Emulator.Core.Effects;
using Sts2Emulator.Core.Run;
using Xunit;

namespace Sts2Emulator.Tests;

// Expected hook/flush ordering: frozen v0.107.1 CombatManager.DoTurnEnd and
// FlushPlayerHand. BadLuck loses 13 HP; CentennialPuzzle draws three once.
// Privileged setup is only for regression checks, never a policy observation.
public class SpireShiftTurnEndAndRewardTests
{
    private static Fight Holding(params int[] ids)
    {
        var fight = Fight.Hand(ids.Select(id => new CardInstance(id, false)).ToArray()).Enemy();
        fight.State.PlayerHp = 100;
        fight.State.PlayerMaxHp = 100;
        fight.State.PlayerBlock = 0;
        fight.State.DiscardPile.Clear();
        fight.State.ExhaustPile.Clear();
        return fight;
    }

    private static CardInstance[] Drawn(int first) =>
        Enumerable
            .Repeat(new CardInstance(first, false), 3)
            .Concat(Enumerable.Repeat(new CardInstance(IC.StrikeIronclad, false), 5))
            .ToArray();

    [Fact]
    public void StatusDrawsAreFlushedWithoutMutationOrCardLoss()
    {
        var fight = Holding(ST.BadLuck, IC.DefendIronclad).Draw(Drawn(IC.Bash));
        fight.State.Relics = [new RelicInstance(RelicEffects.CentennialPuzzle)];
        fight.EndTurn();
        Assert.Equal(87, fight.State.PlayerHp);
        Assert.Equal(5, fight.State.Hand.Count);
        Assert.All(fight.State.Hand, c => Assert.Equal(IC.StrikeIronclad, c.DefId));
        Assert.Equal(5, fight.State.DiscardPile.Count);
        Assert.Equal(3, fight.State.DiscardPile.Count(c => c.DefId == IC.Bash));
        Assert.Empty(fight.State.DrawPile);
    }

    [Fact]
    public void RegretUsesTheInitialHandCountWhenDamageDrawsCards()
    {
        var fight = Holding(ST.Regret, IC.DefendIronclad).Draw(Drawn(IC.Bash));
        fight.State.Relics = [new RelicInstance(RelicEffects.CentennialPuzzle)];
        fight.EndTurn();
        Assert.Equal(98, fight.State.PlayerHp);
        Assert.Equal(5, fight.State.DiscardPile.Count);
        Assert.Equal(3, fight.State.DiscardPile.Count(c => c.DefId == IC.Bash));
    }

    [Fact]
    public void NewlyDrawnStatusesDoNotReceiveAnotherTurnEndHook()
    {
        var fight = Holding(ST.BadLuck).Draw(Drawn(ST.BadLuck));
        fight.State.Relics = [new RelicInstance(RelicEffects.CentennialPuzzle)];
        fight.EndTurn();
        Assert.Equal(87, fight.State.PlayerHp);
        Assert.Equal(4, fight.State.DiscardPile.Count(c => c.DefId == ST.BadLuck));
        Assert.Equal(9, fight.State.Hand.Count + fight.State.DiscardPile.Count);
    }

    [Fact]
    public void RetainIncludesCardsDrawnDuringTurnEnd()
    {
        var fight = Holding(ST.BadLuck, IC.DefendIronclad).Draw(Drawn(IC.Bash));
        fight.State.Relics = [new RelicInstance(RelicEffects.CentennialPuzzle)];
        BuffSystem.Apply(fight.State.PlayerBuffs, BuffId.RetainHand, 1);
        fight.EndTurn();
        Assert.Equal(87, fight.State.PlayerHp);
        Assert.Equal(10, fight.State.Hand.Count);
        Assert.Empty(fight.State.DiscardPile);
        Assert.Empty(fight.State.DrawPile);
        Assert.Equal(3, fight.State.Hand.Count(c => c.DefId == IC.Bash));
    }

    [Fact]
    public void EtherealHooksPrecedeStatusDamageRegardlessOfHandOrder()
    {
        int apparition = GeneratedData.Cards.FindId("Apparition")!.Value;
        var fight = Holding(ST.Burn, apparition).Draw(Drawn(IC.StrikeIronclad));
        BuffSystem.Apply(fight.State.PlayerBuffs, BuffId.FeelNoPain, 3);
        fight.EndTurn();
        Assert.Equal(100, fight.State.PlayerHp); // Exhaust block absorbs Burn's two damage.
        Assert.Single(fight.State.ExhaustPile, c => c.DefId == apparition);
        Assert.Contains(fight.State.DiscardPile, c => c.DefId == ST.Burn);
    }

    private static int[] Offered(RunEngine engine)
    {
        var mask = new int[RunConstants.MaxActions];
        engine.WriteActionMask(mask);
        return Enumerable.Range(0, mask.Length).Where(i => mask[i] != 0).ToArray();
    }

    [Fact]
    public void EmptyCardRewardOffersOnlySkipAndRejectsAbsentCards()
    {
        var engine = new RunEngine();
        engine.Reset("123");
        engine.State.Phase = RunPhase.CardReward;
        Array.Clear(engine.State.RewardCards);
        Assert.Equal(new[] { RunConstants.RewardSkipAction }, Offered(engine));
        foreach (int action in Enumerable.Range(0, 3))
        {
            Assert.Equal(
                -1,
                engine.Step(action, -1, out float reward, out bool terminal, out bool truncated)
            );
            Assert.Equal(0f, reward);
            Assert.False(terminal);
            Assert.False(truncated);
            Assert.Equal(RunPhase.CardReward, engine.State.Phase);
        }
        Assert.Equal(0, engine.Step(RunConstants.RewardSkipAction, -1, out _, out _, out _));
        Assert.NotEqual(RunPhase.CardReward, engine.State.Phase);
    }

    [Fact]
    public void PartialCardRewardPreservesGenuineAndSpecialChoices()
    {
        var engine = new RunEngine();
        engine.Reset("123");
        engine.State.Phase = RunPhase.CardReward;
        engine.State.RewardCards[0] = IC.StrikeIronclad;
        engine.State.RewardCards[1] = 0;
        engine.State.RewardCards[2] = IC.Bash;
        engine.State.LastingCandyRewardCard = IC.DefendIronclad;
        engine.State.CardRewardRerollAvailable = true;
        Assert.Equal(new[] { 0, 2, 3, 5, 6 }, Offered(engine));
        Assert.Equal(-1, engine.Step(1, -1, out _, out _, out _));
        Assert.Equal(0, engine.Step(2, -1, out _, out _, out _));
        Assert.Equal(IC.Bash, engine.State.Deck.Last().DefId);
    }
}
