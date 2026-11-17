# Refresh signal: flash crowds against low-rate attacks (offline, exploratory)

Schedules as sent on the testbed (T1B, benign scale 0.5). A flow is refreshed when it sends after >= 2 idle polls and within the 10 s idle timeout; counted in its first 20 s.

| Flows | Number | Refreshed (%) | Median time to first refresh (s) |
|---|---|---|---|
| Flash crowd F2 (seed 4187) | 4,426 | 0.0 | – |
| Benign replay T1B (seed 4187) | 18,422 | 6.5 | 6 |
| Benign replay, host 1 | 5,381 | 6.8 | 6 |
| Benign replay, host 2 | 6,048 | 5.4 | 6 |
| Benign replay, host 3 | 4,213 | 7.8 | 6 |
| Benign replay, host 4 | 2,780 | 6.1 | 9 |
| Attack G2 (seed 4160) | 3,400 | 100.0 | 7 |
| Attack Spoof (seed 4160) | 3,400 | 100.0 | 8 |
| Attack Pulse (seed 4160) | 10,200 | 100.0 | 7 |
| Attack Mimic (seed 4160) | 3,400 | 100.0 | 8 |
| Attack Aware (seed 4160) | 3,400 | 94.9 | 5 |
| Attack Slow (seed 4160) | 2,520 | 92.2 | 9 |
| Attack EVX (seed 4160) | 1,256 | 100.0 | 7 |

## Gate G0 (refresh share per host, 30 s window)

| Host | Seconds checked | Share: smallest | largest | Rule | Result |
|---|---|---|---|---|---|
| Crowd host d1h3, F2H seed 4187, crowds and 10 s after | 71 | 0.02 | 0.17 | largest <= 0.3 | pass |
| G2 attacker on port 4, seed 4160, 70-300 s | 231 | 0.66 | 1.00 | smallest >= 0.7 | fail |
| G2 attacker on port 5, seed 4160, 70-300 s | 231 | 0.50 | 1.00 | smallest >= 0.7 | fail |
| Spoof attacker on port 4, seed 4160, 70-300 s | 231 | 0.50 | 1.00 | smallest >= 0.7 | fail |
| Spoof attacker on port 5, seed 4160, 70-300 s | 231 | 0.67 | 1.00 | smallest >= 0.7 | fail |
| Pulse attacker on port 4, seed 4160, 70-300 s | 218 | 0.00 | 1.00 | smallest >= 0.7 | fail |
| Pulse attacker on port 5, seed 4160, 70-300 s | 221 | 0.00 | 1.00 | smallest >= 0.7 | fail |
| Mimic attacker on port 4, seed 4160, 70-300 s | 231 | 0.67 | 1.00 | smallest >= 0.7 | fail |
| Mimic attacker on port 5, seed 4160, 70-300 s | 231 | 0.67 | 1.00 | smallest >= 0.7 | fail |
| Aware attacker on port 4, seed 4160, 70-300 s | 231 | 0.78 | 1.00 | smallest >= 0.7 | pass |
| Aware attacker on port 5, seed 4160, 70-300 s | 231 | 0.75 | 1.00 | smallest >= 0.7 | pass |
| Slow attacker on port 4, seed 4160, 70-300 s | 231 | 0.67 | 0.96 | smallest >= 0.7 | fail |
| Slow attacker on port 5, seed 4160, 70-300 s | 231 | 0.67 | 0.97 | smallest >= 0.7 | fail |
| EVX attacker on port 4, seed 4160, 70-300 s | 231 | 0.67 | 1.00 | smallest >= 0.7 | fail |
| EVX attacker on port 5, seed 4160, 70-300 s | 231 | 0.67 | 1.00 | smallest >= 0.7 | fail |

G0: fail
