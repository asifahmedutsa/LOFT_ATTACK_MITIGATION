"""Builds the comparison tables of FEVER against the published methods, and the ablation table,
from the testbed runs (~/loft-runs/v5_T1B_*) and the E11 benchmark. Every method is taken on the
seeds all of them share (rDefender and FEVER-without-ML ran on 4140-4142).

    PYTHONPATH=. ~/.venvs/loft/bin/python docs/build_comparison.py
Writes docs/fever_comparison.pdf and one image per table, docs/fever_table_<name>.png.
"""
import csv
import os
import re

import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

R = os.path.expanduser("~/loft-runs")
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
CAP = ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, spaceBefore=12, spaceAfter=4)
CELL = ParagraphStyle("x", fontName="LS", fontSize=9, leading=11, alignment=1)
CELL_L = ParagraphStyle("xl", parent=CELL, alignment=0)
HEAD = ParagraphStyle("hd", parent=CELL, fontSize=8.4, leading=10)
W = A4[0] - 44 * mm
ATT = ["A2", "A4", "E9P"]
T_ATT = 50.0


def summary(path):
    d = {}
    for line in open(path):
        m = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if not m:
            continue
        try:
            d[m[1]] = float(m[2])
        except ValueError:
            d[m[1]] = m[2]
    d.setdefault("hosts_blocked_attack", 0.0)
    d.setdefault("hosts_blocked_benign", 0.0)
    return d


def run(v, dfn, s):
    p = f"{R}/v5_T1B_{v}_{dfn}_s{s}"
    sm = summary(f"{p}/summary.txt")
    dec = [float(r["decision_ms"]) for r in csv.DictReader(open(f"{p}/switch_T1B_s11.csv")) if float(r["t"]) >= T_ATT]
    mem = [float(f[-3]) / 1024 for f in (ln.split() for ln in open(f"{p}/mem_pidstat.txt"))
           if len(f) > 3 and f[-1] == "python3.8" and f[0][0].isdigit()]
    return dict(variant=v, defense=dfn, seed=s, harm=sm["benign_harmed_pct"], share=sm["attack_share_avg_pct_s11"],
                lost=sm["benign_packet_in_lost_pct"], probe=sm["probe_post_success_pct"],
                att_blocked=sm["hosts_blocked_attack"], ben_blocked=sm["hosts_blocked_benign"],
                first_block=pd.to_numeric(sm.get("first_attack_block_s"), errors="coerce"),
                dec=float(np.median(dec)) if dec else np.nan, mem=max(mem) if mem else np.nan)


DEFS = ["none", "ftmaster", "dms-btt", "rdefender", "ensguard-v4lite", "ensguard-v5-noml", "ensguard-v5"]
NAME = {"none": "No defense", "ftmaster": "FTMaster", "dms-btt": "DMS-BTT", "rdefender": "rDefender",
        "ensguard-v4lite": "FEVER without volume block", "ensguard-v5-noml": "FEVER without ML",
        "ensguard-v5": "FEVER"}
SEEDS = [s for s in range(4140, 4145)
         if all(os.path.exists(f"{R}/v5_T1B_{v}_{d}_s{s}/summary.txt") for v in ATT + ["benign"] for d in DEFS)]
df = pd.DataFrame([run(v, d, s) for v in ATT + ["benign"] for d in DEFS for s in SEEDS])
os.makedirs("results/fever_comparison", exist_ok=True)
df.to_csv("results/fever_comparison/runs.csv", index=False)
A = df[df.variant.isin(ATT)]
B = df[df.variant == "benign"]
mem0 = A[A.defense == "none"].mem.mean()


