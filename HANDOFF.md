# LOFT research handoff — start here

Prepared: 18 October 2026.

## 1. What you are taking over

This is a research prototype for detecting and mitigating low-rate flow-table overflow attacks (LOFT/LFTO) in software-defined networks (SDN). The proposed approach is named **FL-DualGuard**: packet/flow features, an SVM–Random Forest ensemble, and intended collaboration across multiple SDN controllers using federated learning.

The comparison paper is **DMS-BTT: Low-rate flow table overflow attack defense system based on two-level threshold in software-defined networks** (2025).

**Current status: offline prototype and evaluation scaffold. Real federated learning and an end-to-end online defense still need implementation.** The immediate goal is a trustworthy experiment, followed by a precise research contribution. Do not assume the existing figures establish a SOTA result.

## 2. Repository and transfer status

- GitHub remote: <https://github.com/asifahmedutsa/LOFT_ATTACK_MITIGATION>
- Clone URL: `https://github.com/asifahmedutsa/LOFT_ATTACK_MITIGATION.git`
- Branch at handoff inspection: `main`.
- Latest local commit: `de7ac96` — `Add ignore rules for local artifacts.`
- Other relevant commits: `59343f2` adds the audited evaluator/reporting guard and methodology docs; `e97188e` adds the DMS-BTT scaffold.
- The local tracking reference `origin/main` points to the same commit as local `main`. The live GitHub state and your access have not been checked during this handoff.

At preparation time, these existing files were **untracked**:

- `DMS_BTT_2025.pdf`.
- `loft_project/docs/novelty_feasibility_and_research_next_steps.md`.

This new handoff file and the README update also require a commit/push to reach someone cloning GitHub. A clone contains committed, pushed files; it does not include local untracked files. The owner should commit the documentation or send those files separately. Obtain the PDF separately if it is absent from the clone. The visual review under the original owner's home directory and previous `/tmp` outputs are not repository deliverables.

### For the current owner before transferring

From the repository root, review and publish the documentation with:

```bash
git status --short
git add HANDOFF.md README.md loft_project/docs/novelty_feasibility_and_research_next_steps.md
git diff --cached --stat
git commit -m "Document project status and research handoff"
git push origin main
```

These are instructions; this handoff task does not itself create a commit or push. Send the recipient the repository link, any required repository access, and the paper PDF separately. If handing over a folder instead, include `HANDOFF.md`, the novelty review, the PDF, and the `.git` directory to preserve history.

## 3. Read these first

Use repository-relative paths below so the guide works on your own computer.

1. `loft_project/docs/novelty_feasibility_and_research_next_steps.md` — the most current assessment of novelty, implementation gaps, and the research roadmap. Ask the owner for it if missing.
2. `loft_project/docs/evaluation_legitimacy_and_dms_btt_alignment.md` — initial accuracy audit and comparison plan.
3. `loft_project/docs/methodology_loft_vs_dms_btt.md` — architecture and earlier execution guidance. Its federated commands describe a prototype; use the newer review and this guide for readiness judgments.
4. `DMS_BTT_2025.pdf` — read Section 4 for the method and Section 5 for evaluation. Obtain separately if missing.

The initial audit and methodology documents predate the later feasibility review. When they differ on readiness, use the later review and inspect the code.

## 4. Understand the results before running anything

The audited evaluator was executed on 11 October 2026 against the checked-in synthetic dataset, excluding `spoofing_conf`. It produced **98.375% accuracy** on 800 held-out rows from 4,000 records. This was a centralized classification smoke test, not a federated or online mitigation experiment. The full review records the dataset hash and software versions.

All 4,000 flow groups were singletons, and the dataset has no independent run/domain identifiers. Therefore, its group split does not establish generalization across attack runs or controllers. Class-dependent feature generation also remains a problem.

