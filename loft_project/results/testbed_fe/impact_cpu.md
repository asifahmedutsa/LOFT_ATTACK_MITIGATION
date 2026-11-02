Mean over seeds 4100-4102, D1. harm = evicted/deleted then returned; pktin_lost = benign flows whose first packet the controller never answered; impact = either. CPU in % of one core after the first 60 s. dualguard+fairevictq = churn quarantine round 1 (never triggered on the testbed).

| variant | defense | harm | pktin_lost | impact | ctl_cpu | ovs_cpu |
|---|---|---|---|---|---|---|
| A2 | dualguard+evict | 0.07 | 4.89 | 4.96 | 88.45 | 143.36 |
| A2 | dualguard+fairevict | 0.35 | 5.2 | 5.55 | 82.39 | 106.73 |
| A2 | dualguard+fairevictq | 0.54 | 12.59 | 13.13 | 87.74 | 101.56 |
| A2 | dualguard+portguard | 0.27 | 5.06 | 5.33 | 86.41 | 135.82 |
| E9P | dualguard+evict | 6.14 | 18.34 | 24.48 | 106.65 | 109.22 |
| E9P | dualguard+fairevict | 1.66 | 30.54 | 32.19 | 114.17 | 99.58 |
| E9P | dualguard+fairevictq | 2.51 | 39.07 | 41.58 | 107.6 | 74.75 |
| E9P | dualguard+portguard | 5.22 | 18.94 | 24.16 | 106.79 | 100.08 |
| F4 | dualguard+evict | 0.19 | 10.64 | 10.82 | 59.69 | 89.19 |
| F4 | dualguard+fairevict | 0.25 | 11.34 | 11.59 | 68.27 | 82.57 |
| F4 | dualguard+fairevictq | 0.31 | 16.11 | 16.42 | 65.92 | 73.22 |
| F4 | dualguard+portguard | 5.1 | 12.13 | 13.75 | 58.55 | 91.73 |
