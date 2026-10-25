# LOFT_ATTACK_MITIGATION

A research prototype for detecting and mitigating low-rate flow-table overflow (LFTO)
attacks across multiple SDN controllers.

**Status (25 Oct 2026).** The project contains two things:

- **FL-DualGuard v2:** a federated detector, per-controller budget calibration, and
  soft-demotion mitigation.
- **LOFT-Bench:** a test-covered multi-controller LFTO simulator and benchmark.

All of it is implemented and evaluated in simulation. A Mininet/OVS/Ryu harness is
written but **has not yet been run**, because it needs sudo.

Headline result from the pre-registered, one-shot test on fresh seeds (v2.1): 2.2 % of
benign flows impacted, against 12.1 % for a DMS-BTT reimplementation and 42.8 % with no
defense.

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