DMS-BTT's **94% is its mixed attack detection rate**, not accuracy. The supplied paper reports **86.89% mixed three-state accuracy** and **92.42% mixed malicious-flow accuracy**. Compare the same task, metric, data, and split before claiming improvement.

Existing tables, figures, saved models, and `results/paper_results_section.md` are legacy artifacts. Trace their provenance before using them. `results/generate_final_results.py` contains hardcoded/demo reporting and is blocked by default; do not enable its demo override to produce research evidence.

## 5. Repository map

```text
HANDOFF.md                              This guide
loft_project/
  data/
    full_dataset.csv                    Checked-in synthetic data; use for smoke tests
    generate_realistic_dataset.py        Synthetic generator; known class shortcuts
    traffic_log_*.csv                    Legacy controller logs; provenance needs review
  models/local_model_trainer.py          Local SVM/RF training prototype
  federated/
    fl_client.py                        Incomplete client; returned updates ignored
    fl_server.py                        Flower aggregation prototype
  topology/
    multi_controller_topo.py             Existing three-controller Mininet prototype
    ryu_controller.py                   Packet logging/forwarding; defense incomplete
  attack/                               Existing traffic and attack scripts
  eval/
    run_audited_eval.py                  Executable centralized offline evaluator
    run_dms_btt_offline_baseline.py       CatBoost offline scaffold; prepared data required
    config/dms_btt_eval.yaml             Paper-inspired settings; not an executable harness
    features/                           Feature helpers; verify against paper equations
    metrics/                            Offline/online metric helpers
    simulation/                         Schedule/collector helpers; topology is descriptive
  results/                              Legacy outputs and reporting scripts
  docs/                                 Audit, methodology, novelty review
```

The nested `loft_project/LOFT_ATTACK_MITIGATION/README.md` is not the project entrypoint. Work from the top-level clone directory.

## 6. First session: reproduce the offline smoke test

### Step 1 — clone and inspect

```bash
git clone https://github.com/asifahmedutsa/LOFT_ATTACK_MITIGATION.git
cd LOFT_ATTACK_MITIGATION
git status --short
git log -5 --oneline
git switch -c codex/loft-testbed
```

If you received a folder that already contains `.git`, enter it and run the inspection commands instead of cloning again. Confirm the handoff and novelty review are present before relying on the remote alone.

### Step 2 — create an isolated offline environment

The following commands target macOS/Linux shells. Keep the environment outside the checkout because the current `.gitignore` does not ignore `.venv/`.

```bash
python3 --version
python3 -m venv "$HOME/.venvs/loft-offline"
source "$HOME/.venvs/loft-offline/bin/activate"
python -m pip install numpy pandas scikit-learn
```

There is no committed dependency lockfile. The earlier smoke run used Python 3.13.7, NumPy 2.3.5, pandas 2.3.3, and scikit-learn 1.9.0. Versions on your machine may differ; record them and avoid assuming identical numerical results. The audited evaluator does not require Flower, Ryu, Mininet, CatBoost, or prior local-model training.

### Step 3 — run against the existing dataset

From the repository root:

```bash
mkdir -p "$HOME/loft-runs/handoff-smoke"
python loft_project/eval/run_audited_eval.py \
  --data-path loft_project/data/full_dataset.csv \
  --output-dir "$HOME/loft-runs/handoff-smoke" \
  --seed 42
python -m pip freeze > "$HOME/loft-runs/handoff-smoke/environment.txt"
git rev-parse HEAD > "$HOME/loft-runs/handoff-smoke/source_commit.txt"
```

Use a new output directory for subsequent experiments; reusing it overwrites artifacts. Do not pass `--allow-leakage-prone-feature` for the baseline smoke test.

Inspect `metrics.json`, `manifest.json`, `predictions.csv`, `confusion_matrix.csv`, `roc_points.csv`, `train_indices.csv`, and `test_indices.csv` in that output directory. Confirm that `spoofing_conf` is excluded and that counts match your input data. This is a runtime/provenance check, not proof that evaluation design is sufficient for publication.

