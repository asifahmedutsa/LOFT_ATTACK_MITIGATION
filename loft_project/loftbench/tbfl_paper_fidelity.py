"""Fidelity against the papers (docs/final_campaign_prereg.md, section 4): each baseline's published
headline result beside ours. Detection: the deployed per-entry model (results/v21/exported, and the
pooled arm's in pool_T1B) at the threshold its defense applies, on the T1B test recordings (seeds
4176-4178): the rows of the five standard attacks' recordings and of the benign-only ones, as
recorded. Mitigation: the published attack share, beside the earlier testbed runs (A2, s11); the
campaign's own runs replace these.

    PYTHONPATH=. ~/.venvs/loft/bin/python -m loftbench.tbfl_paper_fidelity
"""
import gc
import os
import pickle
from types import SimpleNamespace

import numpy as np

from .data import Dataset
from .tbfl import OUT, TEST
from .tbfl_fidelity import MODELS, STD, _load

EXP = "results/v21/exported"
DST = "results/testbed_baselines_tb/fidelity_papers.md"
CHUNK = 100_000
# Published headline results, read from the papers (Other Paper/M Sc Paper), with their setting.
PAPER = {
    "FTMaster": ("Mininet; LFTO; classifiers' accuracy; attack rules in the table with FTMaster",
                 "accuracy 98 % or higher (most classifiers)", "attack rules below 25 % of the table early, then blocked"),
    "FTOP": ("simulation; LFTO; Table IV",
             "accuracy up to 98 %", "average Pm 20.66 %, table usage 50.56 %"),
    "FloRa": ("Mininet, tables of 1,500-3,000 entries; LOFT",
              "accuracy 99.49 %, FPR 0.01 %", "attack rules below 35 % of the table early, then detected"),
    "DMS-BTT": ("table of 3,500, 600 s runs; LFTO; Table 6",
                "accuracy > 92 %, recall > 80 %, precision > 90 %, F1 > 85 %",
                "average attack flow share 5.25 %, peak 52.32 %, table utilisation 48.69 %"),
    "FTODefender": ("simulation; LFTO; Table 3, against REFUSE",
                    "accuracy 97 %", "Pm 38.74 % (REFUSE) reduced to 22.23 %"),
}
# Earlier testbed runs, A2, s11 attack share after onset (results/tbfl/compare_baselines_dev.md):
# simulator-trained models, blocks in the controller only.
EARLIER = {"FTMaster": "10.0 % (5 runs)", "FTOP": "33.9 % (1 run)", "FloRa": "39.1 % (1 run)",
           "DMS-BTT": "18.7 % (5 runs)", "FTODefender": "no run"}
SOURCE = {"FTMaster": "simulator T1A", "FTOP": "simulator T1A", "FloRa": "C3", "DMS-BTT": "C3", "FTODefender": "C3"}


def metrics(f, y):
    tp, fp = int((f & y).sum()), int((f & ~y).sum())
    fn, tn = int((~f & y).sum()), int((~f & ~y).sum())
    pr, rc = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return dict(acc=100 * (tp + tn) / len(y), prec=100 * pr, rec=100 * rc,
                f1=100 * 2 * pr * rc / max(pr + rc, 1e-12), fpr=100 * fp / max(fp + tn, 1))


def main():
    runs = pickle.load(open(f"{OUT}/rows.pkl", "rb"))
    d = Dataset.concat([runs[("T1B", v, s)] for v in [None] + STD for s in TEST])
    del runs
    y = d.y == 1
    res = {}
    for base, model, unit, fname, feat, decide in MODELS:
        if unit != "entry":
            continue
        for arm, dd in (("main", EXP), ("pooled", f"{EXP}/pool_T1B")):
            m = _load(os.path.join(dd, f"{fname}_T1B.json"), fname)
            # In chunks: the pooled FTOP forest on all rows at once ran out of memory on 8 GB.
            f = np.concatenate([decide(m, feat(SimpleNamespace(X=d.X[i:i + CHUNK], dms=d.dms[i:i + CHUNK])))
                                for i in range(0, len(y), CHUNK)])
            res[(base, arm)] = metrics(f, y)
            del m
            gc.collect()
    L = ["# Retrained baselines against their papers' headline results", "",
         "loftbench/tbfl_paper_fidelity.py. Ours, detection: the deployed per-entry model at the threshold",
         "its defense applies, on the T1B testbed test recordings (seeds 4176-4178; G1-G3, Spoof, Pulse and",
         f"benign-only recordings as recorded: {len(y)} rows, {int(y.sum())} attack). The papers score",
         "their own traces and attacks, so the numbers are beside each other, not a replication.", "",
         "| Baseline | Paper's setting | Published detection | Ours (training) | Acc. | Prec. | Rec. | F1 | FPR | "
         "Pooled arm: Acc. / FPR |", "|---|---|---|---|---|---|---|---|---|---|"]
    for b, (setting, det, _) in PAPER.items():
        r, p = res[(b, "main")], res[(b, "pooled")]
        L.append(f"| {b} | {setting} | {det} | {SOURCE[b]} | {r['acc']:.2f} | {r['prec']:.2f} | {r['rec']:.2f} | "
                 f"{r['f1']:.2f} | {r['fpr']:.2f} | {p['acc']:.2f} / {p['fpr']:.2f} |")
    L += ["", "Mitigation: the published result, and our earlier testbed runs (A2, attack share of s11 after",
          "onset, results/tbfl/compare_baselines_dev.md: simulator-trained models and controller-only source",
          "blocks, both changed since). The campaign's runs, with the deployed models and switch drop rules,",
          "give the numbers reported in the paper.", "",
          "| Baseline | Published mitigation | Earlier testbed, A2, s11 |", "|---|---|---|"]
    for b, (_, _, mit) in PAPER.items():
        L.append(f"| {b} | {mit} | {EARLIER[b]} |")
    L += ["", "rDefender has no learned model; its paper's headline is Packet-In loss (none under its HA flood, where",
          "SAIA, TableGuard and LtRFT lose Packet-Ins) and malicious rules limited on attacked ports; the campaign",
          "reports its lost first packets and attack share."]
    open(DST, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
