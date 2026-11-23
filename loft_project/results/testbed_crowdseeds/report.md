# One-host flash crowd on more seeds (F2H, tables of 2,000 entries)

docs/crowdseeds_prereg.md. 300 s runs, no attacker, three 12 s crowds from d1h3, seeds 4200-4209. Mean (s.d.) over seeds.

| Method | Runs | Harm % | Lost first packets % | New-connection success % | Runs with d1h3 blocked | Benign deletes/min | s11 largest poll | s11 s at >= 90 % | s13 largest poll | Controller messages dropped % |
|---|---|---|---|---|---|---|---|---|---|---|
| No defense | 10 | 0.058 (0.127) | 0.42 (0.57) | 99.2 (1.3) | 0 | 0.00 (0.00) | 1926 (54) | 6 (3) | 1375 (50) | 0.6 (0.8) |
| FEVER | 10 | 20.761 (11.250) | 0.54 (0.83) | 99.5 (1.2) | 9 | 200.07 (75.80) | 1859 (60) | 1 (1) | 1278 (172) | 0.7 (1.2) |

## C1: how often FEVER blocked the crowd host

- This study: 9 of 10 runs (95 % interval 55 % to 100 %).
- Pooled with round 2 (2 of 3): 11 of 13 runs (95 % interval 55 % to 98 %).

## C2: harm against no defense (reported, not tested)

| Seed | No defense harm % | FEVER harm % | Difference (points) | d1h3 blocked |
|---|---|---|---|---|
| 4200 | 0.220 | 31.220 | +31.000 | yes |
| 4201 | 0.000 | 0.040 | +0.040 | no |
| 4202 | 0.000 | 3.550 | +3.550 | yes |
| 4203 | 0.000 | 28.760 | +28.760 | yes |
| 4204 | 0.000 | 20.860 | +20.860 | yes |
| 4205 | 0.000 | 29.340 | +29.340 | yes |
| 4206 | 0.000 | 30.410 | +30.410 | yes |
| 4207 | 0.000 | 20.730 | +20.730 | yes |
| 4208 | 0.000 | 27.380 | +27.380 | yes |
| 4209 | 0.360 | 15.320 | +14.960 | yes |

Mean paired difference +20.703 points over 10 seeds.

## C3: s11's largest poll in the first crowd

- FEVER runs with d1h3 blocked: 1769, 1771, 1785, 1803, 1820, 1830, 1864, 1866, 1882
- FEVER runs without a block: 1776
- Every unblocked run peaks lower than every blocked run: no, the seed-4188 reading is not supported.
- Round 2, for comparison: seed 4187 1634 (blocked); seed 4188 1601 (not blocked); seed 4189 1741 (blocked).

## Blocks of d1h3 by FEVER

- seed 4200: on s11 at 50 s, crowd 1 (40-52 s), 10 s after its start, volume (table 94 %, d1h3 held 1165, median host 233)
- seed 4202: on s11 at 285 s, crowd 2 (261-277 s), 24 s after its start, eviction (table 88 %, d1h3 held 1177, median host 161)
- seed 4203: on s11 at 90 s, crowd 1 (80-92 s), 10 s after its start, volume (table 93 %, d1h3 held 1160, median host 190)
- seed 4204: on s11 at 216 s, crowd 1 (207-219 s), 9 s after its start, volume (table 90 %, d1h3 held 1005, median host 202)
- seed 4205: on s11 at 68 s, crowd 1 (58-69 s), 10 s after its start, volume (table 92 %, d1h3 held 1225, median host 228)
- seed 4206: on s11 at 59 s, crowd 1 (50-62 s), 9 s after its start, volume (table 91 %, d1h3 held 844, median host 272)
- seed 4207: on s11 at 156 s, crowd 2 (145-162 s), 11 s after its start, eviction (table 87 %, d1h3 held 1068, median host 197)
- seed 4208: on s11 at 90 s, crowd 1 (80-106 s), 10 s after its start, eviction (table 89 %, d1h3 held 1207, median host 193)
- seed 4209: on s11 at 137 s, crowd 1 (108-125 s), 29 s after its start, eviction (table 98 %, d1h3 held 991, median host 395)
- Blocks of any other benign host: 0
