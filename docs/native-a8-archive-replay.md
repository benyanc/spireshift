# Reload-free Ironclad/A8 archive replay

The frozen native host replayed all three acts, defeated the Queen on floor 48,
and recorded a genuine victory after the Architect. The saved audit reconstructed
896 native action bindings, receipts and successors. The worker started once
from Neow, issued zero load or reset commands, and shut down cleanly.
[Qualification evidence](evidence/native-a8-archive-replay-v1.json)

The qualification uses the frozen Slay the Spire 2 build `v0.111.0+41cef1ea`
and the existing native worker and public converter. The replay reader consumes
the downloaded journal as data. It binds each recorded choice to the current
native menu and verifies each delivery against the worker's raw receipts and
successor observations.

The selected journal has 5,750 records, 22 complete combat attempts and three
acts. Its header declares zero reloads. The journal records the Queen's defeat
and the Architect choices. The archive marks the run as a win. Its internal end
record reports `death` after the Architect closes the run. Qualification
requires the frozen worker's explicit victory and a matching public terminal
frame. Native matched the recorded 38 HP before the Architect and the terminal
floor, maximum HP, deck and relic inventory. Its terminal record has both the
game-over and victory-room flags. [Selected replay](https://spire-codex.com/runs/ee2ffb605c67742f/replay)

The verifier matches card copies using the recorded hand, discard order and
permanent deck lineage when those views identify an exact copy. For an archive
entry that omits the slot of a potion, equivalent native copies with matching
public facts and targets use the lowest slot. The forced Architect Continue
page has no recorded gameplay effect and folds into the native Proceed menu.
An unresolved choice stops the attempt before delivery.

The engine, runtime, SDK, localization, full checkpoints and Adam passed the
frozen checks. The verified attempt took about 45 seconds from configuration
seal through saved receipt verification. It made zero optimizer updates.
Keep this world in the demonstration scope. Admission and fitting across
distinct worlds are separate steps.

## Source exclusions

- The first reload-free journal reached Act 2 floor 20. The journal records the
  Crystal Sphere payment and rewards, with no grid selections. The worker
  returned the raw grid but its public successor was unacknowledged. The
  242-action prefix and active marker stay preserved as diagnostics.
  [Crystal Sphere replay](https://spire-codex.com/runs/3b747e9621031ae1/replay)
- A second journal declared zero reloads and recorded three combat restarts
  with unmatched combat starts. The source check rejected it before launch.
  [Restarted replay](https://spire-codex.com/runs/9dc545337e0fc3eb/replay)

An earlier attempt on the selected journal reached a discard selector and
failed cleanup after the matcher stopped. The saved audit reconstructed all
606 acknowledged deliveries, identified the selected discard copy, and
confirmed the choice was unsent and the worker had exited. Its original
marker and profile stay preserved. The qualified attempt used a fresh process
and profile.

The public replay catalog and original journal endpoint are documented in the
[Spire Codex replay API](https://github.com/ptrlrd/spire-codex/blob/main/contributing/API_REFERENCE.md#replays).
