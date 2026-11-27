# Native reward-generation comparison

This repository-owned helper checks the frozen game's Calling Bell and Cauldron reward
generation and population. Raw outputs include private RNG and relic-pool state and belong
only under ignored `artifacts/`. They are never player observations, training labels or
full-run results.

Build with the local SDK, passing the qualified wrapper checkout as `CandidateDirectory`
and storing intermediate/output files under `artifacts/`. The project references the MIT
wrapper and locally licensed game but neither copies nor commits those assemblies.
The built helper resolves dependencies from the chosen wrapper's output and `lib` folders.
Run using the separately pinned .NET 9.0.7 runtime.

`spireshift engine check-native-reward-generation` binds the helper, source hashes, two
qualified build reports, complete candidate inventories, exact runtime and extracted native
localization. Its recipe fixes two Ironclad/A8 seeds, both relics and two repeats. Each of
eight cases uses three disposable native profiles:

- The original v10 wrapper, with TestMode disabled only during the original GenerateRewards call.
- The original v10 test branch, which exposes preset rewards.
- The repaired v11 wrapper with TestMode retained.

All three share native initialization, stubs and subsequent Populate behavior. Comparisons
require identical starting RNG/pools, matching repaired rewards and final RNG/pools, an
exposed original shortcut, identical repeats and unchanged archive/profile/input files.
This covers generation and population only. It does not test AfterObtained, curse delivery,
reward claims, capacity, skip/cancel, nested pickup hooks or shipped UI behavior. Those need
separate native/shipped comparisons. Neither a pass nor this helper admits training.

The completed v11/v1 report preserves eight cases, 24 native fixture starts and zero full-run
attempts or reward selections. A rerun refuses existing or interrupted result folders.
