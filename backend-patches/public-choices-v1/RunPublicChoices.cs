namespace Sts2Emulator.Core.Run;

/// <summary>Only objects on a currently open player menu; never hidden pile order or RNG.</summary>
public static class RunPublicChoices
{
    public const int Version = 1;
    public const int SelectionHeaderSize = 7;
    public const int CardSize = 4;

    public static int[] CombatSelection(RunState run) =>
        run.Phase == RunPhase.Combat && run.ActiveCombat is { } combat
            ? CombatSelection(combat)
            : [];

    public static int[] CombatSelection(CombatState combat)
    {
        if (combat.PendingSelection is not { } selection)
        {
            return [];
        }

        if (!Enum.IsDefined(selection.Kind) || selection.Kind == CardSelectionKind.None)
        {
            throw new InvalidOperationException("Unknown public selection kind");
        }

        int[] result = new int[SelectionHeaderSize + selection.Candidates.Count * CardSize];
        result[0] = Version;
        result[1] = (int)selection.Kind;
        result[2] = selection.SourceCardDefId;
        result[3] = selection.Amount;
        result[4] = selection.Skippable ? 1 : 0;
        result[5] = selection.GeneratedRetained ? 1 : 0;
        result[6] = selection.Candidates.Count;
        var pile = selection.Kind switch
        {
            CardSelectionKind.DiscardToDrawPileTop or CardSelectionKind.DiscardToHand =>
                combat.DiscardPile,
            CardSelectionKind.DrawPileToHand
                or CardSelectionKind.TransformDrawPileToSoul
                or CardSelectionKind.ExhaustFromDrawPile
                or CardSelectionKind.TransformDrawToMinionDiveBomb => combat.DrawPile,
            _ => combat.Hand,
        };
        bool generated = selection.Kind
            is CardSelectionKind.GeneratedCardToHand or CardSelectionKind.CurseOfKnowledge;
        for (int action = 0; action < selection.Candidates.Count; action++)
        {
            int sourceIndex = selection.Candidates[action];
            if (sourceIndex < 0 || sourceIndex >= (generated ? selection.GeneratedCandidates.Count : pile.Count))
            {
                throw new InvalidOperationException("Public selection candidate is out of bounds");
            }

            CardInstance card = generated
                ? new CardInstance(selection.GeneratedCandidates[sourceIndex], selection.GeneratedUpgraded)
                : pile[sourceIndex];
            int at = SelectionHeaderSize + action * CardSize;
            result[at] = card.DefId;
            result[at + 1] = card.Upgraded ? 1 : 0;
            result[at + 2] = (int)card.Enchantment;
            result[at + 3] = card.EnchantAmount;
        }

        return result;
    }

    public static int[] BundleSelection(RunState run) =>
        run.Phase == RunPhase.BundleSelect
            ? [Version, run.SelectedBundle, run.SelectedBundle >= 0 ? 1 : 0]
            : [];

    // A source declaration, not proof of live-game conformance. Run reset has no difficulty argument.
    public static int[] FixedProfile() => [Version, Ascension.DefaultLevel, 0];

    /// <summary>22 = offered combat cards, 23 = selected bundle, 24 = capability/fixed profile.</summary>
    /// <returns>Required size (also on a short/zero buffer), or a negative error.</returns>
    public static int WriteStateList(RunState run, int listId, Span<int> output)
    {
        int[] values;
        try
        {
            values = listId switch
            {
                22 => CombatSelection(run),
                23 => BundleSelection(run),
                24 => FixedProfile(),
                _ => throw new ArgumentOutOfRangeException(nameof(listId)),
            };
        }
        catch (InvalidOperationException)
        {
            return -4; // Invalid candidate binding, never an empty successful menu.
        }

        values.AsSpan(0, Math.Min(values.Length, output.Length)).CopyTo(output);
        return values.Length;
    }
}
