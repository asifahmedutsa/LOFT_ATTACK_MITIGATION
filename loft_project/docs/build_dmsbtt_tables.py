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
    cap=ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, spaceBefore=10, spaceAfter=4),
    cell=ParagraphStyle("x", fontName="LS", fontSize=9, leading=11),
    note=ParagraphStyle("n", fontName="LS", fontSize=8.8, leading=11.5, textColor=colors.HexColor("#333333"), spaceBefore=4),
    p=ParagraphStyle("p", fontName="LS", fontSize=10, leading=13.5, spaceAfter=6))
W = A4[0] - 40 * mm


def table(caption, head, rows, widths, note=None, bold_rows=()):
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
NAME = {"none": "None", "ensguard": "EnsGuard v3", "ensguard-v4lite": "FEVER without volume (v4-lite)",
        "ensguard-v5": "FEVER", "dms-btt": "DMS-BTT", "ftmaster": "FTMaster"}
DEFS = ["none", "ensguard", "ensguard-v4lite", "dms-btt", "ftmaster", "ensguard-v5"]
T_ATT = 50.0

s = [Paragraph("FEVER: the result tables of DMS-BTT, from our data", S["title"]),
     Paragraph("Tables 1-5 follow DMS-BTT (Tang et al., ESWA 2025), Tables 2-6, one for one; Table 6 adds the "
               "harm to users that DMS-BTT does not report. Testbed: Mininet + Open vSwitch + Ryu, tree topology "
               "(core switch s11), table 3,500 entries, idle timeout 10 s, 300 s runs, attack from 50 s, benign traffic "
               "the last 60 % of bigFlows (T1B), which no model or threshold was trained on. 7 November 2026.", S["sub"])]

# ---- Table 1 (DMS-BTT Table 2)
rows = []
for v in ATT:
    a = attack_variant(v)
    fo = pd.to_numeric(runs[(runs.defense == "none") & (runs.variant == v)].first_overflow_s, errors="coerce")
    pk = f"{a.pkts_per_refresh[0]}" if a.pkts_per_refresh[0] == a.pkts_per_refresh[1] else f"{a.pkts_per_refresh[0]}-{a.pkts_per_refresh[1]}"
    rows.append([v, f"[{a.t1_range[0]:g}, {a.t1_range[1]:g}]", a.step, a.max_flows, pk,
                 "64 B" if a.size_mode == "fixed" else "benign-like", {"host": "own address", "pool": "address pool"}[a.src_mode],
                 f"{(fo - T_ATT).mean():.1f}"])
s.append(table("<b>Table 1.</b> LFTO attack parameter setting (cf. DMS-BTT Table 2).",
               ["Attack", "T1 (s)", "S (pkt/T)", "M (pkt)", "Packets per refresh", "Packet size", "Source", "T2 (s)"],
               rows, [0.08, 0.11, 0.1, 0.09, 0.14, 0.13, 0.15, 0.1],
               "T1: sending period; S: step (new flows per burst); M: maximum attack flows per attacker (two attackers); "
               "T2: mean time from the start of the attack to the first overflow of the core table with no defense "
               "(5 seeds). A2 is DMS-BTT's parameter set 2. A4 refreshes with benign-like packets from an address pool "
               "(mimicry); E9P is the defense-aware best response found by an offline search."))

# ---- Table 2 (DMS-BTT Table 3)
f = pre[pre.defense == "ensguard-v5"]
rows = []
for v in ATT + ["benign"]:
    g = f[f.variant == v]
    det = int((g.hosts_blocked_attack >= 2).sum())
    fb = pd.to_numeric(g.first_attack_block_s, errors="coerce")
    rows.append([v if v != "benign" else "no attack", f"{len(g)}",
                 f"{det} / {len(g)}" if v != "benign" else "-",
                 f"{int(g.hosts_blocked_attack.sum())} / {2 * len(g)}" if v != "benign" else "-",
                 f"{fb.mean():.1f}" if v != "benign" else "-",
                 f"{int((g.hosts_blocked_benign > 0).sum())} / {len(g)}"])
