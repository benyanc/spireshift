# A8 archive replay effects and boss routes

The v4 batch has one verified Queen victory with 896 native deliveries and
four clean replay stops. Its report is
`sha256:fcc8ebea3efda8c51a19b616a030d9a4674678c3994f97b88c1e2239dae7a037`.
The fitting gate still requires at least three distinct verified winning worlds,
coverage of the declared decision families across all acts, and at least two
distinct openings, Act 1 bosses, and final bosses. The four saved prefixes
independently reconstructed all 1,178 native receipts.

| Journal | Saved deliveries | Verified next action and evidence |
| --- | ---: | --- |
| `3cb0429d17be9210` | 189 | Choose the boss at `(3,16)`. A native control reproduced the full prefix and entered Vantom combat on delivery 190. |
| `6739ccb495f9b471` | 708 | End Turn. Brand exhausted the only eligible card. The raw successor contains the exhausted Shockwave and drawn Hemokinesis. A real selector still uses its bound confirmation. |
| `6f7d841fbdf0bb23` | 73 | Play Abundance. The replay reader moves the three recorded opening discards out of the hand by physical copy and retains their discard lineage until a recorded move. |
| `28b20eb6e1e88812` | 208 | Claim the stolen card. The current native special-card offer has a generic label. Matching requires the corroborated source acquisition, the exact pre-claim deck and one bound offer. The successor must restore the card and consume the offer. |

The shipped map explicitly enables the boss from the last ordinary row and
handles a second boss before free-travel routing. The headless adapter applies
that same rule to the menu and its native vote validation. The v5 qualification
loads the separately built adapter with the frozen game, worker and converter.
The native control stopped at combat entry and verified clean shutdown and all
four full checkpoint and Adam states. Its report is
`sha256:51222d214317b12cbdeb7d72c1b6699834108682f5ed225dbc457ed7bdd10cc3`.

Close STS2 and allow up to nine minutes for the full qualification.

```bash
bash scripts/qualify-a8-archive-batch-v5.sh
```

The runner verifies the saved control and the four earlier clean prefixes,
starts each replay from Neow, and checks public inputs and native receipts
against the saved prefix. Only genuine native victories contribute answers.
Uncertain delivery stops the batch with its evidence preserved. The declared
development and final-test worlds stay reserved. The batch performs zero
optimizer updates and leaves fitting for a separate admission decision.
