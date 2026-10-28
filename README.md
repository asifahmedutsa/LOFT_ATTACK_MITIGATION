# LOFT_ATTACK_MITIGATION

A research prototype for detecting and mitigating low-rate flow-table overflow (LFTO)
attacks across multiple SDN controllers.

**Status (25 Oct 2026).** The project contains two things:

- **FL-DualGuard v2:** a federated detector, per-controller budget calibration, and
  soft-demotion mitigation.
- **LOFT-Bench:** a test-covered multi-controller LFTO simulator and benchmark.

All of it is implemented and evaluated in simulation. A Mininet/OVS/Ryu harness is
written but **has not yet been run**, because it needs sudo.

Headline result (v2.1, fresh seeds, cluster-bootstrap CIs): 1.7 % of benign flows
harmed, meaning refused an entry or evicted while still active. The strongest fair
baseline, DMS-BTT tuned on the same budget plus a blocklist, harms 4.7 %, and 42.8 % of
flows are refused an entry with no defense. The advantage comes from unseen and
mimicry attack variants; on DMS-BTT's own settings the tuned baseline is better.

Federation is needed (revision step 3, pre-registered, fresh seeds 7000–7009): a local
detector given the published DMS-BTT attack settings harms 5.8 % of benign flows against
1.5 % for FedAvg. A one-shot ensemble of the local models matches FedAvg on harm, and the
gain appears only when controllers see different attack variants (`results_v2.md` §12).

Against an adaptive attacker refreshing faster than once a second, every learned
defense fails (revision step 4). A per-port fair-share guard (PortGuard) bounds harm at
about 6 % when attackers have their own ports; combining it with DualGuard is still open
(`results_v2.md` §14).

The independent review (`docs/results_v2.md` §9) identified open problems,
most importantly a faster-refreshing adaptive attacker. Work on them follows
`loft_project/docs/submission_revision_plan.md`.

| Read | For |
|---|---|
| [loft_project/docs/results_v2.md](loft_project/docs/results_v2.md) | Results, including negative findings and what is missing before submission |
| [loft_project/docs/methodology_v2.md](loft_project/docs/methodology_v2.md) | Threat model, design, splits, metrics, reproduction |
| [loft_project/docs/paper_draft.md](loft_project/docs/paper_draft.md) | Paper outline with numbers and TODOs |
| [loft_project/testbed/README.md](loft_project/testbed/README.md) | Emulation acceptance runs |
| [HANDOFF.md](HANDOFF.md) | Original handoff and history (the §0 update lists what changed) |

## Quick start

```bash
python3 -m venv ~/.venvs/loft && source ~/.venvs/loft/bin/activate
pip install -r loft_project/requirements.txt
cd loft_project
python -m pytest -q tests
python -m loftbench.experiment --out results/v2 --stages collect,train,offline,export
python -m loftbench.tune --out results/v2
python -m loftbench.experiment --out results/v2 --stages online,report
# v2.1: pre-registered validation-only selection, then a one-shot fresh-seed test
python -m loftbench.v21 --src results/v2 --out results/v21 --stages prereg,train,select,test,export,report
```

## Layout

```text
loft_project/
  loftbench/     simulator, traffic/attacks, features, models + FL, defenses, pipeline, report
  tests/         unit tests for table semantics, labels, federation, calibration, splits
  testbed/       Mininet/OVS/Ryu harness that shares the loftbench feature extractor
  results/v2/    v2 tables, figures, CSVs, manifest (large pickles are git-ignored)
  results/v21/   v2.1 pre-registration, validation selection, one-shot test, exported model
  docs/          methodology, results, paper draft, earlier audits
  (legacy)       attack/, data/, federated/, models/, topology/, eval/, results/*.png
```

The legacy directories hold the original prototype. Its 98 % accuracy figures come
from synthetic data with class shortcuts, so they must not be used as evidence. See
`loft_project/results/LEGACY.md`.
