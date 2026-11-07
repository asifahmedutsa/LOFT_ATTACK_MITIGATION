"""Builds docs/fever_dmsbtt_tables.pdf: the result tables of DMS-BTT (Tang et al., ESWA 2025,
Tables 2-6) reproduced for FEVER from our own data. Every number is computed here from committed
or recorded results:
  Table 1  attack parameters and time to overflow   <- loftbench/config.py; v5 campaign, defense none
  Table 2  attack detection, run level               <- results/testbed_prereg_v5/runs.csv (FEVER)
  Table 3  malicious-entry identification per attack <- results/v5/t1b_rows.pkl (simulator T1B,
           development seeds 2000-2002, no model trained on T1B), FEVER's detector at its
           deployed tau; and host identification on the testbed (v5 campaign)
  Table 4  classifier comparison                     <- results/e11_detect/table_main.csv (E11)
  Table 5  comparative experiment                    <- results/paper_figs/v5/testbed_runs.csv
  Table 6  harm to users (not in DMS-BTT)            <- same

    PYTHONPATH=. ~/.venvs/loft/bin/python docs/build_dmsbtt_tables.py
"""
import json
import os
import pickle

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from loftbench.config import attack_variant
from loftbench.ensjson import EnsembleJSON

OUT = "docs/fever_dmsbtt_tables.pdf"
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
S = dict(
    title=ParagraphStyle("t", fontName="LS-B", fontSize=15, leading=19, spaceAfter=4),
    sub=ParagraphStyle("s", fontName="LS", fontSize=10, leading=13, textColor=colors.HexColor("#444444"), spaceAfter=12),
    cap=ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, spaceBefore=12, spaceAfter=4),
    cell=ParagraphStyle("x", fontName="LS", fontSize=9, leading=11),
    note=ParagraphStyle("n", fontName="LS", fontSize=8.8, leading=11.5, textColor=colors.HexColor("#333333"), spaceBefore=4),
    p=ParagraphStyle("p", fontName="LS", fontSize=10, leading=13.5, spaceAfter=6))
W = A4[0] - 44 * mm


def table(caption, head, rows, widths, note=None, bold_rows=()):  # noqa: C901
    data = [[Paragraph(f"<b>{h}</b>", S["cell"]) for h in head]]
    for i, r in enumerate(rows):
        data.append([Paragraph(f"<b>{c}</b>" if i in bold_rows else str(c), S["cell"]) for c in r])
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    parts = [Paragraph(caption, S["cap"]), t]
    if note:
        parts.append(Paragraph(note, S["note"]))
    return KeepTogether(parts + [Spacer(1, 8)])


def pct(x, d=2):
    return "NA" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f} %"


runs = pd.read_csv("results/paper_figs/v5/testbed_runs.csv")
pre = pd.read_csv("results/testbed_prereg_v5/runs.csv")
ATT = ["A2", "A4", "E9P"]
NAME = {"none": "None", "dms-btt": "DMS-BTT", "ftmaster": "FTMaster", "rdefender": "rDefender", "ensguard-v5": "FEVER"}
DEFS = ["none", "ftmaster", "dms-btt", "ensguard-v5"]
T_ATT = 50.0
# rDefender (no ML, per-port occupancy) ran later on seeds 4140-4142 only (docs/fever_ablation_plan.md);
# it is listed once those runs exist, with a note on its seeds.
abl = "results/fever_ablation/runs.csv"
RD = pd.read_csv(abl) if os.path.exists(abl) else None

s = [Paragraph("FEVER: experimental results", S["title"]), Spacer(1, 4)]

