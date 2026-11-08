# Deployment check: FEVER with detectors trained on testbed rows by federated learning

T1B at 600 pps, seeds 4181-4182, testbed. fever: v6 as deployed; fever-fl-bag: Flower XGBoost
bagging; fever-fl-ll: lossless federated XGBoost. Means of the runs.

| Traffic | Method | Runs | Harm % | Attack occupancy % | Benign hosts blocked | Attack hosts blocked |
|---|---|---|---|---|---|---|
| A2 | fever | 2 | 0.005 | 24.75 | 0.0 | 2.0 |
| A2 | fever-fl-bag | 2 | 0.010 | 22.54 | 0.0 | 2.0 |
| A2 | fever-fl-ll | 2 | 0.005 | 24.83 | 0.0 | 2.0 |
| A4 | fever | 2 | 0.020 | 24.94 | 0.0 | 2.0 |
| A4 | fever-fl-bag | 2 | 0.045 | 26.62 | 0.0 | 2.0 |
| A4 | fever-fl-ll | 2 | 0.000 | 23.93 | 0.0 | 2.0 |
| E9P | fever | 2 | 0.030 | 29.06 | 0.0 | 2.0 |
| E9P | fever-fl-bag | 2 | 0.030 | 32.22 | 0.0 | 2.0 |
| E9P | fever-fl-ll | 2 | 0.005 | 26.44 | 0.0 | 2.0 |
| benign | fever | 2 | 0.000 | 0.00 | 0.0 | 0.0 |
| benign | fever-fl-bag | 2 | 0.000 | 0.00 | 0.0 | 0.0 |
| benign | fever-fl-ll | 2 | 0.000 | 0.00 | 0.0 | 0.0 |

## fever-fl-bag (Flower XGBoost bagging)

| Condition | Holds |
|---|---|
| A2: harm fever-fl-bag <= fever + 0.1 | yes |
| A2: attack occupancy fever-fl-bag <= fever + 2 | yes |
| A4: harm fever-fl-bag <= fever + 0.1 | yes |
| A4: attack occupancy fever-fl-bag <= fever + 2 | yes |
| E9P: harm fever-fl-bag <= fever + 0.1 | yes |
| E9P: attack occupancy fever-fl-bag <= fever + 2 | no |
| No benign host blocked by fever-fl-bag | yes |
| Benign only: harm fever-fl-bag <= 0.1 % | yes |

**Passes: no.**

## fever-fl-ll (lossless federated XGBoost)

| Condition | Holds |
|---|---|
| A2: harm fever-fl-ll <= fever + 0.1 | yes |
| A2: attack occupancy fever-fl-ll <= fever + 2 | yes |
| A4: harm fever-fl-ll <= fever + 0.1 | yes |
| A4: attack occupancy fever-fl-ll <= fever + 2 | yes |
| E9P: harm fever-fl-ll <= fever + 0.1 | yes |
| E9P: attack occupancy fever-fl-ll <= fever + 2 | yes |
| No benign host blocked by fever-fl-ll | yes |
| Benign only: harm fever-fl-ll <= 0.1 % | yes |

**Passes: yes.**

## Deployed detector (amendment 1)

Mean attack occupancy over A2, A4, E9P: fever-fl-bag 27.13 %, fever-fl-ll 25.07 %.

**fever-fl-ll (lossless federated XGBoost).**
