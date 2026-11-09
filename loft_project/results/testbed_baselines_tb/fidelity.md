# Retrained baselines against their earlier models (testbed, T1B test recordings)

docs/baselines_fidelity_plan.md, fixed before scoring; loftbench/tbfl_fidelity.py. Seeds 4176-4178,
all three switches. Each model at the decision its defense applies. Entry models: 5 % of the entries
per poll; poll models: every poll, labelled by the attack's schedule, without the defenses' occupancy
gates (so poll false alarms are an upper bound). Percentages.

| Baseline | Model | Unit | Training | False alarms | Recall, standard | G1 | G2 | G3 | Spoof | Pulse | Mimic | Slow | Aware |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FTMaster | state | poll | earlier (simulator T1A) | 14.04 | 65.73 | 80.92 | 26.96 | 86.23 | 90.78 | 36.31 | 83.01 | 81.35 | 93.82 |
| FTMaster | state | poll | retrained, C3 | 27.65 | 68.57 | 87.17 | 20.65 | 89.77 | 91.06 | 49.11 | 84.86 | 85.08 | 31.40 |
| FTMaster | state | poll | retrained, C1-C3 pooled | 6.35 | 87.58 | 91.89 | 81.04 | 92.91 | 94.25 | 74.55 | 92.37 | 89.24 | 81.02 |
| FTMaster | rule | entry | earlier (simulator T1A) | 0.11 | 96.60 | 96.70 | 97.83 | 97.42 | 97.13 | 93.54 | 0.01 | 0.02 | 0.00 |
| FTMaster | rule | entry | retrained, C3 | 0.33 | 99.85 | 99.86 | 99.91 | 99.85 | 99.80 | 99.87 | 0.07 | 0.09 | 0.05 |
| FTMaster | rule | entry | retrained, C1-C3 pooled | 3.09 | 99.88 | 99.93 | 99.91 | 99.86 | 99.85 | 99.86 | 88.18 | 83.17 | 24.90 |
| FTOP | state | poll | earlier (simulator T1A) | 0.00 | 33.49 | 31.80 | 36.75 | 36.69 | 32.29 | 28.94 | 28.38 | 17.44 | 31.15 |
| FTOP | state | poll | retrained, C3 | 13.94 | 73.41 | 77.36 | 81.15 | 77.37 | 79.66 | 44.35 | 71.40 | 61.00 | 23.31 |
| FTOP | state | poll | retrained, C1-C3 pooled | 45.70 | 78.14 | 84.59 | 85.20 | 82.46 | 84.69 | 45.68 | 83.01 | 77.52 | 86.88 |
| FTOP | rule | entry | earlier (simulator T1A) | 0.11 | 96.92 | 97.20 | 98.18 | 97.74 | 97.49 | 93.63 | 0.01 | 0.02 | 0.00 |
| FTOP | rule | entry | retrained, C3 | 0.32 | 99.87 | 99.92 | 99.91 | 99.85 | 99.83 | 99.86 | 0.06 | 0.09 | 0.04 |
| FTOP | rule | entry | retrained, C1-C3 pooled | 3.65 | 99.88 | 99.92 | 99.91 | 99.85 | 99.84 | 99.86 | 88.80 | 84.96 | 19.40 |
| FloRa | rule | entry | earlier (simulator T1A) | 0.11 | 96.75 | 97.17 | 98.07 | 97.47 | 97.58 | 93.02 | 0.01 | 0.02 | 0.00 |
| FloRa | rule | entry | retrained, C3 | 0.32 | 99.89 | 99.93 | 99.91 | 99.87 | 99.86 | 99.86 | 0.06 | 0.09 | 0.04 |
| FloRa | rule | entry | retrained, C1-C3 pooled | 2.58 | 99.88 | 99.93 | 99.91 | 99.86 | 99.85 | 99.86 | 87.09 | 77.79 | 7.32 |
| DMS-BTT | state | poll | earlier (simulator T1A) | 0.04 | 84.22 | 81.69 | 85.59 | 87.20 | 85.92 | 79.69 | 69.66 | 66.57 | 69.94 |
| DMS-BTT | state | poll | retrained, C3 | 0.11 | 80.48 | 80.65 | 83.79 | 78.51 | 79.44 | 79.84 | 76.89 | 72.19 | 77.26 |
| DMS-BTT | state | poll | retrained, C1-C3 pooled | 15.16 | 84.27 | 84.38 | 86.49 | 82.69 | 83.85 | 83.78 | 81.49 | 80.18 | 65.67 |
| DMS-BTT | flow | entry | earlier (simulator T1A) | 0.10 | 96.96 | 97.37 | 98.22 | 97.77 | 97.64 | 93.39 | 0.01 | 0.02 | 0.00 |
| DMS-BTT | flow | entry | retrained, C3 | 0.32 | 99.88 | 99.93 | 99.91 | 99.87 | 99.85 | 99.86 | 0.05 | 0.08 | 0.04 |
| DMS-BTT | flow | entry | retrained, C1-C3 pooled | 1.90 | 99.88 | 99.93 | 99.91 | 99.87 | 99.85 | 99.86 | 84.07 | 72.27 | 7.80 |
| FTODefender | rule | entry | retrained, C3 | 0.32 | 99.88 | 99.93 | 99.91 | 99.87 | 99.86 | 99.86 | 0.07 | 0.10 | 0.05 |
| FTODefender | rule | entry | retrained, C1-C3 pooled | 3.34 | 99.88 | 99.93 | 99.91 | 99.87 | 99.85 | 99.85 | 88.28 | 83.91 | 19.76 |
| FTODefender | detector | poll | retrained, C3 | 90.36 | 94.17 | 94.08 | 91.33 | 96.00 | 100.00 | 87.87 | 94.73 | 95.98 | 98.79 |
| FTODefender | detector | poll | retrained, C1-C3 pooled | 86.86 | 91.77 | 92.05 | 90.38 | 93.89 | 96.42 | 84.30 | 92.93 | 84.93 | 98.09 |

