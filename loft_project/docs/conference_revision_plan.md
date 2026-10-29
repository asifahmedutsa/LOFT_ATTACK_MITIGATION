# Conference revision plan (v3): from "two components" to a defensible contribution

Written 29 October 2026, after the minimal testbed matrix (`results_v2.md` §18). It replaces
the open items of `submission_revision_plan.md` (steps 5–6) and schedules the open rows of
`experiments_from_related_work.md` (E3–E19).

## 0. Where the evidence stands

| Claim | Evidence | Status |
|---|---|---|
| Adaptive fast-refresh attackers defeat per-flow ML defenses | Sim: DMS-BTT 62 %, v2.1 73 %, local MLP 75–85 % harmed (§14–15, §17) | **Strong** (sim); testbed limited by Ryu capacity (§18.3) |
| Weighted fair share (PortGuard) stops them when attackers have their own ports | Sim: 0.2 % (gaps ≤ 1 s), ≤ 3.3 % at every gap (§15) | **Strong** (sim); testbed X1 5.8 % with 25 % Packet-In loss |
| FL-DualGuard beats DMS-BTT | Synthetic: yes (§11). Real traces: no, 0.5 points worse, n.s. (§17 H1) | **Weak** |
| Federation beats local training | §12: 1.53 vs 5.75 %; §17 H2: 2.6 points better | **Supported** |
| DualGuard adds to PortGuard | §15 H4 n.s. (dedicated ports); PortGuard hurts with attackers on every port (H6) | **Weak**: the two halves conflict |
| Testbed reproduces the simulator | §18: cell by cell after the install-clock fix; one cell (T1 A4, v2.1 alone) off | **Strong** |
| Novelty against rDefender (per-port occupancy anomaly + random deletion) | Not compared | **Risk** |

A strong reviewer would currently reject the paper for: (1) the conflicting composition, (2) no
comparison with rDefender or the other per-port and two-stage defenses, (3) no fast-refresh
result outside the simulator, and (4) a two-switch topology.

## 1. The paper after this revision

**Title direction.** *Fair-share admission with federated detection: defending SDN flow tables
against adaptive low-rate overflow.*

**Contributions, in the order the paper argues them.**

1. **Attack and measurement.** Adaptive low-rate overflow (refresh-gap and mimicry attackers)
   defeats every per-flow ML defense we reimplemented, on simulation and on Mininet/OVS.
   Pre-registered, one-shot tests with cluster CIs; no related paper reports any.
2. **A guarantee.** Weighted max-min fair admission guarantees every honest port
   min(demand, w_i · λ) entries whatever the attacker does; λ is computable from the poll.
   This is a theorem, not a tuned threshold, and it is what separates PortGuard from
   rDefender's anomaly-and-random-deletion heuristic.
3. **A composition that knows when to use which.** An automatic switch: fair share when the
   excess demand concentrates on few ports, the federated detector alone when it does not.
   This makes "Dual" one design, and removes the 8.9 % regression with attackers on every port.
4. **Federation where ports cannot separate attackers.** Cross-controller model sharing under
   heterogeneous exposure beats local training (already shown) and survives one poisoned
   controller (new).
5. **Data-plane enforcement.** Per-port OpenFlow meters on table misses cap the Packet-In load,
   so the fast-refresh result holds on the testbed.

**Target venues.** IFIP Networking, IEEE CNSM, IEEE NOMS or DSN with items P0–P1 done; IEEE
INFOCOM only if P0–P2 are done *and* the fast-refresh result holds on the testbed with meters.
Check each venue's call for papers for the deadline and page limit before fixing the order of
P1 and P2. Journal fallback: IEEE TNSM or TDSC (where FTMaster, FloRa and rDefender appeared).

**What "outperform" can mean.** Numbers from other papers are not comparable across setups
(their own cross-citations disagree; `Other Paper/experiments_summary.md` §13). We claim
superiority only against baselines **reimplemented on the same testbed and traffic**, and we
report in DMS-BTT's Table 6 format so a reader can line the numbers up with theirs.

---

## 2. Work packages

Status: ❌ not started. Effort assumes this 4-core laptop; "testbed hours" are unattended
Mininet time (one run at a time, about 10.5 min per 600 s run).

### P0 — required for any good conference

#### P0-A. Same-testbed baselines (E6) ❌ — about 3 days + 1 night of runs

| Baseline | Why a reviewer expects it | Mechanism to implement |
|---|---|---|
| **rDefender** (TIFS 2024) | Closest to PortGuard | Per-port abnormal table-occupancy squeezing (ATOS) detection; random deletion within attacked ports; its deletion-count rule against Packet-In loss |
| **FTMaster** (TNSM 2023) | Standard two-stage ML baseline | XGBoost table-state detector + XGBoost per-rule classifier (DT, NP, NB, MPS, MPIT, MTS); evict, then block source |
| **SIFT**, **TableGuard** | Compared in FTOP, FTODefender, DMS-BTT | As described in those papers' baseline sections |
| **EVICT**, **REFUSE** | Every comparison table | Already in the simulator (`OVSEvict`, `none`); add EVICT to the testbed |
| DMS-BTT tuned + blocklist | Already in sim and testbed | — |

