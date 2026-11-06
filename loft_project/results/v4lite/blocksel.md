# v4-lite step 3: block-rule floor (docs/v4lite_plan.md)

Detector: cb (model seed 0). Simulator: D1-D3, A2/A4/E9P/A6/benign x seeds 2000-2002 (closed loop). Replay: the 12 testbed entry logs x s11-s13 (open loop, T1 tau).

| Rule | harm % | attack occ % | benign hosts blocked (sim) | attack hosts blocked, A2 (sim, per episode) | benign hosts blocked (replay) | attack hosts blocked (replay; A2) | eligible |
|---|---|---|---|---|---|---|---|
| m010-f0.2 | 2.028 | 20.56 | 0 | 2.00 | 0 | 6 (6) | yes |
| m010-f0.3 | 2.384 | 23.38 | 0 | 2.00 | 0 | 6 (6) | yes |
| m010-f0.5 | 2.562 | 24.35 | 0 | 2.00 | 0 | 6 (6) | yes |
| m020-f0.2 | 2.028 | 20.56 | 0 | 2.00 | 0 | 6 (6) | yes |
| m020-f0.3 | 2.384 | 23.38 | 0 | 2.00 | 0 | 6 (6) | yes |
| m020-f0.5 | 2.562 | 24.35 | 0 | 2.00 | 0 | 6 (6) | yes |
| m040-f0.2 | 2.032 | 20.57 | 0 | 2.00 | 0 | 6 (6) | yes |
| m040-f0.3 | 2.389 | 23.42 | 0 | 2.00 | 0 | 6 (6) | yes |
| m040-f0.5 | 2.566 | 24.35 | 0 | 2.00 | 0 | 6 (6) | yes |
| v3rule | 0.633 | 6.35 | 0 | 2.00 | 4 | 6 (6) | no |

**Chosen: m010-f0.2.**
