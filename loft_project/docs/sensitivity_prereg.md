# Sensitivity of FEVER to its fixed settings: preregistration

Drafted and fixed 18 November 2026, approved by the user and committed before any code below was
written and before any testbed run. FEVER as evaluated in the
campaign (fever-fl-ll) stays FEVER; this study changes none of the earlier results.

## 1. Why

FEVER's response uses three settings that were fixed before the final campaign and never varied on
the testbed: the occupancy at which eviction starts (rho = 0.7), the eviction ratio of the block rule
(a host is blocked at >= 3 times the median host's evictions, k = 3) and the volume limit (1.5 times
the busiest benign host seen in calibration). The study asks how much FEVER's results change when
each is set lower or higher, one at a time, and whether a preregistered setting avoids blocking the
one-host flash crowd of round 2 (docs/flash2_prereg.md), where FEVER blocked the crowd host in two of
three runs.

## 2. Settings

One setting changed at a time; everything else as in fever-fl-ll (detector, tau = 0.4953 on T1B,
n_min 50, frac_min 0.2, m0 10, 10 s window, permanent blocks at the ingress, changed-entry scoring).

| Method name | Changed setting | Value (default) |
|---|---|---|
| fever-s-r60 | rho | 0.6 (0.7) |
| fever-s-r80 | rho | 0.8 (0.7) |
| fever-s-k2 | eviction ratio k | 2 (3) |
| fever-s-k4 | eviction ratio k | 4 (3) |
| fever-s-v125 | volume multiplier | 1.25 (1.5): X = 666.3 / 653.8 / 663.8 on s11 / s12 / s13 |
| fever-s-v200 | volume multiplier | 2.0 (1.5): X = 1066 / 1046 / 1062 |

The volume limits are the T1A calibration maxima (533, 523, 531 entries; 799.5 / 784.5 / 796.5
divided by 1.5) times the multiplier. No value is chosen or changed after any run of this study.

## 3. Traffic and runs

- **Attacks (campaign settings):** capacity 3,500, T1B at benign scale 0.5, attack at 50 s, 300 s
  runs, G2 (A2), Mimic (A4) and Aware (E9P), seeds 4160-4162. Paired with the campaign's
  fever-fl-ll runs on the same seeds (results/testbed_prereg_final/runs.csv).
- **No attack (campaign settings):** T1B benign only, seeds 4160-4162. Paired with the campaign's
  fever-fl-ll benign runs.
- **One-host crowd (round 2 settings):** capacity 2,000, F2H, seeds 4187-4189. Paired with round 2's
  fever-fl-ll and no-defense runs (results/testbed_flash2/runs.csv).
- 6 settings x 5 traffic cases x 3 seeds = **90 runs**, about 8.5 h, plus one rerun pass. Names
  sens_T1B_<variant>_<method>_s<seed>; the crowd runs also pass --capacity 2000. Order: by seed, then
  traffic case, then setting.
- The default runs are reused, not rerun; they were made on the same testbed and install from 10 to
  17 November. This is stated as a limit of the pairing.
- Invalid runs: the campaign's rule as changed by amendment 1 (docs/final_campaign_prereg.md,
  section 11). An invalid run is rerun once with the same seed and listed in reruns.md; a run invalid
  twice is reported as missing.

## 4. Measures

As in the source studies (testbed/summarize_run.py; --capacity 2000 for the crowd runs): benign harm,
mean attack occupancy, new-connection success (probe), first attack block time, benign hosts blocked
(runs.csv hosts_blocked_benign, counted once per host), and, for blocks, which rule blocked
(eviction or volume, as testbed/analyze_flash2.py infers it).

## 5. Pass rules (no significance tests; three seeds)

- **R1 (attacks).** For each setting and each of G2, Mimic and Aware: the setting's mean harm is at
  most 0.5 point above default FEVER's, and its mean attack occupancy at most 5 points above default
  FEVER's. Each setting-attack pair passes or fails on its own (18 pairs).
- **R2 (no attack).** No setting blocks a benign host in any of its three benign-only runs.
- **R3 (one-host crowd).** Reported per setting: in how many of the three runs the crowd host was
  blocked, by which rule, and the mean harm against no defense. A setting "avoids the crowd block" if
  the crowd host is blocked in none of its three runs. R3 is not a claim about FEVER as evaluated;
  it says only whether a different preregistered setting would have avoided the block, and at what
  cost under R1.

Stated now:
- In round 2 the crowd host was blocked on s11 by the eviction rule in seed 4187 (holding 1,085
  entries, median host 182) and by the volume rule in seed 4189 (holding 1,072, median host 294). The
  s11 limit under fever-s-v200 is 1,066, so it may still block the host by volume; fever-s-k4 may
  avoid only the eviction-rule block.
- fever-s-v125 and fever-s-k2 are the settings most likely to fail R2; fever-s-r80 and fever-s-k4 the
  ones most likely to fail R1 on Mimic and Aware, which depend on the volume rule and on late blocks.
- Whatever the result, FEVER's default is not changed in the paper; the study is reported as a
  sensitivity check.

## 6. Files

- testbed/loft_ryu_app.py: the six method names, built as fever-fl-ll with the one setting changed;
  testbed/root/loft-testbed: accept them. Needs install.sh (run by the user) before any run.
- testbed/campaign_sens.sh (one smoke run, fever-s-k2 on G2 seed 4183, not a result; then the 90 runs
  and one rerun pass), testbed/analyze_sens.py: results/testbed_sens (runs.csv, report.md).