# ---- Table 1
rows = []
for v in ATT:
    a = attack_variant(v)
    fo = pd.to_numeric(runs[(runs.defense == "none") & (runs.variant == v)].first_overflow_s, errors="coerce")
    pk = f"{a.pkts_per_refresh[0]}" if a.pkts_per_refresh[0] == a.pkts_per_refresh[1] else f"{a.pkts_per_refresh[0]}-{a.pkts_per_refresh[1]}"
    rows.append([v, f"[{a.t1_range[0]:g},{a.t1_range[1]:g}]", a.step, a.max_flows, pk,
                 "64 B" if a.size_mode == "fixed" else "benign-like", f"{(fo - T_ATT).mean():.1f}"])
s.append(table("<b>Table 1</b><br/>LFTO attack parameter setting.",
               ["Attack", "T1(s)", "S(pkt/T)", "M(pkt)", "Pkt/refresh", "Pkt size", "T2(s)"],
               rows, [0.12, 0.14, 0.13, 0.12, 0.15, 0.17, 0.12],
               "T2 is the average time from the start of the attack until the flow table overflows without defense."))

# ---- Table 2
f = pre[pre.defense == "ensguard-v5"]
rows = []
for v in ATT:
    g = f[f.variant == v]
    fb = pd.to_numeric(g.first_attack_block_s, errors="coerce")
    rows.append([v, f"{100 * (g.hosts_blocked_attack >= 2).mean():.0f} %",
                 f"{100 * g.hosts_blocked_attack.sum() / (2 * len(g)):.0f} %", f"{fb.mean():.1f}",
                 f"{100 * g.hosts_blocked_benign.sum() / (4 * len(g)):.0f} %"])
nb = pre[(pre.defense == "ensguard-v5") & (pre.variant == "benign")]
rows.append(["No attack", "-", "-", "-", f"{100 * nb.hosts_blocked_benign.sum() / (4 * len(nb)):.0f} %"])
s.append(table("<b>Table 2</b><br/>Attack detection results of FEVER.",
               ["Attack", "Attack detection rate", "Attacker identification rate", "Detection time(s)",
                "False blocking rate"],
               rows, [0.16, 0.2, 0.24, 0.18, 0.22]))

# ---- Table 3
ec = json.load(open("results/v21/exported/ens_config_v5.json"))
tau = ec["tau"]["T1B"]
model = EnsembleJSON("results/v21/exported", ec)
rows_pk = pickle.load(open("results/v5/t1b_rows.pkl", "rb"))


def metrics(tp, fp, fn, tn):
    acc = 100 * (tp + tn) / max(tp + fp + fn + tn, 1)
    rec = 100 * tp / max(tp + fn, 1)
    pre_ = 100 * tp / (tp + fp) if tp + fp else float("nan")
    f1 = 2 * pre_ * rec / (pre_ + rec) if tp and not np.isnan(pre_) else 0.0
    return acc, rec, pre_, f1


rows, tot, per = [], np.zeros(4), []
for v in ATT:
    X = np.concatenate([rows_pk[(v, sd)][0] for sd in (2000, 2001, 2002)])
    y = np.concatenate([rows_pk[(v, sd)][1] for sd in (2000, 2001, 2002)]).astype(bool)
    p = model.predict_proba(X) >= tau
    c = np.array([(p & y).sum(), (p & ~y).sum(), (~p & y).sum(), (~p & ~y).sum()], float)
    tot += c
    per.append(metrics(*c))
    rows.append([v] + [pct(x) for x in per[-1]])
rows.append(["Average"] + [pct(np.nanmean([m[i] for m in per])) for i in range(4)])
rows.append(["Mix"] + [pct(x) for x in metrics(*tot)])
s.append(table("<b>Table 3</b><br/>Results of malicious flow identification of LFTO attacks with different parameters.",
               ["Attack", "Accuracy", "Recall", "Precision", "F1 Score"], rows, [0.2, 0.2, 0.2, 0.2, 0.2],
               "Per flow entry, FEVER's federated detector only. A4 and E9P are left to the volume block."))

