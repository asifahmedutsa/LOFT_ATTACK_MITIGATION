# Experiments needed for submission, from the related work

Source: the 12 papers summarised in `Other Paper/experiments_summary.md` (LOFT,
FTGuard, SFTO-Guard, FTMaster, GASF-IPP, FTODefender, FTOP, ALFO-Guard, FloRa,
rDefender, FTShield, DMS-BTT). Written 28 October 2026, during revision step 4.

**How to read this.** Every LFTO defense paper since 2023 follows nearly the same
evaluation template (Mininet + Ryu + OVS, IMC-10 or bigFlows replay, a 3,500-entry
table, 10 s idle timeout, a Scapy attack with period T, step S and maximum M). Reviewers
in this area expect that template. Items are ranked by how likely a reviewer is to
reject the paper without them.

Status: ✅ done, 🟡 partly done, ❌ missing.

---

## Tier 1 — expected by every reviewer (reject risk without them)

| # | Experiment | Who does it | Our status | What to do |
|---|---|---|---|---|
| E1 | **Emulation testbed**: Mininet + Ryu + OVS, the defense running in the real controller loop | All 11 defense papers | 🟡 Harness written (`testbed/`), never run (needs sudo) | Run the acceptance runs; reduced matrix of {none, DMS-BTT, v2.1, v2.1 + PortGuard} × {A2, A4, A6, fast-refresh} × D1–D3 × 3 seeds; simulator-vs-emulation overlay figure |
| E2 | **Real background traffic**: IMC-10 univ1/univ2 or bigFlows.pcap replayed with tcpreplay | 10 of 11 | ❌ Synthetic per-kind generator only | Add a trace-driven benign source (pcap → per-flow packet times) to the simulator and use tcpreplay on the testbed. Keep the synthetic domains for the heterogeneity study, and report the main comparison on traces as well |
| E3 | **Standard comparison table**: avg and max attack-flow share (Pa / Pm), avg table usage, earliest overflow time, total overflow time and count, Packet-In and Table-Full counts | DMS-BTT, FTOP, FTODefender, FTMaster, FTShield, FloRa | 🟡 All quantities are computed (`sim.py` summary) except avg table usage as a column | Add one table in exactly this format, so readers can line our numbers up with DMS-BTT Table 6 and FTOP |
| E4 | **Offline classification metrics**: Accuracy, Precision, Recall, F1, FPR, FNR (± MCC) for the table-state detector and the per-rule classifier | 9 of 11 | 🟡 We report TPR at a 1 % FPR budget, which is stricter but non-standard | Add the standard confusion-matrix metrics on the offline test split, per variant and mixed, alongside the budgeted TPR |
| E5 | **Classifier comparison**: RF, XGBoost, LightGBM, CatBoost, KNN, SVM, MLP on the same features | SFTO-Guard, FTMaster, FTOP, FloRa, DMS-BTT, FTShield | ❌ Only MLP, CatBoost (DMS-BTT) and the legacy SVM-RF | Train each on our 17 features (local and pooled), report offline metrics and per-rule inference time. Explain why the MLP was chosen (it is federable by weight averaging; trees are not) |
| E6 | **More baselines** | Each paper compares 3–7 | 🟡 none (= REFUSE), OVS evict (= EVICT), threshold-LRU, DMS-BTT (+ tuned + blocklist) | Add **SIFT**, **TableGuard**, **FTOP** or **SFTO-Guard**, and, essential for PortGuard, **rDefender** (per-port occupancy anomaly + random deletion) and **FTGuard** (per-user priority eviction). Both are per-port or per-user schemes that reviewers will compare PortGuard against |
| E7 | **Overhead and real-time cost**: per-module latency (detect, mitigate, total; mean, max), controller CPU and memory with and without the defense | 10 of 11 | 🟡 Only simulator decision time in Python | Measure in Ryu on the testbed: decision-loop time, CPU, memory, flow-mod rate; PortGuard's per-poll cost |
| E8 | **Time-series figures** of rule count and malicious share over time, with and without the defense | All | 🟡 Occupancy timelines exist (v2) | Regenerate for the final configuration, including PortGuard against the fast attacker (rule count stays at the 90 % target) |

## Tier 2 — expected at a good venue (weak-accept → accept)

