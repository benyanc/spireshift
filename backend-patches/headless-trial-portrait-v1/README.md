# Headless Trial portrait guard

On v0.111.0 / 41cef1ea, `Trial.Accept` has two local-player guards around
portrait clear and portrait replacement. `Trial.AddVfxAnchoredToPortrait` has
one around scene loading and attachment. The event presentation bridge rewrites
these three calls for TestMode. The native Accept body still selects its own
entrant and publishes the associated choices. Each verdict runs the game's
existing effect and completion code.

The guard checks both method identities and their exact call counts. The build
and event controls bind the game assembly, previous support library, and native
worker input contract. Double Down's abandon confirmation is a separate modal
interaction outside this repair.
