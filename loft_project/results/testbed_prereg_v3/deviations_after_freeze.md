# Deviations after the freeze of preregistration v3

The preregistration (preregistration.json, sha256 in preregistration.sha256) is unchanged; this
file logs what happened after it was frozen.

## D1. Seed 4120's first 18 runs discarded: testbed load from another application (2026-11-04)

- The campaign started at 18:46. A Zoom client had been open since 18:10, before the campaign
  started, and its webview used up to about 117 % CPU. With it, the 4-core laptop ran at load
  average 9 with about 2 % idle CPU (Open vSwitch and the Ryu controller each on a full core).
- Symptom, the same for every defense, none included: after the attack start, benign lost first
  packets were 12-29 % and probe success about 30 %. The matching smoke run of the day before
  (A2, ensguard, scale 0.5, idle laptop) lost 2.08 % with 64 % probe success.
- Why discarded: G0 (benign-only, idle laptop) holds only for the load it was calibrated at;
  these runs measure an overloaded host rather than the defenses. The decision rests on the
  load and on the no-defense runs, which no defense can affect.
- Action: the campaign was stopped at 20:23 during run 18 of 40 (A4, rdefender). All 18 run
  directories were renamed in place to `_invalid_load_zoom_v3_T1_*_s4120` and are excluded
  from every analysis. The campaign restarts from the first run of seed 4120, unchanged
  (same script, hash 12ebc74b...), with no other application open.
- From here on, the laptop runs nothing but the testbed during the campaign.

### Correction to D1 (2026-11-05): Zoom was not the cause

The 19 runs repeated after the restart (20:45, Zoom closed, load average about 1 at the start)
reproduce the discarded runs closely: lost first packets after the attack start 12-30 % for
every defense, none included (A2 none 21.6 % vs 18.1 % before; FTMaster 12.4 vs 12.2 %), probe
success 21-30 % (before 19-32 %). So the load from Zoom did not drive these numbers; the attack
itself does (G0 tested benign traffic only). The discarded runs stay discarded (the reruns
replace them one for one and are the ones analysed); the attack-time loss of first packets is
reported as preregistered under "also_reported".

## D2. Power loss during seed 4120 (2026-11-04, 22:30)

- Mains power failed during the evening; the laptop ran on battery (tracker reported low
  battery at 22:22) and shut down at about 22:30 during run 20 of 40 (A4, ensguard). The
  start of battery operation is not in the logs, so some of runs 1-19 may have run on battery.
- The partial run was renamed `_invalid_poweroff_v3_T1_A4_ensguard_s4120` and is excluded.
- The reboot (2026-11-05 00:10) brought a pending kernel update (7.0.0-38 to 7.0.0-42).
  Runs from run 20 of seed 4120 on use the new kernel; the testbed snapshot in /opt/loft-testbed
  and Open vSwitch are unchanged.

## D3. Laptop suspended during seed 4121 (2026-11-05, 03:53 to about 07:54)

- The lid was closed at 03:53 and the laptop suspended, one minute into run 20 of 40 of
  seed 4121 (A4, ensguard); it resumed at about 07:54 on battery. Runs 1-19 of 4121 had
  finished before the suspend, with the charger connected (the power watcher checked every
  30 s and fired only after the resume), and are kept.
- The interrupted run spans a 4-hour suspend; it was renamed
  `_invalid_suspend_v3_T1_A4_ensguard_s4121` and is excluded. The campaign was stopped so no run
  starts on battery, and resumes from this run once the charger is back.
