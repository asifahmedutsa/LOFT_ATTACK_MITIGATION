# Exploratory: how close is ensguard-v5 to DMS-BTT and FTMaster, per attack

**Not preregistered.** Added after the v5 campaign, at the user's request (2026-11-07), to describe where v5 is
close to the baselines rather than better. Source: results/testbed_prereg_v5/runs.csv (the same 120 runs).
Paired by seed; difference = v5 minus baseline (negative = v5 lower = better). 5 seeds per cell.

| Attack | Measure | Baseline | v5 mean | baseline mean | mean difference | min / max difference | v5 lower in |
|---|---|---|---|---|---|---|---|
| A2 | harm % | dms-btt | 1.05 | 0.02 | +1.03 | +0.02 / +1.76 | 0 of 5 |
| A2 | harm % | ftmaster | 1.05 | 0.01 | +1.03 | +0.02 / +1.78 | 0 of 5 |
| A2 | attack share s11 % | dms-btt | 12.62 | 18.67 | -6.05 | -9.67 / -0.27 | 5 of 5 |
| A2 | attack share s11 % | ftmaster | 12.62 | 9.98 | +2.64 | -3.74 / +5.36 | 1 of 5 |
| A4 | harm % | dms-btt | 0.32 | 2.09 | -1.77 | -3.70 / -0.03 | 5 of 5 |
| A4 | harm % | ftmaster | 0.32 | 4.16 | -3.84 | -5.39 / -2.12 | 5 of 5 |
| A4 | attack share s11 % | dms-btt | 27.23 | 47.58 | -20.36 | -24.10 / -12.78 | 5 of 5 |
| A4 | attack share s11 % | ftmaster | 27.23 | 53.36 | -26.13 | -32.70 / -7.80 | 5 of 5 |
| E9P | harm % | dms-btt | 0.10 | 3.01 | -2.91 | -3.73 / -1.23 | 5 of 5 |
| E9P | harm % | ftmaster | 0.10 | 10.22 | -10.12 | -12.57 / -6.19 | 5 of 5 |
| E9P | attack share s11 % | dms-btt | 25.96 | 59.30 | -33.34 | -42.20 / -28.78 | 5 of 5 |
| E9P | attack share s11 % | ftmaster | 25.96 | 73.29 | -47.33 | -51.81 / -41.93 | 5 of 5 |
