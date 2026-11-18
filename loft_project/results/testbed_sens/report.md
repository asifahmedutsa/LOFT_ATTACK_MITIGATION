# Sensitivity of FEVER to its fixed settings (T1B)

docs/sensitivity_prereg.md. One setting changed at a time; default FEVER's runs from results/testbed_prereg_final (attacks, benign only) and results/testbed_flash2 (one-host crowd). Means over three seeds.

## R1: attacks (harm at most 0.5 point and occupancy at most 5 points above default FEVER)

| Setting | Attack | Harm % | Default | Occupancy % | Default | New-connection success % | Default | First block s | Default | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| rho 0.6 | G2 | 0.007 | 0.003 | 2.22 | 4.82 | 100.0 | 98.8 | 55 | 79 | pass |
| rho 0.6 | Mimic | 0.010 | 0.017 | 2.15 | 4.89 | 99.0 | 97.0 | 56 | 81 | pass |
| rho 0.6 | Aware | 0.363 | 0.003 | 15.85 | 14.29 | 41.7 | 49.3 | 99 | 94 | pass |
| rho 0.8 | G2 | 0.003 | 0.003 | 6.16 | 4.82 | 95.1 | 98.8 | 87 | 79 | pass |
| rho 0.8 | Mimic | 0.017 | 0.017 | 15.05 | 4.89 | 64.8 | 97.0 | 108 | 81 | fail |
| rho 0.8 | Aware | 0.007 | 0.003 | 12.04 | 14.29 | 57.7 | 49.3 | 82 | 94 | pass |
| k 2 | G2 | 0.010 | 0.003 | 4.56 | 4.82 | 99.2 | 98.8 | 76 | 79 | pass |
| k 2 | Mimic | 0.003 | 0.017 | 4.90 | 4.89 | 97.0 | 97.0 | 81 | 81 | pass |
| k 2 | Aware | 0.007 | 0.003 | 12.68 | 14.29 | 54.1 | 49.3 | 87 | 94 | pass |
| k 4 | G2 | 0.007 | 0.003 | 4.57 | 4.82 | 99.0 | 98.8 | 76 | 79 | pass |
| k 4 | Mimic | 0.017 | 0.017 | 4.93 | 4.89 | 97.4 | 97.0 | 81 | 81 | pass |
| k 4 | Aware | 0.010 | 0.003 | 11.68 | 14.29 | 56.1 | 49.3 | 85 | 94 | pass |
| volume x1.25 | G2 | 0.003 | 0.003 | 4.62 | 4.82 | 99.1 | 98.8 | 77 | 79 | pass |
| volume x1.25 | Mimic | 0.007 | 0.017 | 4.72 | 4.89 | 98.3 | 97.0 | 80 | 81 | pass |
| volume x1.25 | Aware | 0.007 | 0.003 | 12.33 | 14.29 | 55.9 | 49.3 | 85 | 94 | pass |
| volume x2.0 | G2 | 0.003 | 0.003 | 4.62 | 4.82 | 98.7 | 98.8 | 77 | 79 | pass |
| volume x2.0 | Mimic | 0.007 | 0.017 | 4.71 | 4.89 | 98.5 | 97.0 | 79 | 81 | pass |
| volume x2.0 | Aware | 0.003 | 0.003 | 13.10 | 14.29 | 52.5 | 49.3 | 87 | 94 | pass |

R1: 17 of 18 setting-attack pairs pass.

## R2: no attack (no benign host blocked)

| Setting | Runs counted | Benign host blocks | Harm % | Default harm % | Result |
|---|---|---|---|---|---|
| rho 0.6 | 3 | 0 | 0.000 | 0.000 | pass |
| rho 0.8 | 3 | 0 | 0.000 | 0.000 | pass |
| k 2 | 3 | 0 | 0.000 | 0.000 | pass |
| k 4 | 3 | 0 | 0.000 | 0.000 | pass |
| volume x1.25 | 3 | 0 | 0.000 | 0.000 | pass |
| volume x2.0 | 3 | 0 | 0.000 | 0.000 | pass |

R2: 6 of 6 settings pass.

## R3: one-host crowd (F2H, capacity 2,000; reported, not tested)

| Setting | Runs counted | Runs with the crowd host blocked | Harm % | No defense harm % | Result |
|---|---|---|---|---|---|
| Default (round 2) | 3 | 2 | 4.890 | 0.000 | – |
| rho 0.6 | 3 | 3 | 22.980 | 0.000 | does not avoid it |
| rho 0.8 | 3 | 3 | 22.877 | 0.000 | does not avoid it |
| k 2 | 3 | 3 | 29.423 | 0.000 | does not avoid it |
| k 4 | 3 | 3 | 24.857 | 0.000 | does not avoid it |
| volume x1.25 | 3 | 3 | 29.370 | 0.000 | does not avoid it |
| volume x2.0 | 3 | 3 | 29.533 | 0.000 | does not avoid it |

- rho 0.6, seed 4187: d1h3 blocked on s11 at 119 s, eviction (table 84 %, d1h3 held 966, median 241)
- rho 0.6, seed 4188: d1h3 blocked on s11 at 62 s, volume (table 93 %, d1h3 held 1140, median 242)
- rho 0.6, seed 4189: d1h3 blocked on s11 at 249 s, eviction (table 87 %, d1h3 held 1026, median 288)
- rho 0.8, seed 4187: d1h3 blocked on s11 at 121 s, eviction (table 88 %, d1h3 held 1068, median 197)
- rho 0.8, seed 4188: d1h3 blocked on s11 at 61 s, eviction (table 85 %, d1h3 held 983, median 255)
- rho 0.8, seed 4189: d1h3 blocked on s11 at 249 s, volume (table 93 %, d1h3 held 1116, median 296)
- k 2, seed 4187: d1h3 blocked on s11 at 121 s, eviction (table 90 %, d1h3 held 1104, median 197)
- k 2, seed 4188: d1h3 blocked on s11 at 61 s, volume (table 90 %, d1h3 held 1086, median 244)
- k 2, seed 4189: d1h3 blocked on s11 at 49 s, volume (table 91 %, d1h3 held 1288, median 195)
- k 4, seed 4187: d1h3 blocked on s11 at 121 s, eviction (table 89 %, d1h3 held 1085, median 197)
- k 4, seed 4188: d1h3 blocked on s11 at 163 s, eviction (table 86 %, d1h3 held 1121, median 170)
- k 4, seed 4189: d1h3 blocked on s11 at 49 s, volume (table 90 %, d1h3 held 1262, median 198)
- volume x1.25, seed 4187: d1h3 blocked on s11 at 119 s, volume (table 91 %, d1h3 held 1092, median 243)
- volume x1.25, seed 4188: d1h3 blocked on s11 at 62 s, volume (table 92 %, d1h3 held 1118, median 244)
- volume x1.25, seed 4189: d1h3 blocked on s11 at 50 s, eviction (table 90 %, d1h3 held 1255, median 198)
- volume x2.0, seed 4187: d1h3 blocked on s11 at 119 s, volume (table 91 %, d1h3 held 1071, median 249)
- volume x2.0, seed 4188: d1h3 blocked on s11 at 62 s, volume (table 94 %, d1h3 held 1149, median 249)
- volume x2.0, seed 4189: d1h3 blocked on s11 at 49 s, volume (table 90 %, d1h3 held 1260, median 197)
