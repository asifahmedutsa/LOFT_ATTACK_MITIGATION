# EnsGuard v4: plan and decision rules (fixed 2026-11-06, before any v4 model was trained)

## Why

The v3 testbed campaign and the testbed E11 benchmark (results/e11_testbed,
results/testbed_prereg_v3/posthoc_diagnosis.md) show:

- EnsGuard's detector misses A4 and E9P on T1. This happens in the simulator and on the testbed
  alike: it is domain shift, not jitter.
- The block rule blocked a benign host in 4 of 20 runs.
- Scoring is the slowest of all the defenses.

## The change (decided by the user, 2026-11-06)

**Detection.** The T1 controller joins the federation as a fourth client.
- It trains RF (50 trees, depth 12) and CatBoost locally. The training data is the T1 trace's
  benign traffic plus A2, the only attack it sees. Training seeds are 1000-1004
  (results/revision5/trace_runs.pkl).
- The models are shared exactly as D1-D3 share theirs: EnsGuard v4 is the mean of 8 models
  (4 RF + 4 CatBoost).
- T1 never sees A4 or E9P. A4 stays seen by D1 only; E9P and A6 stay seen by no controller.
- Every controller recalibrates tau on its own validation benign at the 0.1 % budget. T1 uses
  seeds 2000-2002.

**Block rule.** A host is blocked when all three hold:
- its evictions in 10 s are at least 50;
- they are at least 3 x max(median host, m0);
- the flagged fraction of its own entries is at least f.

The grid is m0 in {10, 20, 40} and f in {0.2, 0.3, 0.5}. It is selected on simulator
development seeds 2000-2002 in phase 3.

**Scoring.** Only entries whose counters changed since the last poll are re-scored. Phase 4 checks
offline that the scores are identical.

## Phase 2 decision rule (detection), fixed before training

Data:
- **Simulator T1:** seeds 3000-3002, attacks A2, A4 and E9P, plus benign. These seeds were never
  used for T1.
- **Testbed:** the 12 entry-log recordings (seeds 4131-4133), wall clock.

v4 must meet every condition below. v3 is reported next to it for comparison.

| ID | Condition | Bar | Applies to |
|---|---|---|---|
| R1 | T1 recall on A4 at the T1 tau | >= 30 % | both simulator and testbed |
| R2 | Benign false-positive rate on T1 at that tau | <= 0.5 % | simulator benign runs and testbed benign recordings |
| R3 | T1 recall on A2 | no more than 2 points below v3 | simulator |
| R4 | E11 recall on attacks unseen by all controllers (D1-D3 test_off, 0.1 % operating point) | >= 46.5 % (v3: 48.5 %) | D1-D3 |

E9P recall is reported but has no bar.

**If any condition fails:** stop. Report v4 detection as a negative result, with no retuning on
these data and no testbed campaign.

## Later phases (unchanged from the plan given to the user)

- **Phase 3:** block-rule grid on simulator development seeds. Pick the setting with 0 benign
  host blocks and the lowest attack occupancy.
- **Phase 4:** controller code, then the user reinstalls.
- **Phase 5:** testbed development check, A4 + benign x seeds 4134-4136.
- **Phase 6:** preregistration_v4.json.
- **Phase 7:** test campaign. Defenses: none, ensguard (v3), ensguard-v4, dms-btt, flora@fed.
  Traffic: A2, A4, E9P, benign x fresh seeds 4140-4144 (100 runs).

## Phase 2 result (2026-11-06): detection fails the rule, so v4 detection stops here

From `results/v4/check.md` (`python -m loftbench.v4_t1 check`):

| Candidate | A4 recall, sim / testbed | E11 recall on unseen attacks | Pass |
|---|---|---|---|
| ens3 (v3) | 0.0 / 0.0 | 48.5 | no |
| ens4 (T1 joins) | 0.0 / 0.0 | 14.9 | no |
| cb4 (CatBoost only) | 0.0 / 0.0 | 21.0 | no |

R2 and R3 pass for every candidate.

**R1: A4 is still not detected.** T1's threshold drops from 0.64 to 0.48, but A4's median score
drops too (simulator 0.34 to 0.25, testbed 0.26 to 0.20). T1's local model learns that only
A2's pattern is an attack. Its vote then pulls the mimicry attack further toward benign.

**R4: generalization collapses.** Recall on attacks no controller saw falls from 48.5 % to
14.9 %. D1 goes from 45.9 % to 0.2 %, D2 from 61.7 % to 7.8 %. Because the models are averaged,
one client that knows only one easy attack dilutes what the others learned.

As fixed in advance, there is no retuning on these data and no testbed campaign for this
detector. The block-rule floor and the cheaper scoring (phases 3-4) do not depend on the
detector. Whether to continue with them alone (a "v4-lite" on the v3 detector) is the user's
decision.
