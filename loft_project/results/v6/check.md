# FEVER v6 development check (docs/v6_plan.md)

Simulator, T1B at 600 pps, seeds 2000-2002, volume limit of s11. Means of three runs.

| Traffic | Method | Harm % | Attack occupancy % | Benign hosts blocked | Attack blocks | First block (s after onset) |
|---|---|---|---|---|---|---|
| A2 | v5 | 0.000 | 4.51 | 0 | 6.0 | 51.0 |
| A2 | v6 | 0.000 | 3.93 | 0 | 2.0 | 51.0 |
| A4 | v5 | 0.197 | 14.07 | 0 | 4.0 | 93.7 |
| A4 | v6 | 0.006 | 13.07 | 0 | 2.0 | 93.7 |
| E9P | v5 | 0.333 | 5.59 | 0 | 6.0 | 31.7 |
| E9P | v6 | 0.004 | 4.50 | 0 | 2.0 | 31.7 |
| benign | v5 | 0.000 | 0.00 | 0 | 0.0 | nan |
| benign | v6 | 0.000 | 0.00 | 0 | 0.0 | nan |

| Condition | Holds |
|---|---|
| A2: harm v6 <= v5 | yes |
| A2: attack occupancy v6 <= v5 | yes |
| A4: harm v6 <= v5 + 0.1 | yes |
| A4: attack occupancy v6 <= v5 + 2 | yes |
| E9P: harm v6 <= v5 + 0.1 | yes |
| E9P: attack occupancy v6 <= v5 + 2 | yes |
| No benign host blocked by v6 | yes |
| Benign only: harm v6 <= 0.1 % | yes |

**Adopt v6: yes.**
