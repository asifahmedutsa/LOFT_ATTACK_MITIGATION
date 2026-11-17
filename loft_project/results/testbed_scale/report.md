# More colluding attackers on T1B

docs/scale_prereg.md. Mean (s.d.) over seeds; n = 4 and 8 are seeds 4184-4186; n = 2 is the final campaign's 300 s T1B runs (G2 seeds 4160-4162, EVX seeds 4160-4164).

## G2

| Method | n | Occupancy % | Harm % | New-connection success % | Lost first packets % | Attackers blocked | Benign hosts blocked |
|---|---|---|---|---|---|---|---|
| No defense | 2 | 39.54 (1.10) | 10.603 (2.591) | 31.1 (3.2) | 21.27 (5.26) | 0 of 6 | 0 |
| No defense | 8 | 60.93 (0.97) | 16.343 (1.175) | 15.4 (0.8) | 45.12 (1.05) | 0 of 24 | 0 |
| FEVER | 2 | 4.82 (0.95) | 0.003 (0.006) | 98.8 (1.1) | 0.15 (0.16) | 6 of 6 | 0 |
| FEVER | 4 | 2.58 (0.43) | 0.003 (0.006) | 98.5 (2.5) | 0.06 (0.06) | 12 of 12 | 0 |
| FEVER | 8 | 11.15 (4.36) | 0.927 (0.806) | 52.3 (18.1) | 10.29 (8.17) | 24 of 24 | 0 |
| FTMaster | 2 | 24.92 (0.46) | 0.023 (0.012) | 41.2 (15.7) | 3.14 (2.58) | 0 of 6 | 0 |
| FTMaster | 4 | 11.35 (1.90) | 0.007 (0.006) | 51.1 (10.7) | 5.20 (4.99) | 0 of 12 | 0 |
| FTMaster | 8 | 29.67 (9.62) | 0.503 (0.674) | 17.9 (6.3) | 44.10 (11.13) | 0 of 24 | 0 |
| FTODefender | 2 | 0.29 (0.16) | 0.260 (0.017) | 100.0 (0.0) | 0.11 (0.17) | 0 of 6 | 0 |
| FTODefender | 4 | 0.17 (0.04) | 0.237 (0.031) | 100.0 (0.0) | 0.00 (0.00) | 0 of 12 | 0 |
| FTODefender | 8 | 0.30 (0.14) | 0.267 (0.015) | 98.9 (1.8) | 0.01 (0.01) | 0 of 24 | 0 |
| DMS-BTT | 2 | 26.83 (0.59) | 0.603 (1.002) | 28.6 (6.6) | 18.31 (1.78) | 0 of 6 | 0 |
| DMS-BTT | 4 | 27.18 (2.68) | 0.420 (0.701) | 24.2 (1.4) | 32.14 (2.16) | 0 of 12 | 0 |
| DMS-BTT | 8 | 34.79 (1.77) | 0.727 (0.674) | 15.7 (1.0) | 48.38 (1.62) | 0 of 24 | 0 |

## EVX

| Method | n | Occupancy % | Harm % | New-connection success % | Lost first packets % | Attackers blocked | Benign hosts blocked |
|---|---|---|---|---|---|---|---|
| No defense | 2 | 20.62 (0.17) | 0.000 (0.000) | 96.5 (7.5) | 0.11 (0.11) | 0 of 10 | 0 |
| No defense | 8 | 56.51 (0.64) | 12.100 (0.355) | 15.7 (1.0) | 28.43 (1.46) | 0 of 24 | 0 |
| FEVER | 2 | 17.71 (6.66) | 0.006 (0.013) | 98.6 (1.8) | 0.10 (0.11) | 2 of 10 | 0 |
| FEVER | 4 | 2.39 (0.59) | 0.000 (0.000) | 99.8 (0.2) | 0.04 (0.03) | 12 of 12 | 0 |
| FEVER | 8 | 27.10 (3.46) | 1.957 (0.785) | 13.7 (0.6) | 27.54 (12.53) | 20 of 24 | 0 |
| FTMaster | 2 | 20.48 (0.24) | 0.006 (0.013) | 88.1 (25.2) | 0.31 (0.35) | 0 of 10 | 0 |
| FTMaster | 4 | 22.36 (0.45) | 0.007 (0.006) | 56.9 (13.4) | 0.38 (0.18) | 0 of 12 | 0 |
| FTMaster | 8 | 19.26 (2.94) | 0.613 (0.686) | 20.8 (11.2) | 23.50 (4.85) | 0 of 24 | 0 |
| FTODefender | 2 | 0.22 (0.14) | 0.246 (0.039) | 100.0 (0.0) | 0.06 (0.10) | 0 of 10 | 0 |
| FTODefender | 4 | 0.19 (0.03) | 0.247 (0.032) | 100.0 (0.0) | 0.00 (0.00) | 0 of 12 | 0 |
| FTODefender | 8 | 0.33 (0.11) | 0.257 (0.035) | 98.8 (2.1) | 0.00 (0.00) | 0 of 24 | 0 |
| DMS-BTT | 2 | 14.05 (0.59) | 0.018 (0.019) | 95.1 (5.3) | 0.08 (0.10) | 0 of 10 | 0 |
| DMS-BTT | 4 | 26.86 (0.88) | 0.010 (0.010) | 26.3 (4.5) | 6.97 (2.81) | 0 of 12 | 0 |
| DMS-BTT | 8 | 26.38 (1.11) | 0.350 (0.470) | 16.0 (1.4) | 34.72 (1.37) | 0 of 24 | 0 |

## Tests

| S1 (G2): FEVER below | Wins / pairs | p | p (Holm) | Supported |
|---|---|---|---|---|
| FTMaster | 6 / 6 | 0.0156 | 0.0469 | yes |
| FTODefender | 0 / 6 | 1.0000 | 1.0000 | no |
| DMS-BTT | 6 / 6 | 0.0156 | 0.0469 | yes |

- S2 (EVX): reported above; FEVER blocked 32 EVX attackers over its 6 EVX runs. An EVX attacker holds at most 628 entries, below the volume limit, so these blocks are the eviction-share rule's: with 4 or more attackers the core table passes the pressure level and the detector's evictions fall on the attackers. Occupancy does not grow steadily with n (table above).
- S3: FEVER blocked 0 benign hosts over its 12 runs: pass.
