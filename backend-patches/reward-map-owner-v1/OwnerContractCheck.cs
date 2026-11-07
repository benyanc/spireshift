using Sts2Headless;

var owner = new RewardMapPresentationOwner();
var skipped = new RewardIdentity(11);
var other = new RewardIdentity(11); // Same contents, different native instance.
void Require(bool condition, string message)
{
    if (!condition) throw new InvalidOperationException(message);
}

Require(!owner.IsOpen && !owner.RewardIsForeground(null), "No fabricated reward owner");
Require(owner.RewardIsForeground(skipped), "A normal reward screen must remain selectable");
owner.Open(skipped);
Require(owner.IsOpen && !owner.RewardIsForeground(skipped), "Map owns the dismissed reward screen");
Require(owner.RewardIsForeground(other), "New genuine rewards must supersede the map");
owner.Open(other);
Require(!owner.RewardIsForeground(skipped) && !owner.RewardIsForeground(other),
    "Repeated map openings retain each exact dismissed owner");
owner.Open(null);
Require(!owner.RewardIsForeground(skipped), "An unrelated HUD refresh cannot reopen rewards");
owner.Close();
Require(!owner.IsOpen && owner.RewardIsForeground(skipped), "New room clears presentation ownership");
owner.Open(null);
Require(owner.RewardIsForeground(skipped), "Map without rewards cannot suppress a new reward screen");
Console.WriteLine("Reward/map ownership: 8 controls pass; no game, optimizer or reward effects.");

internal sealed record RewardIdentity(int Gold);