def fmt(x, d=2):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def make(caption, head, rows, widths, best=None, head2=None, spans=()):
    """rows: list of lists of strings; best: {col: 'min'|'max'} marks the best value in bold."""
    body = [list(r) for r in rows]
    if best:
        for c, how in best.items():
            vals = [float(re.sub(r"[^0-9.+-]", "", r[c]) or "nan") if r[c] not in ("-", "") else np.nan for r in body]
            if np.all(np.isnan(vals)):
                continue
            tgt = np.nanmin(vals) if how == "min" else np.nanmax(vals)
            for r, val in zip(body, vals):
                if not np.isnan(val) and abs(val - tgt) < 1e-9:
                    r[c] = f"<b>{r[c]}</b>"
    hdr = [[Paragraph(f"<b>{h}</b>" if h else "", HEAD) for h in head]]
    if head2:
        hdr.append([Paragraph(f"<b>{h}</b>" if h else "", HEAD) for h in head2])
    data = hdr + [[Paragraph(r[0], CELL_L)] + [Paragraph(x, CELL) for x in r[1:]] for r in body]
    t = Table(data, colWidths=[w * W for w in widths])
    nh = len(hdr)
    st = [("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, nh - 1), (-1, nh - 1), 0.5, colors.black),
          ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    for (c0, c1) in spans:
        st += [("SPAN", (c0, 0), (c1, 0)), ("LINEBELOW", (c0, 0), (c1, 0), 0.4, colors.black)]
    if head2:
        for c in range(len(head)):
            if head2[c] == "" and not any(c0 <= c <= c1 for c0, c1 in spans):
                st.append(("SPAN", (c, 0), (c, 1)))
    t.setStyle(TableStyle(st))
    return KeepTogether([Paragraph(caption, CAP), t, Spacer(1, 10)])


tables = {}
# ---- Table 1: overall
pub = ["none", "ftmaster", "dms-btt", "rdefender", "ensguard-v5"]
rows = []
for d in pub:
    a, b = A[A.defense == d], B[B.defense == d]
    rows.append([NAME[d], fmt(a.harm.mean()), fmt(a.share.mean(), 1), f"{int(a.att_blocked.sum())} / {2 * len(a)}",
                 f"{int(a.ben_blocked.sum() + b.ben_blocked.sum())}", fmt(a.probe.mean(), 1), fmt(a.lost.mean(), 1),
                 fmt(a.dec.mean(), 0), fmt(a.mem.mean() - mem0, 0) if d != "none" else "-"])
tables["overall"] = make(
    "<b>Table 1</b><br/>Comparison with published methods under LFTO attacks.",
    ["Method", "Normal flows harmed (%)", "Attacker's share of the table (%)", "Attackers blocked",
     "Innocent hosts blocked", "New connections succeeding (%)", "First packets lost (%)",
     "Decision time (ms)", "Extra memory (MB)"],
    rows, [0.13, 0.105, 0.115, 0.1, 0.1, 0.125, 0.1, 0.1, 0.1],
    best={1: "min", 2: "min", 5: "max", 6: "min", 7: "min"})

# ---- Table 2: per attack
rows = []
for d in pub:
    r = [NAME[d]]
    for key, dd in (("harm", 2), ("share", 1)):
        for v in ATT:
            r.append(fmt(A[(A.defense == d) & (A.variant == v)][key].mean(), dd))
    rows.append(r)
tables["per_attack"] = make(
    "<b>Table 2</b><br/>Results under each attack.",
    ["Method", "Normal flows harmed (%)", "", "", "Attacker's share of the flow table (%)", "", ""],
    rows, [0.22, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13],
    best={i: "min" for i in range(1, 7)}, head2=["", "A2", "A4", "E9P", "A2", "A4", "E9P"], spans=[(1, 3), (4, 6)])

# ---- Table 3: detection metrics (E11)
e = pd.read_csv("results/e11_detect/table_main.csv")
e = e[e.op == "fpr0.1"]
if os.path.exists("results/e11_detect/table_fever.csv"):
    e = pd.concat([e, pd.read_csv("results/e11_detect/table_fever.csv")])
rows = []
for k, name in (("ftop", "FTOP"), ("ftmaster", "FTMaster"), ("flora", "FloRa"), ("dms-btt", "DMS-BTT"), ("fever", "FEVER")):
    if not (e.detector == k).any():
        continue
    r = [name]
    for x in ("seen-local", "seen-remote", "unseen-all"):
        q = e[(e.detector == k) & (e.exposure == x)].iloc[0]
        r += [fmt(q.accuracy), fmt(q.precision), fmt(q.recall), fmt(q.f1)]
    rows.append(r)
tables["detection"] = make(
    "<b>Table 3</b><br/>Accuracy, precision, recall and F1 score (%) of the detectors.",
    ["Detector", "Attacks seen in training", "", "", "", "Attacks seen only by another controller", "", "", "",
     "New attack seen by no controller", "", "", ""],
    rows, [0.12] + [0.0733] * 12, best={i: "max" for i in range(1, 13)},
    head2=[""] + ["Acc.", "Prec.", "Rec.", "F1"] * 3, spans=[(1, 4), (5, 8), (9, 12)])

# ---- Table 4: ablation
abl = ["ensguard-v5", "ensguard-v4lite", "ensguard-v5-noml"]
rows = []
for d in abl:
    a = A[A.defense == d]
    r = [NAME[d]] + [fmt(a[a.variant == v].harm.mean()) for v in ATT] + [fmt(a.share.mean(), 1),
         f"{int(a.att_blocked.sum())} / {2 * len(a)}", fmt(a[a.variant == "A2"].first_block.mean(), 0),
         f"{int(a.ben_blocked.sum() + B[B.defense == d].ben_blocked.sum())}"]
    rows.append(r)
tables["ablation"] = make(
    "<b>Table 4</b><br/>Contribution of each part of FEVER.",
    ["Variant", "Normal flows harmed (%)", "", "", "Attacker's share of the flow table (%)", "Attackers blocked",
     "Time to block under A2 (s)", "Innocent hosts blocked"],
    rows, [0.24, 0.09, 0.09, 0.09, 0.13, 0.11, 0.13, 0.12],
    best={1: "min", 2: "min", 3: "min", 4: "min", 6: "min"},
    head2=["", "A2", "A4", "E9P", "", "", "", ""], spans=[(1, 3)])

doc = SimpleDocTemplate("docs/fever_comparison.pdf", pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                        topMargin=20 * mm, bottomMargin=20 * mm, title="FEVER comparison", author="asifahmedutsa")
doc.build(list(tables.values()))

# one image per table
tmp = "results/fever_comparison/_tmp"
os.makedirs(tmp, exist_ok=True)
for name, flow in tables.items():
    SimpleDocTemplate(f"{tmp}/{name}.pdf", pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm,
                      bottomMargin=20 * mm).build([flow])
    os.system(f"pdftoppm -r 250 -png -f 1 -l 1 {tmp}/{name}.pdf {tmp}/{name}")
    im = Image.open(f"{tmp}/{name}-1.png").convert("RGB")
    bb = ImageOps.invert(im.convert("L")).point(lambda v: 255 if v > 20 else 0).getbbox()
    im.crop((bb[0] - 30, bb[1] - 30, bb[2] + 30, bb[3] + 30)).save(f"docs/fever_table_{name}.png", dpi=(250, 250))
print("seeds", SEEDS, "; wrote docs/fever_comparison.pdf and docs/fever_table_*.png")