Steps: implement in `loftbench/defenses.py` → check each against its paper's qualitative
result in the simulator (e.g. rDefender's malicious share falls under LA/HA) → port to Ryu
through the same `build_defense` path → 2-run smoke test each. Document every deviation from
the original paper, as was done for DMS-BTT (§13).

**Gate.** Every baseline reproduces its paper's direction in our simulator before it goes on
the testbed.

#### P0-B. Automatic switch between fair share and detector (contribution 3) ❌ — 2 days

- **Concentration statistic** per poll: the share of the excess demand (entries above each
  port's calm-period weight) held by the top-k ports. Enforce PortGuard while it is above κ;
  otherwise run the detector alone.
- Pre-register κ (and k) selection on validation seeds 2000–2002, as in step 4b; one-shot
  test on fresh seeds in the three scenarios (dedicated, shared, distributed).
- **Hypotheses.** Non-inferior (≤ 0.5 points) to the best fixed choice in each scenario;
  strictly better than v2.1 + PortGuard in the distributed scenario (8.9 % today); still
  ≤ 1 % on dedicated fast refresh.

**Gate.** H-auto supported in all three scenarios. If it fails in one, the paper states the
deployment rule (§15.4) as the design and the switch as future work.

#### P0-C. Fair-share guarantee (contribution 2) ❌ — 2 days

- **Theorem.** With weights w and target qC, an honest port with demand d_i receives at least
  min(d_i, w_i·λ) entries at every poll, for any attacker demand on other ports; λ solves
  Σ_j min(d_j, w_j·λ) = qC (`weighted_level`).
- **Corollary.** Attacker-independent bound on honest refusals between polls (installs since
  the last poll are counted, `PortGuard.used`).
- **New adaptive attacker: weight inflation.** Weights come from calm periods, so an attacker
  that holds entries *before* pressure earns weight. Test a slow pre-build attacker (fills its
  port during calm, then refreshes fast) and bound its gain by the τ_s = 60 s time constant.
  A reviewer will raise this attack if we do not.
- Check the bound empirically: the minimum honest-port share in every test episode is above
  the theoretical value.

**Gate.** The proof is written and checked, and the weight-inflation attacker's gain is
measured and bounded.

#### P0-D. DMS-BTT-format testbed comparison (E3, E7, E8, E13) ❌ — 1 day coding + 26 testbed hours

- **Controller logging (one reinstall):**
  - per-label occupancy from `OFPFlowRemoved` + install/delete events + truth, giving avg/max Pa;
  - memory (RSS) beside CPU;
  - per-module decision time.
- **Protocol (DMS-BTT's):** trace T1 (bigFlows) at the same per-host rate; 600 s, attack from
  50 s; table 3,500, idle timeout 10 s.
- **Attacks (5):** A1–A3 (DMS-BTT's own three groups), A4 (mimicry), X1 (fast refresh).
- **Defenses (10):** REFUSE, EVICT, SIFT, TableGuard, FTMaster, rDefender, DMS-BTT,
  v2.1, PortGuard, FL-DualGuard (auto).
- **Runs:** 5 × 10 × 3 seeds = 150 runs, about 26 h.
- **Reported, exactly as DMS-BTT Table 6:** avg Pa, max Pa, avg table usage, earliest overflow,
  total overflow time, Packet-In, TABLE_FULL. Added beside it: benign harmed (our metric),
  Packet-In loss rate (rDefender's), ping RTT, CPU, memory.
- **Time-series figure:** rule count, Pa and Packet-In over time with and without the defense.

**Gate.** All 150 runs complete; simulator-vs-testbed overlay within the §18 tolerance.

### P1 — needed to be competitive rather than borderline

#### P1-A. Data-plane enforcement for fast refresh (contribution 5) ❌ — 2 days + 4 testbed hours

- **Meters on table misses:** a priority-0 table-miss rule per access port with an OpenFlow
  meter (OVS ≥ 2.10 supports meters in the kernel datapath; check `ovs-ofctl -O OpenFlow13
  meter-features`). This caps each port's Packet-In rate at r_port.
- **Rate choice:** r_port is set from the calm-period weights, so an honest port's rate is
  untouched.
- **What it should fix:** the §18.3 finding was that the load comes from admitted-then-trimmed
  attacker flows. A per-port cap bounds that load regardless of the attacker's refresh gap.
- **Runs:** X0.25–X2 on D1 and T1 × {v2.1 + PortGuard, auto} × 3 seeds.

**Gate.** Benign Packet-In loss under X1 drops from 15–38 % to under 2 %, and harm approaches
the simulator's 0.2 %. If OVS meters do not work in Mininet's datapath, report the bound
analytically and state the hardware requirement (P2-C).

#### P1-B. Fat-tree topology with shared ports (E17) ❌ — 1 day + 8 testbed hours

- **Topology:** fat-tree k=2 per domain (FTODefender: 10 switches, 8 hosts). One monitored
  switch with the 3,500-entry limit; the other switches forward proactively, so a new flow
  causes one Packet-In, not one per hop.
- **Attacker placement:** attackers on edge switches shared with benign hosts. This is the
  realistic "shared" scenario, where PortGuard alone harmed 26 % in simulation and the auto
  switch has to earn its place.
- **Runs:** T1 × {A2, A4, X1} × {DMS-BTT, rDefender, v2.1, PortGuard, auto} × 3 seeds,
  about 45 runs, 8 h.

#### P1-C. Offline classification metrics and classifier comparison (E4, E5) ❌ — 1 day, simulator only

- **Metrics:** Acc / Precision / Recall / F1 / FPR / FNR / MCC on the offline test split, per
  variant and mixed, beside our budgeted TPR.
- **Classifiers:** RF, XGBoost, LightGBM, CatBoost, KNN, SVM, MLP on our 17 features, local and
  pooled, with per-rule inference time.
- **Argument for the MLP:** it is federable by weight averaging; trees are not. Show the cost
  in accuracy, if any.

#### P1-D. Federation robustness and scale (E18, E19) ❌ — 1.5 days, simulator only

- **Poisoning:** one controller sends a label-flipped or scaled update; compare FedAvg with
  coordinate-wise median and trimmed mean. Report harm, not only accuracy.
- **Scale:** 3 → 10 controllers (synthetic domains drawn from the existing profiles), with a
  convergence curve and communication bytes.

#### P1-E. Sweeps (E9, E10, E11, E14) ❌ — 1 day of compute + 6 testbed hours

- **Simulator:**
  - table size 1.5K / 2K / 3.5K / 4K, with τ recalibrated per size;
  - idle timeout 10 / 20 / 30 s;
  - sensitivity of ρ, q, τ_s and κ;
  - flash crowds (benign overflow, as in FTOP): does any defense evict benign flows?
- **Testbed:** table 2K and 4K × {DMS-BTT, auto} on T1 A2.

### P2 — for INFOCOM or a security venue

- **P2-A. Two-stage federated detector.**
  - Replace the 70 % occupancy trigger with a federated table-state classifier (FedAvg on FN,
    APIT, install rate, Packet-In rate, port skew), gating the per-flow MLP. `DualGuard`
    already accepts a `state_model`.
  - Pre-register one-stage vs two-stage. Expected benefit: fewer actions under flash crowds,
    and a detection delay to report. Risk: misses A4/A6.
- **P2-B. ALFO eviction-adaptive attacker** (E16) and rDefender's high-rate and replay attacks
  (E15).
- **P2-C. Hardware or P4.**
  - A meter-capable hardware switch or a Tofino port of the fair-share admission (per-port
    counters plus a quota check fit a P4 pipeline).
  - Without it, a top-tier security venue is out of reach.
- **P2-D. Artifact.** `make reproduce`, a pinned environment and a Zenodo DOI (artifact
  badges).

---

## 3. Order, effort and checkpoints

| Week | Work | Testbed (nights) | Checkpoint |
|---|---|---|---|
| 1 | P0-A baselines in the simulator; P0-C proof draft; P1-C offline metrics | — | Each baseline reproduces its paper's direction |
| 2 | P0-B auto switch (pre-register, select, one-shot test); P0-A port to Ryu; P0-D logging (reinstall) | smoke tests | H-auto result; all baselines run in Ryu |
| 3 | P0-D main testbed comparison | 150 runs, about 26 h | DMS-BTT-format table complete |
| 4 | P1-A meters; P1-B fat-tree; P1-D federation robustness | about 12 h | Fast refresh holds on the testbed, or the limit is documented |
| 5 | P1-E sweeps; figures; paper rewrite around §1's contributions | about 6 h | Full draft |

About 5 weeks to a full draft at P0–P1. P2 adds 2–4 weeks; P2-C depends on hardware access.

**Decision points.**
- **After week 2:** if the auto switch fails, the paper uses the explicit deployment rule;
  aim at CNSM / NOMS / TNSM rather than INFOCOM.
- **After week 3:** if rDefender matches PortGuard on harm, the contribution rests on the
  guarantee (P0-C), the adaptive-attacker study and the federated component for the
  distributed case. Say so in the paper; do not tune PortGuard against the test set.
- **After week 4:** if meters do not cap the load, report fast refresh from the simulator with
  an analytic Packet-In bound, and name meter-capable hardware as the deployment requirement.

## 4. Rules that stay in force

- **Testing discipline:** every new defense, knob and hypothesis is fixed on validation seeds
  and tested once on fresh seeds; negative results are reported (§11–§18 practice).
- **Fair baselines:** baselines are tuned on the same validation data as our method, and every
  deviation from the original paper is documented.
- **Testbed hygiene:** runs go one at a time through `sudo -n loft-testbed`, with a reinstall
  after any testbed code change, and never concurrently with simulator jobs.
- **What the paper claims:**
  - Superiority is claimed only on same-testbed comparisons.
  - Packet-In loss is reported as its own column for every defense.
