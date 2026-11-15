# Shared-head A8 later-act training result

The study finished all eight rounds for both initializers. It sealed
254 of 256 scheduled training games and recorded 720 optimizer
updates on copies. The two earlier failed Act 2 starts retain their
original evidence and supplied zero samples.

| Training origin | Completed games | Native terminal wins | Progress |
| --- | ---: | ---: | --- |
| Normal start | 128 | 0 | 3 Act 1 clears |
| Prepared Act 2 | 62 | 0 | 15 Act 2 clears |
| Prepared Act 3 | 64 | 18 | 9 winning worlds, each cleared by both initializers |

Every prepared victory used the same `fit-045` pre-boss profile.
The native outcomes confirm that the policy can finish from some
prepared states. The fresh comparison measures whether the trained
copies can reach and beat the final boss from Neow.

| Initializer | Parent A8 wins | Fitted A8 wins | Parent Act 1 clears | Fitted Act 1 clears |
| --- | ---: | ---: | ---: | ---: |
| Player 2 | 0/32 | 0/32 | 3/32 | 1/32 |
| Player 3 | 0/32 | 0/32 | 0/32 | 0/32 |
| Total | 0/64 | 0/64 | 3/64 | 1/64 |

All 128 fresh games ended in verified native losses. Neither arm
cleared Act 2. Player 2's fitted copy cleared Act 1 on one of the same
three worlds as its parent. The two other clears went to the parent
alone. Two discordant pairs leave substantial uncertainty about the
Act 1 effect. The study compares the mixed training copies to their
frozen parents. A matched normal-only learner would be needed to
isolate the effect of later-act exposure.

The saved audit reloaded the full optimizer lineage, verified all
382 game seals and reconstructed the matched evaluation. The frozen
game, runtime, SDK, localization, and four original checkpoints and
their full Adam states passed verification. The completed run's report is
`sha256:0d6e1b4580a9b88c7a29381e94fc1974586e9f163a6ac21cfa8498465dbdb18c`.
The saved audit made zero optimizer updates and launched zero games.

Act 1 is still the main obstacle on normal starts. The next
[replay comparison](native-a8-act1-success-replay-v1.md) uses
verified model-owned normal-start clears across independent
worlds and measures transfer on new normal starts.
