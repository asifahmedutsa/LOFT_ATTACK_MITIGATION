# Exploratory 600 s runs

Amendment 2 of the final campaign's preregistration: the six preregistered 600 s runs could not run (one T1B replay pass is 343 s at the campaign's rate) and are reported missing. These six runs were made afterwards with a replay that loops past one pass, on the same deployed models, tree3, benign scale 0.5 and seed 4160. One seed per cell, so no test is made and nothing here enters the preregistered results.

Measures as in the campaign, over the traffic window (probe start + 600 s). The first half is from the attack's start at 50 s to the middle of the traffic, the second half the remaining 300 s.

| Trace | Variant | Method | Harm % | Occupancy % | Probe success % | Benign deletes/min | Decision ms | Occ. 1st / 2nd half % | Probe 1st / 2nd half % | Hosts 5 / 6 blocked at s | Probe outage s | 300 s run: occ. / probe % / first block s / outage s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1B | Mimic | fever-fl-ll | 0.030 | 9.50 | 58.6 | 1.18 | 18 | 21.22 / 0.00 | 17.5 / 94.2 | 146 / 269 | 86–327 | 4.95 / 97.1 / 129 / 129–137 |
| T1B | Mimic | dms-btt | 2.070 | 43.55 | 13.1 | 1307.98 | 119 | 33.98 / 52.51 | 28.1 / 0.0 | – / – | 114– | 35.49 / 30.6 / – / 130– |
| T1B | Mimic | ftmaster | 4.250 | 45.79 | 14.1 | 11.02 | 76 | 34.64 / 57.20 | 30.4 / 0.0 | – / – | 129– | 36.33 / 31.0 / – / 131– |
| T1B | Aware | fever-fl-ll | 0.000 | 10.49 | 53.8 | 0.00 | 42 | 26.29 / 0.00 | 9.8 / 91.8 | 188 / 188 | 76–334 | 14.99 / 44.3 / 147 / 76–221 |
| T1B | Aware | dms-btt | 4.860 | 51.75 | 4.7 | 1321.43 | 147 | 41.74 / 60.99 | 10.0 / 0.0 | – / – | 76– | 43.01 / 9.8 / – / 76– |
| T1B | Aware | ftmaster | 15.370 | 55.23 | 4.6 | 3.15 | 58 | 46.30 / 64.76 | 9.8 / 0.0 | – / – | 76– | 47.28 / 10.0 / – / 76– |
| T1B | Mimic | fever-fl-ll (excluded run) | 0.000 | 2.88 | 86.6 | 0.00 | 13 | 6.30 / 0.00 | 71.0 / 100.0 | 143 / 143 | 94–169 | 4.95 / 97.1 / 129 / 129–137 |

Block times are controller time, as is the attack's start at 50 s. The last column is the same cell in the 300 s campaign with seed 4160, over its own traffic window (260 s after the attack's start, against 300 s for the first half here). The probe outage runs from the first failed attempt after the attack's start to the first of 20 successes in a row; an open end means no recovery.

The last row is the first A4 FEVER run, which overlapped a reinstall of the unchanged testbed code and was redone. It is not counted and is shown only for the spread between two runs of one seed.

Up to 160 s the 300 s and 600 s runs receive the same traffic: the benign flows are identical and the attack packets agree within 2 %, as rebuilt from the drivers' schedules, and the controller code and model files are those of the campaign. DMS-BTT and FTMaster behave as in their 300 s runs. FEVER does not: in its 600 s runs the attackers were blocked later and the probe outage lasted longer than in the 300 s runs, and on Mimic the outage also began earlier. The cause was not found; with one seed per cell this is a difference to check, not a result.

Controller log length (s): Mimic fever-fl-ll 646, Mimic dms-btt 620, Mimic ftmaster 776, Aware fever-fl-ll 612, Aware dms-btt 847, Aware ftmaster 887