s.append(table("<b>Table 2.</b> Attack detection by FEVER on the testbed, per run (cf. DMS-BTT Table 3).",
               ["Traffic", "Runs", "Attack detected (both attackers blocked)", "Attackers blocked",
                "Time to first block (s after attack start)", "Runs with a benign host blocked"],
               rows, [0.12, 0.08, 0.22, 0.15, 0.22, 0.21],
               "DMS-BTT classifies the network state (normal / attack / overflow) with CatBoost on FN and APIT. FEVER "
               "uses the occupancy thresholds TH1 = 70 % and TH2 = 90 % instead and detects an attack by acting on its "
               "hosts, so its detection is reported per run. v5 campaign, seeds 4140-4144."))

# ---- Table 3 (DMS-BTT Table 4)
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


rows, tot = [], np.zeros(4)
per = []
for v in ATT:
    X = np.concatenate([rows_pk[(v, sd)][0] for sd in (2000, 2001, 2002)])
    y = np.concatenate([rows_pk[(v, sd)][1] for sd in (2000, 2001, 2002)]).astype(bool)
    p = model.predict_proba(X) >= tau
    c = np.array([(p & y).sum(), (p & ~y).sum(), (~p & y).sum(), (~p & ~y).sum()], float)
    tot += c
    m = metrics(*c)
    per.append(m)
    rows.append([v] + [pct(x) for x in m])
rows.append(["Average"] + [pct(np.nanmean([m[i] for m in per])) for i in range(4)])
rows.append(["Mix"] + [pct(x) for x in metrics(*tot)])
hb = pre[(pre.defense == "ensguard-v5") & (pre.variant != "benign")]
tp_h, fp_h = int(hb.hosts_blocked_attack.sum()), int(pre[pre.defense == "ensguard-v5"].hosts_blocked_benign.sum())
fn_h = 2 * len(hb) - tp_h
tn_h = 4 * len(pre[pre.defense == "ensguard-v5"]) - fp_h
rows.append(["Host level, testbed"] + [pct(x) for x in metrics(tp_h, fp_h, fn_h, tn_h)])
s.append(table("<b>Table 3.</b> Results of malicious flow identification of LFTO attacks with different parameters "
               "(cf. DMS-BTT Table 4).",
               ["Attack", "Accuracy", "Recall", "Precision", "F1 Score"], rows, [0.28, 0.18, 0.18, 0.18, 0.18],
               f"Rows A2-Mix: FEVER's detector alone (the three shared CatBoost models, τ = {tau:.3f}), per flow entry, on "
               "simulator T1B traffic at the testbed's rate (development seeds 2000-2002; 5 % of entries per poll). "
               "It identifies A2 almost perfectly but not A4 or E9P, whose entries look benign; this is why FEVER adds "
               "the volume block. Last row: FEVER as deployed, per host on the testbed (v5 campaign): "
               f"{tp_h} of {tp_h + fn_h} attacker hosts blocked, {fp_h} of {fp_h + tn_h} benign hosts blocked.",
               bold_rows=(len(rows) - 1,)))

# ---- Table 4 (DMS-BTT Table 5)
e = pd.read_csv("results/e11_detect/table_main.csv")
e = e[e.op == "fpr0.1"]
lab = [("ftop", "FTOP (Random Forest)"), ("ftmaster", "FTMaster (XGBoost)"), ("flora", "FloRa (CatBoost)"),
       ("dms-btt", "DMS-BTT (CatBoost)"), ("fl-dualguard", "FL-DualGuard (MLP, federated)"),
       ("ensguard", "EnsGuard (RF + CatBoost, federated)")]
rows = []
for k, name in lab:
    r = [e[(e.detector == k) & (e.exposure == x)].iloc[0] for x in ("seen-local", "seen-remote", "unseen-all")]
    rows.append([name] + [pct(r[0][c]) for c in ("accuracy", "recall", "precision", "f1")]
                + [pct(r[1].recall), pct(r[2].recall), pct(r[2].f1)])
s.append(table("<b>Table 4.</b> Comparing the outcomes of various classifiers to recognize harmful flows "
               "(cf. DMS-BTT Table 5).",
               ["Detector", "Accuracy", "Recall", "Precision", "F1", "Recall, seen only by another controller",
                "Recall, seen by none", "F1, seen by none"],
               rows, [0.22, 0.11, 0.1, 0.1, 0.1, 0.13, 0.11, 0.13],
               "E11 benchmark (simulator domains D1-D3): every detector trained and scored on identical rows, each at a "
               "0.1 % benign false-positive rate. Columns 2-5: attacks the controller trained on (DMS-BTT's setting). "
               "FEVER's detector is the CatBoost half of EnsGuard; on validation it matches the ensemble on attacks not "
               "trained on (92.5 % against 92.2 % recall, results/v4lite/detsel.md).",
               bold_rows=(len(rows) - 1,)))

