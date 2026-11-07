# FEVER ablation on the testbed: which part does the work?

*Fixed 2026-11-07, before any ablation run. Exploratory (not a preregistered confirmatory test):
results describe, they do not change FEVER.*

## Question

FEVER = federated CatBoost detector (evict + block rule A) + volume block (rule B) + PortGuard.
Does each of the two main parts add something on the real testbed?

| Variant | Defense name | Detector | Volume block | Source of runs |
|---|---|---|---|---|
| FEVER | ensguard-v5 | yes | yes | v5 campaign (reused) |
| FEVER without volume | ensguard-v4lite | yes | no | v5 campaign (reused) |
| FEVER without ML | ensguard-v5-noml | no | yes | **new runs** |
| rDefender (published, no ML) | rdefender | no | per-port occupancy (ATOS), random deletion | **new runs** |

FEVER without ML keeps the volume block (same X per switch) and PortGuard; with no detector,
nothing is evicted by score, block rule A never fires, and PortGuard trims the lowest packet
rate first (its documented behaviour with no detector). The code is otherwise unchanged, so the
reused runs and the new runs differ only in the defense.

## Runs

T1B, tree3, benign scale 0.5, 300 s, attack at 50 s; A2, A4, E9P and benign x seeds 4140-4142
x {FEVER without ML, rDefender} = 24 new runs (about 2 h 10 min). rDefender was added on
2026-11-07, still before any ablation run, at the user's request: it is the closest published
defense to the volume block (per-port occupancy, no ML). Seeds 4143-4144 can be added later with
`ABL_SEEDS="4143 4144"`; the analysis then uses every seed that all three variants have.

## Analysis (testbed/analyze_ablation.py, written before the runs)

Per attack, mean over seeds of: benign harm, attack share s11, lost first packets, attackers
blocked, benign hosts blocked, first attacker block (s after the attack), decision time; plus
paired wins of FEVER against each ablation over the attack runs.

Reading, fixed in advance:
- **The detector adds value** if FEVER has lower harm than FEVER-without-ML in most A2 pairs or
  blocks the A2 attackers clearly earlier (expected from the offline replay: about 70 s against
  100-175 s).
- **The volume block adds value** if FEVER has lower harm or attack share than
  FEVER-without-volume in most A4/E9P pairs (already seen in the v5 campaign, H8).
- **The detector is redundant** if FEVER-without-ML matches FEVER (within 0.1 point of harm and
  2 points of attack share) under every attack. This would be reported as such.
- **Against rDefender:** FEVER and FEVER-without-ML are compared with it on harm and attack share
  per attack, with paired wins, as for the ablations.
- Any benign host blocked by FEVER-without-ML is reported.
