# Flash crowds on T1B, round 2 (F2, tables of 2,000 entries)

docs/flash2_prereg.md. 300 s runs, no attacker, three 12 s crowds per run, seeds 4187-4189. Mean (s.d.) over seeds; blocks are totals over the three runs.

Crowd rate (section 3): selection F2: s11 largest poll 1885 entries (rule: >= 1800), controller messages dropped 0.0 % (rule: <= 10). Used: F2.

## Spread

| Method | Harm % | Lost first packets % | New-connection success % | Benign hosts blocked | Benign sources blocked | Benign deletes/min | Table-Full | s11 largest poll | s11 s at >= 90 % | s13 largest poll | Controller messages dropped % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| No defense | 0.000 (0.000) | 0.20 (0.26) | 88.8 (6.7) | 0 | 0 | 0.00 (0.00) | 0 (0) | 1801 (147) | 4 (4) | 840 (90) | 0.4 (0.6) |
| FTMaster | 0.013 (0.015) | 0.15 (0.16) | 89.8 (1.4) | 0 | 0 | 2.71 (0.70) | 0 (0) | 1801 (26) | 1 (1) | 823 (30) | 0.2 (0.3) |
| FTOP | 0.713 (0.473) | 0.12 (0.14) | 88.6 (8.5) | 0 | 0 | 137.47 (55.39) | 0 (0) | 1722 (13) | 0 (0) | 842 (1) | 0.1 (0.1) |
| FTODefender | 0.217 (0.021) | 0.45 (0.38) | 81.7 (7.3) | 0 | 0 | 56.07 (16.09) | 0 (0) | 1768 (49) | 0 (1) | 834 (33) | 0.8 (0.9) |
| FloRa | 0.140 (0.010) | 0.73 (0.67) | 83.9 (1.6) | 0 | 0 | 15.51 (3.68) | 0 (0) | 1787 (77) | 1 (1) | 816 (13) | 0.4 (0.3) |
| DMS-BTT | 0.593 (0.652) | 0.19 (0.24) | 87.5 (4.6) | 0 | 0 | 165.40 (185.04) | 0 (0) | 1790 (73) | 1 (2) | 802 (29) | 0.0 (0.0) |
| rDefender | 0.000 (0.000) | 0.67 (1.01) | 87.2 (9.3) | 0 | 0 | 0.00 (0.00) | 0 (0) | 1854 (54) | 4 (5) | 850 (24) | 0.7 (1.2) |
| FEVER | 0.020 (0.017) | 0.22 (0.09) | 79.9 (19.8) | 0 | 0 | 1.42 (0.60) | 0 (0) | 1789 (90) | 2 (2) | 807 (9) | 0.2 (0.2) |

Pass rule for FEVER, spread (section 6):

- F1, no benign host blocked in any of FEVER's runs (3 of 3 runs counted): pass (0 blocks)
- F2, FEVER's mean harm at most 1.0 point above no defense's: pass (0.020 % against 0.000 %)

## One host

| Method | Harm % | Lost first packets % | New-connection success % | Benign hosts blocked | Benign sources blocked | Benign deletes/min | Table-Full | s11 largest poll | s11 s at >= 90 % | s13 largest poll | Controller messages dropped % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| No defense | 0.000 (0.000) | 0.37 (0.54) | 95.5 (5.0) | 0 | 0 | 0.00 (0.00) | 0 (0) | 1790 (134) | 2 (4) | 1279 (143) | 0.5 (0.7) |
| FTMaster | 0.043 (0.038) | 0.18 (0.26) | 97.4 (2.4) | 0 | 0 | 3.87 (1.08) | 0 (0) | 1797 (134) | 2 (3) | 1263 (79) | 0.2 (0.4) |
| FTOP | 0.967 (0.257) | 0.03 (0.05) | 97.9 (1.9) | 0 | 0 | 166.91 (26.17) | 0 (0) | 1725 (7) | 0 (0) | 1346 (63) | 0.0 (0.0) |
| FTODefender | 0.213 (0.006) | 0.17 (0.13) | 97.2 (2.4) | 0 | 0 | 48.84 (6.62) | 0 (0) | 1787 (9) | 0 (0) | 1227 (64) | 0.1 (0.2) |
| FloRa | 0.133 (0.023) | 0.00 (0.01) | 97.3 (2.4) | 0 | 0 | 19.59 (3.56) | 0 (0) | 1800 (34) | 1 (1) | 1267 (86) | 0.0 (0.0) |
| DMS-BTT | 0.847 (0.380) | 0.01 (0.01) | 97.4 (2.3) | 0 | 0 | 251.14 (122.42) | 0 (0) | 1836 (9) | 2 (1) | 1310 (95) | 0.0 (0.0) |
| rDefender | 0.000 (0.000) | 0.08 (0.13) | 95.5 (5.2) | 0 | 0 | 0.00 (0.00) | 0 (0) | 1903 (98) | 4 (4) | 1344 (135) | 0.0 (0.0) |
| FEVER | 4.890 (5.870) | 0.18 (0.24) | 99.2 (1.4) | 4 | 0 | 140.75 (121.43) | 0 (0) | 1782 (71) | 1 (1) | 1242 (69) | 0.0 (0.0) |

Pass rule for FEVER, one host (section 6):

- F1, no benign host blocked in any of FEVER's runs (3 of 3 runs counted): fail (4 blocks)
- F2, FEVER's mean harm at most 1.0 point above no defense's: fail (4.890 % against 0.000 %)
  - seed 4187: host_block of 00:00:00:00:01:03 on s11 at 284 s, crowd 3 (273-285 s), 11 s after its start, eviction (table 87 %, d1h3 held 1085, median host 182)
  - seed 4187: ingress_drop of 00:00:00:00:01:03 on s13 at 285 s, crowd 3 (273-285 s), 12 s after its start
  - seed 4189: host_block of 00:00:00:00:01:03 on s11 at 249 s, crowd 2 (238-250 s), 11 s after its start, volume (table 91 %, d1h3 held 1072, median host 294)
  - seed 4189: ingress_drop of 00:00:00:00:01:03 on s13 at 249 s, crowd 2 (238-250 s), 11 s after its start

Round 1 (3,500 entries, F8, 24 runs): controller messages dropped 17.6 % to 28.6 % (mean 23.0 %).

