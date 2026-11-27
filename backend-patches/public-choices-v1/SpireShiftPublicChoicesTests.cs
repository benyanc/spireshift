using Sts2Emulator.Core;
using Sts2Emulator.Core.Run;
using Xunit;

namespace Sts2Emulator.Tests;

public sealed class SpireShiftPublicChoicesTests
{
    private static PendingCardSelection Selection(CardSelectionKind kind, params int[] candidates) =>
        new() { Kind = kind, Candidates = [.. candidates], SourceCardDefId = 0, Amount = 1 };

    [Fact]
    public void EveryOfferedCardBeyondTenIsExposedAndVectorPrefixAgrees()
    {
        var combat = new CombatState();
        combat.DiscardPile = [.. Enumerable.Range(1, 15).Select(i => new CardInstance(i, i % 2 == 0))];
        combat.PendingSelection = Selection(CardSelectionKind.DiscardToHand, [.. Enumerable.Range(0, 15)]);
        int[] menu = RunPublicChoices.CombatSelection(combat);
        Assert.Equal(67, menu.Length);
        Assert.Equal(15, menu[6]);
        Assert.Equal(15, menu[7 + 14 * 4]);
        int[] obs = new int[CombatObservation.ObsSize];
        CombatObservation.Write(combat, obs);
        Assert.Equal(15, obs[CombatObservation.SelectionCountOffset]);
        Assert.Equal(menu.AsSpan(7, 40).ToArray(), obs.AsSpan(CombatObservation.SelectionOffset, 40).ToArray());
    }

    [Theory]
    [InlineData(CardSelectionKind.DrawPileToHand)]
    [InlineData(CardSelectionKind.TransformDrawPileToSoul)]
    [InlineData(CardSelectionKind.ExhaustFromDrawPile)]
    [InlineData(CardSelectionKind.TransformDrawToMinionDiveBomb)]
    [InlineData(CardSelectionKind.DiscardToDrawPileTop)]
    [InlineData(CardSelectionKind.DiscardToHand)]
    public void OfferedIndexResolvesToTheCorrectPile(CardSelectionKind kind)
    {
        var combat = new CombatState();
        combat.Hand = [new CardInstance(1, false), new CardInstance(2, false)];
        combat.DrawPile = [new CardInstance(11, false), new CardInstance(12, true)];
        combat.DiscardPile = [new CardInstance(21, false), new CardInstance(22, true)];
        combat.PendingSelection = Selection(kind, 1, 0);
        bool discard = kind is CardSelectionKind.DiscardToDrawPileTop or CardSelectionKind.DiscardToHand;
        int[] menu = RunPublicChoices.CombatSelection(combat);
        Assert.Equal(discard ? 22 : 12, menu[7]);
        Assert.Equal(1, menu[8]);
        Assert.Equal(discard ? 21 : 11, menu[11]);
    }

    [Theory]
    [InlineData(CardSelectionKind.GeneratedCardToHand)]
    [InlineData(CardSelectionKind.CurseOfKnowledge)]
    public void GeneratedOptionsUseActualCandidateIndicesAndVisibleUpgrades(CardSelectionKind kind)
    {
        var combat = new CombatState();
        combat.PendingSelection = new PendingCardSelection
        {
            Kind = kind, Candidates = [2, 0], GeneratedCandidates = [30, 40, 50],
            GeneratedUpgraded = true, GeneratedRetained = true, Skippable = true,
            SourceCardDefId = 0, Amount = 2,
        };
        int[] menu = RunPublicChoices.CombatSelection(combat);
        Assert.Equal(new[] { 1, (int)kind, 0, 2, 1, 1, 2, 50, 1, 0, 0, 30, 1, 0, 0 }, menu);
        int[] obs = new int[CombatObservation.ObsSize];
        CombatObservation.Write(combat, obs);
        Assert.Equal(menu.AsSpan(7, 8).ToArray(), obs.AsSpan(CombatObservation.SelectionOffset, 8).ToArray());
    }

    [Fact]
    public void UnofferedHiddenCardsCannotEnterTheMenu()
    {
        var combat = new CombatState();
        combat.DrawPile = [new CardInstance(30, true), new CardInstance(40, false), new CardInstance(50, false)];
        combat.PendingSelection = Selection(CardSelectionKind.DrawPileToHand, 0);
        int[] before = RunPublicChoices.CombatSelection(combat);
        combat.DrawPile[1] = new CardInstance(999, true);
        combat.DrawPile.Reverse(1, 2);
        Assert.Equal(before, RunPublicChoices.CombatSelection(combat));
        Assert.Equal(new[] { 1, 4, 0, 1, 0, 0, 1, 30, 1, 0, 0 }, before);
    }

    [Fact]
    public void ClosedMenuAndStaleCombatExposeNoCards()
    {
        var run = new RunState { Phase = RunPhase.Combat, ActiveCombat = new CombatState() };
        Assert.Empty(RunPublicChoices.CombatSelection(run));
        run.ActiveCombat.Hand = [new CardInstance(30, false)];
        run.ActiveCombat.PendingSelection = Selection(CardSelectionKind.ExhaustFromHand, 0);
        run.Phase = RunPhase.Map;
        Assert.Empty(RunPublicChoices.CombatSelection(run));
    }

    [Fact]
    public void BundleReadoutTracksSelectionAndConfirmationWithoutChangingIt()
    {
        var run = new RunState { Phase = RunPhase.BundleSelect, BundleOffer = [1, 2, 3, 4, 5, 6] };
        Assert.Equal(new[] { 1, -1, 0 }, RunPublicChoices.BundleSelection(run));
        run.SelectedBundle = 1;
        Assert.Equal(new[] { 1, 1, 1 }, RunPublicChoices.BundleSelection(run));
        Assert.Equal(1, run.SelectedBundle);
        run.Phase = RunPhase.Map;
        Assert.Empty(RunPublicChoices.BundleSelection(run));
    }

    [Fact]
    public void FixedProfileMatchesSourceDefaultsAndResetResources()
    {
        var run = new RunEngine();
        run.Reset("1");
        Assert.Equal(new[] { 1, 8, 0 }, RunPublicChoices.FixedProfile());
        Assert.Equal(64, run.State.PlayerHp);
        Assert.Equal(80, run.State.PlayerMaxHp);
        Assert.Equal(2, run.State.MaxPotionSlots);
        Assert.Contains(run.State.Deck, c => c.DefId == RunConstants.CardAscendersBane);
        Assert.Equal(8, new CombatState().AscensionLevel);
    }

    [Fact]
    public void BufferQueriesReportRequiredSizeAndBadBindingsAreErrors()
    {
        var run = new RunState { Phase = RunPhase.Combat, ActiveCombat = new CombatState() };
        Assert.Equal(3, RunPublicChoices.WriteStateList(run, 24, Span<int>.Empty));
        int[] shortBuffer = new int[1];
        Assert.Equal(3, RunPublicChoices.WriteStateList(run, 24, shortBuffer));
        Assert.Equal(1, shortBuffer[0]);
        run.ActiveCombat.PendingSelection = Selection(CardSelectionKind.ExhaustFromHand, 100);
        Assert.Equal(-4, RunPublicChoices.WriteStateList(run, 22, Span<int>.Empty));
    }
}
