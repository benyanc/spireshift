# Soul Nexus death presentation guard

In the frozen v0.111.0 / 41cef1ea assembly, `SoulNexus.AfterDeath(Creature)`
unsubscribes from the native death event and looks up a scene node to stop
its spine animation. The headless host has no combat room scene.

The patch binds exactly one native `GetCreatureNode` call inside that callback.
It returns an absent presentation node when the test-mode room is absent.
The native event unsubscribe, death resolution, combat completion and
reward generation keep their original owners. The graphical call still
delegates to the native lookup.
