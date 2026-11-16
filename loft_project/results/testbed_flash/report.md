# Flash crowds on T1B (F8)

docs/flash_prereg.md. 300 s runs, no attacker, three 12 s crowds per run, seeds 4165-4167. Mean (s.d.) over seeds; blocks are totals over the three runs.

Burst size (section 3): selection F4: s11 largest poll 1867 entries (rule: >= 3150); selection F6: s11 largest poll 2434 entries (rule: >= 3150); selection F8: s11 largest poll 2625 entries (rule: >= 3150); F8 did not fill s11; the study runs at F8 (section 3). Used: F8.

| Method | Harm % | Lost first packets % | New-connection success % | Benign hosts blocked | Benign sources blocked | Benign deletes/min | Table-Full | s11 largest poll | s11 s at >= 90 % |
|---|---|---|---|---|---|---|---|---|---|
| No defense | 0.000 (0.000) | 20.40 (2.66) | 57.9 (4.0) | 0 | 0 | 0.00 (0.00) | 0 (0) | 2628 (122) | 0 (0) |
| FTMaster | 0.000 (0.000) | 21.89 (4.36) | 58.1 (5.6) | 0 | 0 | 0.00 (0.00) | 0 (0) | 2528 (94) | 0 (0) |
| FTOP | 0.000 (0.000) | 20.37 (4.09) | 54.3 (6.7) | 0 | 0 | 0.62 (1.07) | 0 (0) | 2532 (292) | 0 (0) |
| FTODefender | 0.167 (0.057) | 23.23 (3.64) | 20.6 (35.7) | 0 | 0 | 182.52 (54.13) | 0 (0) | 2306 (287) | 0 (0) |
| FloRa | 0.013 (0.006) | 21.88 (4.30) | 55.7 (6.5) | 0 | 0 | 8.89 (1.68) | 0 (0) | 2493 (201) | 0 (0) |
| DMS-BTT | 0.007 (0.006) | 22.03 (3.40) | 58.4 (3.5) | 0 | 0 | 5.46 (2.19) | 0 (0) | 2474 (106) | 0 (0) |
| rDefender | 0.000 (0.000) | 19.73 (5.30) | 52.5 (8.6) | 0 | 0 | 0.00 (0.00) | 0 (0) | 2664 (45) | 0 (0) |
| FEVER | 0.000 (0.000) | 21.34 (5.25) | 57.2 (5.6) | 0 | 0 | 1.26 (1.10) | 0 (0) | 2492 (30) | 0 (0) |

## Pass rule for FEVER (section 6)

- F1, no benign host blocked in any of FEVER's runs (3 of 3 runs counted): pass (0 blocks)
- F2, FEVER's mean harm at most 1.0 point above no defense's: pass (0.000 % against 0.000 %)
