# FL-DualGuard: novelty, feasibility, and research next steps

Review date: 11 October 2026. Code reviewed at `de7ac9676846117820c75650270e7309517b8904`.

## 1. Verdict and scope

This review concerns **our FL-DualGuard project**. DMS-BTT is a published comparison method. The approach currently consists of synthetic packet/flow features, an SVM–Random Forest soft-voting classifier, three nominal controller clients, and evaluation/reporting scripts.

**The current formulation has weak methodological novelty.** Its main ingredients already appear in related work. In particular, FTSheild already combines SVM and Random Forest for LOFT detection and mitigation, while earlier work covers federated SDN intrusion detection and federated low-rate attack detection. Switching classifiers, adding controllers, or reporting a higher accuracy is insufficient to establish a new research contribution.

**A research prototype is technically feasible, but the current implementation does not establish a working federated defense.** The next milestone should demonstrate genuine learning across controllers and measurable protection of legitimate traffic under unseen LFTO attacks.

This is a targeted literature review, not a systematic review or proof that every possible combination has been published. I searched for federation, low-rate attacks, flow-table overflow, multi-controller SDN, SVM/RF ensembles, predictive mitigation, personalization, and distillation. Conclusions use publisher pages, author repositories, original papers, and the supplied DMS-BTT PDF. Where only a publisher abstract or indexed excerpt was accessible, the comparison is limited to those verified claims. An identical complete FL-DualGuard algorithm was not established; an absence in these searches does not prove novelty.

## 2. Closest prior work and implications

### FTSheild / FTShield — direct overlap with the classifier idea

Jain, Venkanna, and Vollala's **FTSheild: An intelligent framework for LOFT attack detection and mitigation with programmable data plane**, Expert Systems with Applications 265, 125865 (2025), explicitly combines SVM and RF for LOFT detection. It implements a P4/Tofino prototype and blocks attack hosts. Its publisher abstract reports 95.7% accuracy under its own experiment.