# ---- Table 5 (DMS-BTT Table 6)
a = runs[runs.variant.isin(ATT)].copy()
a["fo"] = pd.to_numeric(a.first_overflow_s, errors="coerce") - T_ATT
rows = []
for d in DEFS:
    g = a[a.defense == d]
    fo = g.fo.dropna()
    rows.append([NAME[d], pct(g.pa_avg.mean()), pct(g.pa_max.mean()), pct(g.usage_avg.mean()),
                 f"{fo.min():.0f} ({len(fo)}/{len(g)})" if len(fo) else f"never (0/{len(g)})",
                 f"{g.packet_in.mean():,.0f}", f"{g.table_full.mean():,.0f}"])
s.append(table("<b>Table 5.</b> Comparative experiment results (cf. DMS-BTT Table 6).",
               ["Method", "Average Pa", "Max Pa", "Average flow table usage", "Earliest overflow time (s)",
                "Packet-In messages", "Table-Full messages"],
               rows, [0.26, 0.11, 0.1, 0.13, 0.15, 0.12, 0.13],
               "Mean over A2, A4 and E9P x 5 seeds (15 runs per method), core switch s11. Earliest overflow: seconds from "
               "the start of the attack to the table's first overflow, the earliest over the runs, with the number of "
               "runs that overflowed at all. Packet-In and Table-Full: mean per 300 s run. All methods run on the "
               "controller. DMS-BTT and FTMaster are trained on T1A. EVICT, SIFT, TableGuard and FTOP ran only in "
               "the earlier campaign (other traffic) and are not listed.",
               bold_rows=(len(rows) - 1,)))
for v in ATT:
    g0 = a[a.variant == v]
    rows = []
    for d in DEFS:
        g = g0[g0.defense == d]
        fo = g.fo.dropna()
        rows.append([NAME[d], pct(g.pa_avg.mean()), pct(g.pa_max.mean()), pct(g.usage_avg.mean()),
                     f"{fo.min():.0f} ({len(fo)}/{len(g)})" if len(fo) else f"never (0/{len(g)})",
                     f"{g.packet_in.mean():,.0f}", f"{g.table_full.mean():,.0f}"])
    s.append(table(f"<b>Table 5{'abc'[ATT.index(v)]}.</b> As Table 5, attack {v} only (5 seeds).",
                   ["Method", "Average Pa", "Max Pa", "Average flow table usage", "Earliest overflow time (s)",
                    "Packet-In messages", "Table-Full messages"],
                   rows, [0.26, 0.11, 0.1, 0.13, 0.15, 0.12, 0.13], bold_rows=(len(rows) - 1,)))

# ---- Table 6 (ours)
rows = []
for d in DEFS:
    g = a[a.defense == d]
    p = pre[(pre.defense == d) & pre.variant.isin(ATT)]
    rows.append([NAME[d], pct(g.harm.mean()), pct(g.pin_lost.mean(), 1), pct(g.probe_ok.mean(), 1),
                 f"{g.decision_ms_median.mean():.0f}", f"{int(p.hosts_blocked_attack.sum())} / 30",
                 f"{int(pre[pre.defense == d].hosts_blocked_benign.sum())}"])
s.append(table("<b>Table 6.</b> Harm to users and actions taken (not reported by DMS-BTT).",
               ["Method", "Benign flows harmed", "Lost first packets", "New connections succeeding",
                "Decision time per poll (ms, median)", "Attackers blocked", "Benign hosts blocked (20 runs)"],
               rows, [0.26, 0.12, 0.11, 0.13, 0.14, 0.11, 0.13],
               "Same 15 attack runs per method (benign hosts blocked: also the 5 no-attack runs). Benign flows harmed: "
               "refused, dropped by a block, or first packet lost. New connections: a probe opens one TCP connection "
               "every 0.5 s after the attack starts. Preregistered tests on these runs: "
               "results/testbed_prereg_v5/report.md.",
               bold_rows=(len(rows) - 1,)))

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                        bottomMargin=18 * mm, title="FEVER: DMS-BTT tables", author="asifahmedutsa")
doc.build(s)
print("wrote", OUT)