| # | Experiment | Who does it | Our status | What to do |
|---|---|---|---|---|
| E9 | **Table-size sweep** 2K / 3K / 4K (and 1.5K) | FTMaster, FTShield, FloRa | ❌ 3,500 only | Rerun the main comparison at 1.5K, 2K, 3.5K, 4K; recalibrate τ per size on validation |
| E10 | **Idle-timeout sweep** 10 / 20 / 30 s | LOFT, FloRa (20 s), rDefender (30 s) | ❌ 10 s only | Rerun at 20 and 30 s with the attack period scaled accordingly; t_short stays 1 s |
| E11 | **Parameter sensitivity** of the defense's own knobs | FTMaster (threshold 70/80/90 %), FTOP (α), FTODefender (TH2), DMS-BTT (Pe) | 🟡 Validation selection tables exist (v2.1, revision 2, revision 4) | Turn them into sensitivity figures: harm and malicious share against ρ, t_short, the calibration budget and PortGuard's q |
| E12 | **Service-level harm**: new-flow RTT (ping), new-flow throughput (iperf), background throughput degradation | LOFT, ALFO-Guard | 🟡 Flow-level harm metric in simulation | On the testbed: ping and iperf from a benign host during the attack, for each defense |
| E13 | **Packet-In loss rate** at the controller | rDefender | ❌ No controller capacity model | Count Packet-Ins the controller drops at a measured service rate μ, or measure loss directly on the testbed. Important because PortGuard turns refused attack installs into Packet-Ins |
| E14 | **Flash-crowd (benign overflow) scenario** | FTOP | 🟡 D3 has flash crowds, not reported separately | Report benign-only overflow episodes: does any defense evict benign flows when the table fills with no attacker? |
| E15 | **High-rate attack** (2,000 pps) and **trace-replay mimicry** | rDefender (HA, AHA, ALA) | 🟡 Step 4 covers fast refresh up to 0.25 s gaps | Add a high-rate variant (one packet per new flow at 2,000 pps) and a replay-based mimic |
| E16 | **Eviction-policy-adaptive attack** (ALFO: adapts to FIFO / Random / LRU) | ALFO-Guard | ❌ | Run ALFO's three modes against OVS evict and against each defense |
| E17 | **Multi-switch topology** per domain (Napnet, fat-tree, tree) | FTMaster, FTODefender, FloRa, rDefender | ❌ One switch per domain | At least one multi-switch domain on the testbed. The multi-controller claim is otherwise thin |

## Tier 3 — specific to our contribution (no related paper does them, but our claims need them)

| # | Experiment | Our status | What to do |
|---|---|---|---|
| E18 | **Federation**: rounds vs accuracy, communication bytes, number of controllers (3 → 10), non-IID skew | 🟡 Skew sweep and comparators done (step 3); bytes measured | Add a scaling run over controller count and a convergence curve |
| E19 | **Poisoning robustness**: one compromised controller sends a manipulated model | ❌ | A label-flip or scaled-update client, with and without robust aggregation (median, trimmed mean) |
| E20 | **Generalisation to unseen parameters** (held-out variants) | ✅ Leave-one-variant-out (step 3) | Highlight it; the summary notes this is a gap in all related work |
| E21 | **Attacker-budget curve** (refresh gap vs harm, occupancy, attacker pps) | 🟡 Running now (step 4) | Central figure of the revised paper |
| E22 | **Hardware or P4** | ❌ | Only if targeting INFOCOM or a security venue (LOFT, rDefender and FTShield use hardware; FloRa uses Raspberry Pi). Not needed for CNSM, NOMS, NetSoft or TNSM |

---

## What we already do that the related work does not

- Paired online evaluation with cluster-bootstrap CIs and pre-registered, one-shot tests.
  None of the 12 papers reports confidence intervals or significance tests.
- A service-level harm metric (refused, or evicted while active) rather than only
  table-level proxies.
- Held-out attack variants, mimicry, spoofing, pulsing and an adaptive attacker.
- A fair, tuned DMS-BTT baseline with its deviations documented against the paper.

## Suggested order

1. **E2 + E1 together** (trace replay on the testbed). This is the largest credibility
   gap, and both need the same tooling. Needs sudo.
2. **E3, E4, E5** (cheap, simulation only; about half a day).
3. **E6** baselines, prioritising rDefender and FTGuard because PortGuard is per-port.
4. **E9, E10, E11, E14, E15** (simulation sweeps; about one day of compute).
5. **E7, E12, E13** on the testbed after E1.
6. **E16–E19** if time allows; E19 strengthens the federation claim most.