## Replacement rule (main arm)

| Baseline | Model | Recall >= earlier - 5 | False alarms <= 1 % | Decision |
|---|---|---|---|---|
| FTMaster | state | yes | no | earlier (simulator) |
| FTMaster | rule | yes | yes |  |
| FTOP | state | yes | no | earlier (simulator) |
| FTOP | rule | yes | yes |  |
| FloRa | rule | yes | yes | retrained (C3) |
| DMS-BTT | state | yes | yes | retrained (C3) |
| DMS-BTT | flow | yes | yes |  |
| FTODefender | rule | no earlier model | yes | retrained (C3) |
| FTODefender | detector | no earlier model | no |  |

## Data-matched arm (pooled)

Not replaced (docs/baselines_fidelity_plan.md). Models above 1 % false alarms: FTMaster state (6.35 %), FTMaster rule (3.09 %), FTOP state (45.70 %), FTOP rule (3.65 %), FloRa rule (2.58 %), DMS-BTT state (15.16 %), DMS-BTT flow (1.90 %), FTODefender rule (3.34 %), FTODefender detector (86.86 %).

## Rows

| Traffic | Entry rows (attack) | Polls (active) |
|---|---|---|
| benign | 69377 (49) | 2770 (0) |
| G1 | 172794 (125694) | 2375 (1824) |
| G2 | 178247 (134663) | 2328 (1777) |
| G3 | 177430 (134618) | 2296 (1750) |
| Spoof | 187933 (140947) | 2922 (1790) |
| Pulse | 174396 (119499) | 2623 (1344) |
| Mimic | 173455 (128136) | 2367 (1783) |
| Slow | 146111 (82731) | 2635 (2064) |
| Aware | 175746 (146284) | 2115 (1570) |