Implication: SVM + RF applied to LOFT is already published. Our soft-voting implementation may differ from their fusion method; the accessible material does not establish identical algorithms. Nevertheless, classifier selection alone is a weak novelty argument. Hardware deployment is also a substantial difference when interpreting runtime comparisons. [Publisher source](https://www.sciencedirect.com/science/article/abs/pii/S0957417424027325).

### Ahuja et al. — earlier SVC–RF SDN detection

**Automated DDOS attack detection in software defined networking**, Journal of Network and Computer Applications 187, 103108 (2021), proposes an SVC–RF hybrid and reports 98.8% testing accuracy on its SDN dataset.

Implication: the ensemble combination predates this project even outside LOFT. This is broader DDoS detection; it does not establish the same LFTO threat model. [Publisher source](https://www.sciencedirect.com/science/article/pii/S1084804521001296).

### Weighted federated low-rate detection — already studied

Ali et al., **Low Rate DDoS Detection Using Weighted Federated Learning in SDN Control Plane in IoT Network**, Applied Sciences 13(3), 1431 (2023), studies weighted federation for low-rate DDoS using MATLAB experiments.

Implication: federation for low-rate SDN attacks is not a new broad claim. Control-plane LR-DDoS and switch table exhaustion are different targets; our contribution would need a precise LFTO mechanism and online evidence. [Publisher source](https://www.mdpi.com/2076-3417/13/3/1431).

### FedSec — federation across multiple SDN controllers

Alkhamisi, Katib, and Buhari, **Federated Learning-Based Security Attack Detection for Multi-Controller Software-Defined Networks**, Algorithms 17(7), 290 (2024), proposes a federated security architecture with GCNN–GRU models and SDN-specific dataset enrichment.

Implication: using multiple controllers and federated attack knowledge is established. This paper's broader data-plane intrusion task and enriched NSL-KDD evaluation differ from a faithful LFTO testbed. [Publisher source](https://www.mdpi.com/1999-4893/17/7/290).

### FloRa — a necessary LOFT baseline

Mudgal et al., **FloRa: Flow Table Low-Rate Overflow Reconnaissance and Detection in SDN**, IEEE TNSM (2024), uses CatBoost, packet arrival frequency, content relevance, and possible spoofed-IP features, followed by malicious-flow blacklisting and eviction. The authors report 99.49% detection accuracy.

Implication: spoofing-related information, timing features, and ML-based LOFT mitigation already exist. FloRa's reported accuracy is higher than 98% on its own protocol, but neither number establishes superiority across different datasets. [Author paper and IEEE DOI](https://arxiv.org/abs/2410.19832).

### FTMaster, FTOP, and DMS-BTT — detect then mitigate is established

**FTMaster** (2023) monitors table state, classifies flows, evicts malicious entries, and blocks attack sources. [Author-hosted original paper](https://www.cs.newpaltz.edu/~lik/publications/Chenjun-Gao-IEEE-TNSM-2023).

**FTOP** (online publication 2023; journal issue 2024) predicts flow count, detects attacks with RF, and applies eviction/prevention to LFTO and legitimate flash crowds. Early prediction and preventing overflow with limited evictions are already part of this work. [Author-hosted original paper](https://www.cs.newpaltz.edu/~lik/publications/Dan-Tang-IEEE-TNSE-2024).

**DMS-BTT** (2025) combines CatBoost state detection, malicious-flow identification, and two occupancy thresholds. Its supplied PDF explicitly lists expanding the environment and federation-inspired incentives among future directions. This is a research lead, not a novelty guarantee. [Publisher source](https://www.sciencedirect.com/science/article/abs/pii/S0957417425023036); supplied `DMS_BTT_2025.pdf`, Sections 4–6.

### Recent work narrows generic federation claims further

**FL-NDR** (available online 30 June 2026) couples federated detection/unlearning with OpenFlow response. Its limitations acknowledge IID clients and synthetic SDN simulation, suggesting a useful experimental gap without proving a new method. [Original article](https://iieta.org/journals/ijsse/paper/10.18280/ijsse.160615).

**Dynamic weighted federated learning with client level differential privacy for DDoS detection in IoT networks** (7 October 2026) already combines non-IID training, dynamic weighting, and formal privacy accounting. It addresses broader IoT DDoS. Adding those ingredients to this project would require further differentiation. [Original article](https://link.springer.com/article/10.1007/s44163-026-02452-0).

**DeepMonitor** (2021) uses federated DDQN for traffic monitoring with explicit table-capacity considerations. It is not the same LFTO classifier, but it prevents claiming that federation and table-capacity management have never been combined. [Author institution record](https://digitalcommons.kennesaw.edu/facpubs/5003/).

## 3. Correct the accuracy comparison

The supplied DMS-BTT PDF reports these distinct outcomes on printed page 8:

- Table 3, mixed traffic: **86.89% three-state accuracy** and **94% attack detection rate**. The latter combines both attack stages as positive.
- Tables 4–5, mixed parameters: **92.42% malicious-flow accuracy**, **83.12% recall**, **92.51% precision**, and **87.57% F1**.
- Table 6, printed page 12: **5.25% average malicious table occupancy**, plus other online mitigation outcomes.

Therefore, **94% is not DMS-BTT's accuracy or a universal SOTA accuracy**. Our binary flow classification, their three-state classification, and their online mitigation metrics are separate tasks. Published percentages should be treated as context until the methods are rerun on matched data and splits.

I also executed the existing audited evaluator against the repository's current `full_dataset.csv`, excluding `spoofing_conf`. This produced:

- 4,000 synthetic records; 3,200 training / 800 test; seed 42.
- Accuracy **98.375%**; precision **98.282%**; recall **97.279%**; F1 **97.778%**.
- Confusion counts: TN 501, FP 5, FN 8, TP 286; FPR **0.988%**.

This confirms that approximately 98% can be computed by a fitted classifier on this synthetic split. It **does not establish real-traffic performance, federation gains, or SOTA superiority**. Every one of the 4,000 source/destination/port groups is a singleton, so the advertised group split does not hold out independent attack runs, domains, or temporal windows. The data has no run, scenario, controller, or attack-parameter identifier. Test attack prevalence is 294/800, substantially different from many deployment settings.

Temporary smoke-test artifacts are in `/tmp/loft_novelty_feasibility_smoke/`. They are a diagnostic run, not publication results. Preserve new benchmark artifacts with dataset hashes, versions, and immutable run identifiers.

For this diagnostic: dataset SHA-256 `632a44eb0d0d39ab3e1d6b82dca4a48a5dba6206a292712a51ccd1bca305dff6`; Python 3.13.7, pandas 2.3.3, NumPy 2.3.5, scikit-learn 1.9.0. Reproduce from the repository root with:

```bash
python3 loft_project/eval/run_audited_eval.py \
  --data-path loft_project/data/full_dataset.csv \
  --output-dir /tmp/loft_novelty_feasibility_smoke \
  --seed 42
```

## 4. Feasibility findings from the actual code

### Genuine federation is missing

`federated/fl_client.py:67` returns only RF `feature_importances_`. Both `fit` and `evaluate` ignore the incoming aggregated parameters. Consequently, the server aggregates summaries that never update client predictors. Local retraining repeated three times is not evidence of collaborative learning.

There is also a schema mismatch: `models/local_model_trainer.py` prepares 15 features, while `federated/fl_client.py` prepares 19 before loading the locally trained model. Fit can replace the loaded model, but then the earlier saved-model evidence no longer describes that fitted predictor. The schemas must be unified.

Practical choice: keep SVM/RF as a centralized/local baseline; implement a small model whose weights can actually be shared for the first federated prototype. If retaining heterogeneous SVM/RF clients is essential, use a defined prediction/distillation protocol with a justified reference dataset and communication accounting. Distillation itself is prior art: [FedDF, NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/hash/18df51b97ccd68128e994804f3eccc87-Abstract.html).

### The controller does not currently reproduce table exhaustion

`topology/ryu_controller.py:33` installs a table-miss rule. Its packet handler ends with Packet-Out and does not install distinct forwarding rules for arriving flows. This code therefore cannot demonstrate the intended growth in attack entries. It also does not run a trained classifier, delete classified entries, set the paper's idle timeout, or collect the required table counters. Packet-In logs alone cannot supply the feature schema required by the offline model.

Build and verify rule installation, flow statistics, labels from the experiment harness, and a real response loop. With no defense, the attack must visibly fill the bounded table and impair legitimate forwarding before any defense claim is tested.

### The DMS-BTT implementation is still a scaffold

- `eval/simulation/topology_dms_btt.py` defines a dataclass and description, not an executable Mininet network. Its six user hosts plus two attackers differ from the paper's six user hosts including two attackers, plus a server.
- `eval/run_dms_btt_offline_baseline.py:23` can derive labels from `FN`, an input feature. This creates a learn-the-threshold task. The paper instead uses known attack onset and actual overflow to label stages; occupancy above 75% alone does not prove an attack.
- Its 5:1 row split does not implement independent run/domain holdouts or all paper parameter experiments. Keep a faithful replication track and a stricter generalization track separately labeled.
- The schedule helper generates burst sizes but does not transmit traffic or retain and refresh installed attack flows. Verify its interpretation against the paper's attack recurrence before using it.
- No executable DMS-BTT eviction loop is present. Configuring thresholds and calculating metrics is insufficient to reproduce the full defense.

The paper states that the authors cannot share their data (printed page 12). A new testbed is a **reimplementation under documented conditions**, not an exact replay of the original results. Also record unavailable hyperparameters and implementation ambiguities.

### Synthetic data still encodes class-specific rules

Removing `spoofing_conf` fixes only one shortcut. In `data/generate_realistic_dataset.py`, the normal branch computes `burst_score` with a different formula from the attack branch (lines 148 and 266). The remaining distributions are hand-selected by class. Such generated features do not validate a deployable causal extractor.

Use one feature-extraction function for all traffic. Experimental labels must never decide which formula to execute. Fit transformations only on training data; make features available at the actual decision time; avoid completed-flow statistics for claims about early detection.

### Platform and runtime

The current host is macOS. Use a Linux VM or Linux test host for Mininet experiments, following the [official installation guidance](https://mininet.org/download/). Start with software OVS; disclose that it emulates a finite table and does not measure physical TCAM or Tofino line-rate performance.

Enforce and verify a real OVS `flow_limit`, document the table-miss rule's capacity cost, and explicitly choose the overflow policy. Automatic OVS eviction can hide overflow and change the no-defense baseline. [Official OVS table configuration](https://www.openvswitch.org/support/dist-docs/ovs-vswitchd.conf.db.5.html).

For one-second polling, measure feature extraction, inference, and rule updates together; the full decision loop must fit its interval. Report tail latency, training/communication overhead, CPU, and legitimate throughput. Keep federated training out of the Packet-In handler.

## 5. Recommended research direction

Working question:

> Can federated collaboration across heterogeneous SDN domains improve defense against unseen LFTO traffic while meeting a specified budget for legitimate-flow disruption and controller overhead?

This is a **candidate research direction**, not an established novelty claim. Personalization, adaptive thresholds, predictive capacity control, and privacy mechanisms already have prior work. Define a precise new mechanism or an unusually rigorous, reproducible LFTO benchmark; verify the final mechanism against the closest methods before claiming originality.

A manageable design is a shared detector with local probability calibration and a controller-specific eviction policy. Choose calibration and policy settings using held-out local validation runs. Train on measured packet/flow behavior, and drive actions from calibrated malicious-flow estimates plus local table pressure. Quantify both benign short-flow damage and elephant-flow damage.

The research objective should be operational: reduce overflow duration and preserve legitimate goodput, subject to a predeclared benign-flow eviction budget and controller-time budget. The budget is an empirical acceptance criterion, not a distribution-free guarantee unless a separate proof supports one. Attacker churn or reuse of spoofed IPs must not turn labels or IP blocking into an oracle.

## 6. Ordered next steps and completion gates

### Step 1 — narrow the claim and freeze the experiment contract

Specify attacker powers, which domains collaborate, which traffic remains private, when prediction happens, and what causes rule admission/deletion. Stop using “98% versus 94% SOTA.” Declare primary online outcomes, a permitted benign eviction budget, and resource limits before inspecting final test results.

Gate: a one-page method definition and a versioned experiment configuration. Establish whether our contribution is a new policy/learning mechanism or a benchmark/system study.

### Step 2 — make an attack-only testbed work

Use the DMS-BTT topology, 3,500-entry limit, 10-second idle timeout, 300 pps background replay, and its three attack parameter sets. Install distinguishable rules; refresh attack flows before expiration; collect occupancy, admission failures, and legitimate service outcomes. Add a genuine benign-only control.

Gate: recorded evidence that no-defense traffic causes table exhaustion under the attack, while the benign control establishes the normal load. Do not tune attack generation merely to reproduce a published overflow timestamp.

### Step 3 — collect ground truth and causal features

Store `run_id`, domain/controller, scenario, seed, trace ID, attack parameters, timestamps, flow identity including protocol, and feature-window boundaries. Label from controlled traffic provenance and attack timing. Rotate addresses across runs; include legitimate sparse flows and benign load surges. One packet/flow extractor must serve both classes.

Gate: consistent feature schemas, no label-driven formulas, and no shared runs or overlapping windows between train, validation, and test. Freeze the final test set. Use train-only scaling and validation-only tuning/calibration.

### Step 4 — build defensible baselines before a new model

Minimum baselines: no defense, OVS eviction, standalone DMS-BTT, FloRa when sufficiently specified, FTOP, local SVM/RF, and a pooled centralized model. Include FTSheild as closest classifier prior art; a software adaptation must be labeled and cannot establish equivalence to its hardware prototype.

Use identical traffic, seeds, observation time, and outcomes for each executable baseline. First compare detectors with a fixed mitigation policy, then compare full defenses. This separates learning improvements from more aggressive deletion.

Gate: prediction artifacts and online measurements for every evaluated method, with replication deviations documented.

### Step 5 — implement and prove genuine federation

Start with three actual domains whose service mix and attack exposure differ. Apply received global weights before local training and inference. Verify that an update from another domain changes the receiving model and held-out predictions. Add local-only, pooled, FedAvg, and a heterogeneity baseline such as FedProx under the same backbone and feature set.

Gate: measured collaboration effects and communication costs. Equal partitions of a shuffled synthetic dataset do not establish cross-domain transfer. Raw-data locality alone does not establish formal privacy.

### Step 6 — test the specific proposed contribution

Add the local calibration/eviction-budget mechanism only after the basic federation works. Ablate federation, calibration, the proposed policy, and extra features one at a time. Use the same backbone and input features when isolating federation effects.

Gate: repeatable improvement over simple local/global thresholds and federation baselines at matched benign disruption. If the combined method fails to improve these trade-offs, revise the hypothesis rather than adding unrelated modules.

### Step 7 — run generalization and online experiments

Run two explicitly labeled tracks:

1. Paper-oriented replication: the supplied paper settings and reported tasks; disclose ambiguities in splits, versions, and thresholds.
2. Generalization: independently held-out attack runs, unseen attack parameter sets, future-time windows, different background traces, and domains unseen in training. Evaluate zero-shot unseen-domain transfer separately from adaptation with local validation data.

Begin with at least five independent seeds/runs per selected condition as a pilot. Report uncertainty over runs, then size further experiments using the observed variability. Adjacent snapshots from one run are not independent replicates. Pair defenses on the same traffic seeds; treat no overflow as a censored outcome, not a fabricated negative time.

Measure classification precision/recall/F1 and attack detection rate separately; online outcomes include average/peak malicious occupancy, overflow duration/time, benign eviction fraction, goodput, latency, Packet-In, Table-Full, controller CPU, and federation bytes/rounds. Report whole-run and post-activation windows separately. Test low attack prevalence rather than relying only on near-balanced synthetic classes.

Gate: an operational benefit with confidence intervals on untouched scenarios and acceptable legitimate traffic/resource costs.

### Step 8 — decide the paper's contribution from the evidence

Proceed with a method paper if a clearly specified mechanism improves the operational trade-off and the closest literature does not already implement it. Proceed with a benchmark/system paper if the strongest contribution is independent-run LFTO data, faithful reproducible baselines, and evidence of where federation helps or fails. A negative federation result can still inform that study.

If a local CatBoost model plus an existing eviction policy performs equally well at lower cost, the evidence does not support the proposed federation claim.

## 7. Immediate practical recommendation

**Implement and validate the bounded-table attack-only harness first, then repair labels/features, and then implement real federation.** These establish whether there is a real problem, usable observations, and a benefit from collaboration. Refining the current accuracy number cannot resolve those questions.

The earlier methodology file's federated execution commands should currently be treated as prototype instructions. The earlier description that the project was fully fixed overstated its readiness: substantial learning and online-defense work remains. This review documents those gaps; it does not modify the algorithms or claim that the online experiments have been executed.