# ---- Table 4
e = pd.read_csv("results/e11_detect/table_main.csv")
e = e[e.op == "fpr0.1"]
fev = "results/e11_detect/table_fever.csv"
lab = [("ftop", "FTOP"), ("ftmaster", "FTMaster"), ("flora", "FloRa"), ("dms-btt", "DMS-BTT")]
if os.path.exists(fev):
    e = pd.concat([e, pd.read_csv(fev)])
    lab.append(("fever", "FEVER"))
rows = []
for k, name in lab:
    r = {x: e[(e.detector == k) & (e.exposure == x)].iloc[0] for x in ("seen-local", "seen-remote", "unseen-all")}
    rows.append([name] + [pct(r["seen-local"][c]) for c in ("accuracy", "recall", "precision", "f1")]
                + [pct(r["seen-remote"].f1), pct(r["unseen-all"].f1)])
s.append(table("<b>Table 4</b><br/>Comparing the outcomes of various classifiers to recognize harmful flows.",
               ["Classifier", "Accuracy", "Recall", "Precision", "F1 Score", "F1 (seen remotely)", "F1 (unseen)"],
               rows, [0.16, 0.13, 0.12, 0.13, 0.13, 0.17, 0.16],
               "All classifiers at a 0.1 % false-positive rate on the same data. Seen remotely: attacks seen only by "
               "another controller; unseen: an attack no controller was trained on."))


# ---- Table 5
def t5rows(sel):
    out = []
    for d in DEFS + (["rdefender"] if RD is not None else []):
        if d == "rdefender":
            g = RD[(RD.defense == d) & RD.variant.isin(sel)]
            out.append([NAME[d], "Control", pct(g.attack_share_avg_pct_s11.mean()), "-", "-", "-", "-", "-"])
            continue
        g = runs[(runs.defense == d) & runs.variant.isin(sel)]
        fo = pd.to_numeric(g.first_overflow_s, errors="coerce").dropna() - T_ATT
        out.append([NAME[d], "None" if d == "none" else "Control", pct(g.pa_avg.mean()), pct(g.pa_max.mean()),
                    pct(g.usage_avg.mean()), f"{fo.min():.0f}" if len(fo) else "-",
                    f"{g.packet_in.mean():,.0f}", f"{g.table_full.mean():,.0f}"])
    return out


H5 = ["Method", "Deploy plane", "Average Pa", "Max Pa", "Average flow table usage", "Earliest overflow time(s)",
      "Packet-in message", "Table-full message"]
W5 = [0.13, 0.11, 0.11, 0.11, 0.14, 0.14, 0.13, 0.13]
s.append(table("<b>Table 5</b><br/>Comparative experiment results.", H5, t5rows(ATT), W5,
               "Mean per run over attacks A2, A4 and E9P; earliest overflow time is counted from the start of the "
               "attack (-: the table never overflowed)."))
for i, v in enumerate(ATT):
    s.append(table(f"<b>Table {5}{'abc'[i]}</b><br/>Comparative experiment results under {v}.", H5, t5rows([v]), W5))

# ---- Table 6
rows = []
for d in DEFS:
    g = runs[(runs.defense == d) & runs.variant.isin(ATT)]
    p = pre[(pre.defense == d) & pre.variant.isin(ATT)]
    rows.append([NAME[d], pct(g.harm.mean()), pct(g.pin_lost.mean(), 1), pct(g.probe_ok.mean(), 1),
                 f"{g.decision_ms_median.mean():.0f}", f"{int(p.hosts_blocked_attack.sum())}/30"])
s.append(table("<b>Table 6</b><br/>Impact on benign users.",
               ["Method", "Benign flows harmed", "Lost first packets", "New connections succeeding",
                "Decision time(ms)", "Attackers blocked"],
               rows, [0.16, 0.17, 0.16, 0.19, 0.16, 0.16]))

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm,
                        bottomMargin=20 * mm, title="FEVER results", author="asifahmedutsa")
doc.build(s)
print("wrote", OUT)
