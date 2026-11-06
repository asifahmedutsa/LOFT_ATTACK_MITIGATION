# EnsGuard v4-lite: plan and decision rules (fixed 2026-11-06, before any v4-lite run)

## Starting point

- The detector stays federated over D1-D3. The v4 detector change failed (docs/v4_plan.md).
- v4-lite targets the two testbed problems a defense change can fix:
  - **H4 failure:** a benign host was blocked in 4 of 20 v3 runs, because the block rule's median
    collapses when few entries are evicted.
  - **Slow scoring:** EnsGuard has the highest per-poll time and the most lost first packets
    under A4 and E9P on a saturated controller.
- v4-lite does not try to fix the A4/E9P detection miss on T1.

## Development data only

Nothing below touches the v3 test seeds 4120-4124 or the planned test seeds 4140-4144.

| Source | Contents |
|---|---|
| Simulator | D1-D3; A2, A4, E9P, A6 and benign; validation seeds 2000-2002 (closed loop, loftbench/evictblock.py) |
| Offline validation rows | results/v2/datasets.pkl, the val split of D1-D3 |
| Testbed recordings | the 12 entry logs (A2, A4, E9P and benign x seeds 4131-4133, defense none, s11-s13), already development data since v4 phase 2. They are replayed open loop: the defense's decisions are computed on the recorded table but not applied. |

## Step 2: detector. RF + CatBoost (ens) or CatBoost only (cb)

**Procedure.**
- Both candidates are trained 3 times, with model seeds 0, 1 and 2, on the D1-D3 training rows.
- Each controller sets tau at the 0.1 % budget on its own validation benign.
- Seed 0 of ens is the deployed v3 model.

**Measures (mean over the 3 model seeds; the spread across seeds is reported).**
- V: validation recall on attacks the scoring controller did not train on (seen elsewhere, plus
  A6), at tau.
- H: simulator benign harm (%), averaged over all cells. The evict-block setting is v3's:
  n_min 50, k 3, first block 60 s, inside PortGuard full.
- O: simulator attack occupancy (%), averaged over the attack cells.
- B: benign hosts blocked in the simulator, summed.
- Scoring time per 10,000 entries.

**Rule.** cb is chosen only if all of the following hold. Otherwise ens is kept.

| Measure | Condition for choosing cb |
|---|---|
| V | V(cb) >= V(ens) - 2 points |
| H | H(cb) <= H(ens) + 0.25 points |
| O | O(cb) <= O(ens) + 1 point |
| B | B(cb) = 0 |

## Step 3: block-rule floor

**The rule.** A host is blocked when all three conditions hold. They are computed over the last
10 s.

| Condition | Meaning |
|---|---|
| evictions >= n_min (50) | the host's own eviction count |
| evictions >= k (3) x max(median host's evictions, m0) | m0 is the new floor (v3: effectively 1) |
| flagged fraction >= f | the host's evicted entries / the entries it held, summed over the polls in the window (new; v3: 0) |

**Grid.** m0 in {10, 20, 40} x f in {0.2, 0.3, 0.5}, plus the v3 rule as a reference
(10 settings). It runs with the detector chosen in step 2, at its seed-0 model.

**Measures.**
- Simulator (closed loop): harm, attack occupancy, and benign and attack hosts blocked.
- Testbed replay (open loop, T1 tau of the chosen detector): benign hosts that would be blocked,
  and attack hosts that would be blocked, per recording and switch.

**Rule.**
1. **Eligible:** 0 benign hosts blocked in the simulator and in the replay, and in the simulator
   at least as many attack hosts blocked under A2 as the v3 rule blocks.
2. **Choice:** among the eligible settings, the lowest simulator attack occupancy. Settings within
   0.5 points of it tie, and the tie goes to the lowest harm.
3. **If none is eligible:** keep the v3 rule and report it.
4. **If the v3 rule blocks no benign host in the replay,** the replay cannot reproduce H4. This
   will be stated in the report.

## Step 4: score only entries whose counters changed

An entry with no new packets keeps its previous score.

- **Not exact:** age and gap features keep changing, so scores drift for idle entries.
- **Measured on the testbed replay:** the share of eviction decisions that differ from full
  scoring, and the time saved.
- **Adopted only if** decisions agree on at least 99.9 % of entries AND scoring time falls by at
  least 30 %. Otherwise full scoring stays.

## Then (unchanged)

1. The user reinstalls.
2. Testbed development check: A4 + benign x seeds 4134-4136.
3. preregistration_v4lite.json.
4. Test campaign on fresh seeds 4140-4144:
   - defenses: none, ensguard (v3), ensguard-v4lite, dms-btt, ftmaster;
   - traffic: A2, A4, E9P, benign;
   - 100 runs in all.

## Results so far (2026-11-06)

### Step 2: CatBoost only is chosen

It passes V, H, O and B (results/v4lite/detsel.md). Means and spreads are over 3 model seeds.

| Measure | ens | cb |
|---|---|---|
| Validation recall on attacks not trained on | 92.2 % | 92.5 % |
| Harm | 0.66 % | 0.67 % |
| Attack occupancy | 8.2 % | 6.2 % |
| Benign hosts blocked | 0 | 0 |
| Scoring time per 10,000 entries | 104 ms | 20 ms |

### Step 3: the fixed rule picks m0 10, f 0.2. It is not adopted, pending the user's decision.

The testbed replay reproduces H4: the v3 rule blocks benign hosts 4 times (3 under A4, 1 under
A2). Every floored setting removes those blocks, but in the closed-loop simulator the
flagged-fraction condition stops blocking the E9P attacker (2.0 to 0.1 per episode):

| Variant | Measure | v3 rule | m0 10, f 0.2 |
|---|---|---|---|
| E9P | harm | 1.8 % | 5.9 % |
| E9P | attack occupancy | 13.9 % | 44.9 % |
| A4 | attack occupancy | 4.4 % | 22.0 % |

m0 alone changed nothing: m0 10, 20 and 40 give identical results. The cause was already noted
in loftbench/evictblock.py (round 2): an attacker that keeps replacing evicted entries never
shows a high flagged fraction.

The rule above had no guard against getting worse than v3 on harm or occupancy. That is a gap in
the rule as written, and it is recorded here instead of being silently corrected.