### Step 4 — record your starting point

Write down your OS, Python/package versions, commit, dataset hash, command, and output location. Preserve the original checked-in dataset so future changes remain comparable. Fix discrepancies before moving to online experiments.

## 7. Known blockers to address

1. **Federation does not update predictors.** `fl_client.py` returns RF feature importances; both training and evaluation ignore incoming aggregated parameters. Replace this with an actual shared-model or defined distillation protocol.
2. **Feature schemas disagree.** The local trainer prepares 15 features; the FL client prepares 19. Define one schema and test it across training, inference, and telemetry.
3. **The controller does not grow the forwarding table as intended.** It installs a table-miss rule and sends Packet-Out, but does not install distinct forwarding rules for arriving flows. There is no trained online detector/eviction loop.
4. **Paths assume the original layout.** Several legacy scripts read/write `~/loft_project/...`, even when run from a clone elsewhere. Change them to explicit CLI paths or paths relative to the project before execution. This affects generators, local training, federation, and controller logs.
5. **Synthetic shortcuts remain.** Normal and attack branches use different `burst_score` formulas; dropping `spoofing_conf` alone does not fix data validity.
6. **DMS-BTT labels can be circular.** The baseline runner derives `state_label` from the input feature `FN` if labels are missing. Require labels from attack timing and observed overflow instead.
7. **Paper settings are not wired into a runner.** The YAML lists group columns and protocol settings, but the offline runner currently uses a row split, and the topology module is only a dataclass. Merely editing YAML does not enforce an experiment.
8. **Topology differs from the paper.** Correct the scaffold's six benign users plus two attackers to the paper's six user hosts including two attackers, plus a server.

Do not start the Flower server/clients expecting valid federated results. First repair paths, feature schemas, and parameter application. Do not regenerate data as the first setup step: the checked-in dataset is enough for the smoke test, and the generator currently writes outside the clone.

## 8. First development milestone: a working bounded-table experiment

Use a Linux VM or Linux test host for Mininet/OVS. The current owner's machine is macOS; no online testbed run was validated during this handoff. Keep the networking environment separate from the offline environment until compatible versions are established. Record OS, Mininet, Ryu, OVS, OpenFlow, and traffic-tool versions; add reproducible installation instructions when tested.

The first milestone should run **benign-only** and **attack-without-defense** conditions on an isolated testbed:

- DMS-BTT reference topology: one controller, two switches, six user hosts including two attackers, plus a server.
- Inter-switch link: 250 Mbps / 15 ms. Host links: 1,000 Mbps / 2 ms.
- Enforced table capacity: 3,500 entries; idle timeout: 10 seconds. Account for infrastructure rules when reporting occupancy.
- Background replay: paper's `bigFlows.pcap`, 300 packets/second per replaying user host. The trace is not bundled; obtain it or document a substitute and the resulting replication difference.
- Reference LFTO parameters in YAML: intervals `[5, 8.5]`, `[5.5, 9]`, `[6, 9.5]` seconds; step values 75/100/125; `M = 1700`. Verify the recurrence and packet-refresh semantics in the paper; the existing schedule helper is not a validated traffic generator.
- Reference offline collection: 150-second runs, one-second samples, attack onset at 50 seconds.
- Reference online comparison: 600 seconds. Preserve separately documented activation timing, including the paper's example defense activation at 100 seconds.

Implement distinct flow admission, attack-flow refresh, bounded capacity, counters, and a measurement loop. Explicitly configure OVS overflow behavior; automatic eviction can mask the no-defense overflow condition. Software OVS experiments do not measure physical TCAM or Tofino line-rate performance.

**Acceptance evidence:** benign forwarding works; distinct arriving flows create entries; counters show expiry/refresh; the attack fills the table without defense and causes admission failures; legitimate service degradation is measurable; stopping the attack allows recovery. Save occupancy timelines, flow snapshots, control events, and throughput/latency measurements with independent run IDs and seeds. Do not force the published overflow timestamp.

Suggested first implementation units:

1. Replace/extend the descriptive topology with a runnable Linux topology and deterministic teardown.
2. Implement reactive forwarding-rule installation and bounded-table configuration.
3. Add a paper-aligned attack driver that retains flow identities and refreshes them before timeout.
4. Wire a collector for flow statistics, Packet-In/Table-Full events, and legitimate service measurements.
5. Add focused checks for admission, timeout/refresh, and ground-truth labeling; collect a small repeated pilot.

## 9. Work after the first milestone

Proceed in this order:

1. **Causal data and labels:** one extractor for both traffic classes; retain run/domain/trace/flow IDs, protocol, window boundaries, attack settings, and provenance. Use distinct training, validation, and test runs.
2. **DMS-BTT reimplementation:** state features `FN/APIT`; flow features `Numb/PIT/Sizep`; CatBoost classifiers; two thresholds; eviction and elephant-flow protection. Require explicit labels. Record every deviation from paper details.
3. **Matched baselines:** no defense, OVS eviction, DMS-BTT, local SVM/RF, pooled centralized training; extend to FloRa/FTOP when specified sufficiently. Keep detector-only and full-defense comparisons distinct.
4. **Real federation:** apply received weights, demonstrate transfer, compare local/pooled/FedAvg and an appropriate heterogeneity baseline under the same features/backbone. Measure communication overhead.
5. **Novel mechanism:** define a precise contribution around defense across heterogeneous domains at a specified benign-flow disruption and controller-time budget. SVM/RF, federation, and multiple controllers alone are already covered in prior work.
6. **Generalization and reporting:** independent attack runs, unseen settings/domains, multiple traces, repeated seeds, uncertainty over runs, and ablations. Report benign goodput/eviction, overflow, latency, malicious occupancy, control load, and CPU as well as classifier metrics.

Start with a three-domain pilot after the single-domain reference works. Begin with at least five independent runs per selected condition to estimate variability, then decide the experiment size. Do not treat adjacent snapshots as independent trials. Test the specific benefit of collaboration before adding more model complexity.

## 10. DMS-BTT offline runner: when to use it

The current script is useful only after preparing suitable data. It is not a complete defense or a validated reproduction. Run it as a file, from the repository root; its imports currently assume that execution style.

Required CSVs:

- State CSV: `FN`, `APIT`, **explicit `state_label`**. Labels 0/1/2 mean benign / attack before overflow / overflow-stage attack. Include classes and enough samples for splitting.
- Flow CSV: `Numb`, `PIT`, `Sizep`, `label`, with 0/1 benign/malicious labels from experimental ground truth.

After correcting labels/splits and verifying feature equations, install CatBoost in the chosen offline environment and invoke:

```bash
python -m pip install catboost
python loft_project/eval/run_dms_btt_offline_baseline.py \
  --state-csv /absolute/path/to/state_dataset.csv \
  --flow-csv /absolute/path/to/flow_dataset.csv \
  --output-dir "$HOME/loft-runs/dms-btt-offline"
```

The runner currently uses a 5:1 row split and writes `dms_btt_offline_metrics.json`. That does not hold out independent runs. Implement the required split/provenance artifacts before research comparisons; do not present this command as a completed paper replication.

## 11. Definition of a successful handoff

By the end of your first working session, you should have:

- The repository, the three research documents, and access to the paper.
- A reproducible offline smoke run with recorded environment and artifacts.
- A written understanding that the 98% result is synthetic and the federated/online pipeline is unfinished.
- A branch and concrete tasks for the bounded-table attack-only milestone.
- A Linux testbed plan and an explicit list of missing dependencies/traffic traces.

The next research decision is whether a precise federated defense mechanism improves legitimate service at matched disruption/overhead, or whether the strongest contribution is a reproducible LFTO benchmark. Let the controlled experiments decide.
