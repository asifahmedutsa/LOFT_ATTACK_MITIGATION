"""Builds docs/fever_results_tables.pdf: every result table of FEVER in one plain PDF, computed from the
result files (E11 detection benchmark; testbed runs of the v5 campaign seeds with FEVER v6; the
rDefender and ablation runs on seeds 4140-4142; controller overhead).

    PYTHONPATH=. ~/.venvs/loft/bin/python docs/build_results_tables.py
"""
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
TITLE = ParagraphStyle("t", fontName="LS-B", fontSize=15, leading=19, spaceAfter=12)
CAP = ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, spaceAfter=4)
NOTE = ParagraphStyle("n", fontName="LS", fontSize=8.5, leading=10.5, spaceBefore=3)
CELL = ParagraphStyle("x", fontName="LS", fontSize=8.8, leading=10.8, alignment=1)
CELL_L = ParagraphStyle("xl", parent=CELL, alignment=0)
HEAD = ParagraphStyle("h", parent=CELL, fontName="LS-B")
W = A4[0] - 40 * mm
ATT = ["A2", "A4", "E9P"]
n_tab = [0]


def table(cap, head, rows, widths, best=None, head2=None, spans=(), note=None):
    """rows: lists of strings; best: {column: 'min'|'max'} marks the best method row in bold
    (rows whose first cell is 'None' are left out of the comparison)."""
    n_tab[0] += 1
    body = [list(r) for r in rows]
    for c, how in (best or {}).items():
        vals = [float(r[c].split()[0].replace("%", "")) if r[0] != "None" and r[c] not in ("-", "") else np.nan
                for r in body]
        if np.all(np.isnan(vals)):
            continue
        tgt = np.nanmin(vals) if how == "min" else np.nanmax(vals)
        for r, v in zip(body, vals):
            if not np.isnan(v) and abs(v - tgt) < 1e-9:
                r[c] = f"<b>{r[c]}</b>"
    hdr = [[Paragraph(h, HEAD) for h in head]]
    if head2:
        hdr.append([Paragraph(h, HEAD) for h in head2])
    data = hdr + [[Paragraph(r[0], CELL_L)] + [Paragraph(x, CELL) for x in r[1:]] for r in body]
    t = Table(data, colWidths=[w * W for w in widths])
    nh = len(hdr)
    st = [("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, nh - 1), (-1, nh - 1), 0.5, colors.black),
          ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    for c0, c1 in spans:
        st += [("SPAN", (c0, 0), (c1, 0)), ("LINEBELOW", (c0, 0), (c1, 0), 0.4, colors.black)]
    if head2:
        for c in range(len(head)):
            if head2[c] == "" and not any(c0 <= c <= c1 for c0, c1 in spans):
                st.append(("SPAN", (c, 0), (c, 1)))
    t.setStyle(TableStyle(st))
    parts = [Paragraph(f"<b>Table {n_tab[0]}</b><br/>{cap}", CAP), t]
    if note:
        parts.append(Paragraph(note, NOTE))
    return KeepTogether(parts + [Spacer(1, 14)])


def f(x, d=2, pct=False):
    """Rounded half up (11.85 -> 11.9, as in the other documents)."""
    from decimal import ROUND_HALF_UP, Decimal
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    v = Decimal(repr(round(float(x), 6))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return f"{v}" + (" %" if pct else "")


s = [Paragraph("FEVER: results tables", TITLE)]

# ---- 1. detection (E11)
e = pd.read_csv("results/e11_detect/table_main.csv")
e = pd.concat([e[e.op == "fpr0.1"], pd.read_csv("results/e11_detect/table_fever.csv")])
rows = []
for k, name in (("ftop", "FTOP"), ("ftmaster", "FTMaster"), ("flora", "FloRa"), ("dms-btt", "DMS-BTT"), ("fever", "FEVER")):
    r = [name]
    for x in ("seen-local", "seen-remote", "unseen-all"):
        q = e[(e.detector == k) & (e.exposure == x)].iloc[0]
        r += [f(q.accuracy), f(q.precision), f(q.recall), f(q.f1)]
    rows.append(r)
s.append(table("Accuracy, precision, recall and F1 score (%) of the detectors at a 0.1 % false-alarm rate.",
               ["Detector", "Attacks seen in training", "", "", "", "Attacks seen only by another controller", "", "", "",
                "New attack seen by no controller", "", "", ""],
               rows, [0.12] + [0.0733] * 12, best={i: "max" for i in range(1, 13)},
               head2=[""] + ["Acc.", "Prec.", "Rec.", "F1"] * 3, spans=[(1, 4), (5, 8), (9, 12)],
               note="Same rows for every detector (simulator domains D1-D3)."))

# ---- testbed, seeds 4140-4144
r = pd.read_csv("results/v6/runs.csv")
A, B = r[r.variant.isin(ATT)], r[r.variant == "benign"]
DEFS = [("none", "None"), ("ftmaster", "FTMaster"), ("dms-btt", "DMS-BTT"), ("ensguard-v6", "FEVER")]


def m(df, d, k):
    return df[df.defense == d][k].mean()


rows = []
for d, name in DEFS:
    a = A[A.defense == d]
    rows.append([name, f(a.benign_harmed_pct.mean(), 2, True), f(a.attack_share_avg_pct_s11.mean(), 1, True),
                 f(a.attack_share_max_pct_s11.mean(), 1, True), f(a.benign_packet_in_lost_pct.mean(), 1, True),
                 f(a.probe_post_success_pct.mean(), 1, True),
                 f"{int(a.hosts_blocked_attack.sum())} / {2 * len(a)}",
                 f"{int(a.hosts_blocked_benign.sum() + B[B.defense == d].hosts_blocked_benign.sum())}"])
s.append(table("Comparison under LFTO attacks on the testbed (A2, A4 and E9P, five runs each).",
               ["Method", "Benign flows harmed", "Average attack share", "Maximum attack share", "First packets lost",
                "New connections succeeding", "Attackers blocked", "Innocent hosts blocked"],
               rows, [0.13, 0.12, 0.125, 0.125, 0.115, 0.135, 0.12, 0.13],
               best={1: "min", 2: "min", 3: "min", 4: "min", 5: "max"},
               note="Attack share: attack rules as a share of the core switch's table. FEVER with permanent blocking."))

rows = []
for d, name in DEFS:
    rr = [name]
    for k, dd in (("benign_harmed_pct", 2), ("attack_share_avg_pct_s11", 1)):
        rr += [f(A[(A.defense == d) & (A.variant == v)][k].mean(), dd, True) for v in ATT]
    rows.append(rr)
s.append(table("Results under each attack.",
               ["Method", "Benign flows harmed", "", "", "Average attack share", "", ""],
               rows, [0.22, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13], best={i: "min" for i in range(1, 7)},
               head2=["", "A2", "A4", "E9P", "A2", "A4", "E9P"], spans=[(1, 3), (4, 6)]))

rows = []
for d, name in DEFS:
    rr = [name]
    for k, dd in (("benign_packet_in_lost_pct", 1), ("probe_post_success_pct", 1)):
        rr += [f(A[(A.defense == d) & (A.variant == v)][k].mean(), dd, True) for v in ATT]
    rows.append(rr)
s.append(table("Service to benign users under each attack.",
               ["Method", "First packets lost", "", "", "New connections succeeding", "", ""],
               rows, [0.22, 0.13, 0.13, 0.13, 0.13, 0.13, 0.13],
               best={1: "min", 2: "min", 3: "min", 4: "max", 5: "max", 6: "max"},
               head2=["", "A2", "A4", "E9P", "A2", "A4", "E9P"], spans=[(1, 3), (4, 6)]))

# ---- seeds 4140-4142, with rDefender and the ablation
c = pd.read_csv("results/fever_comparison/runs.csv")
CA, CB = c[c.variant.isin(ATT)], c[c.variant == "benign"]
rows = []
for d, name in DEFS[:3] + [("rdefender", "rDefender"), ("ensguard-v6", "FEVER")]:
    a = CA[CA.defense == d]
    rows.append([name, f(a.harm.mean(), 2, True), f(a.share.mean(), 1, True), f(a.lost.mean(), 1, True),
                 f(a.probe.mean(), 1, True), f"{int(a.att_blocked.sum())} / {2 * len(a)}",
                 f"{int(a.ben_blocked.sum() + CB[CB.defense == d].ben_blocked.sum())}"])
s.append(table("Comparison including rDefender (A2, A4 and E9P, three runs each).",
               ["Method", "Benign flows harmed", "Average attack share", "First packets lost",
                "New connections succeeding", "Attackers blocked", "Innocent hosts blocked"],
               rows, [0.16, 0.14, 0.14, 0.14, 0.15, 0.13, 0.14],
               best={1: "min", 2: "min", 3: "min", 4: "max"}, note="Seeds 4140-4142, the runs rDefender has."))

# ---- overhead
o = pd.read_csv("results/paper_figs/v6/testbed_runs.csv")
OA, OB = o[o.variant != "benign"], o[o.variant == "benign"]
base_mem, base_idle = OA[OA.defense == "none"].mem_mb.mean(), OB[OB.defense == "none"].cpu_pct.mean()
rows = []
for d, name in DEFS:
    a, b = OA[OA.defense == d], OB[OB.defense == d]
    rows.append([name, f(b.cpu_pct.mean(), 1), f"{b.cpu_pct.mean() - base_idle:+.1f}" if d != "none" else "-",
                 f(a.cpu_pct.mean(), 1), f(a.mem_mb.mean(), 0),
                 f"{a.mem_mb.mean() - base_mem:+.0f}" if d != "none" else "-", f(a.decision_ms_median.mean(), 0)])
s.append(table("System overhead of each method on the testbed.",
               ["Method", "CPU usage (%)", "", "", "Memory (MB)", "", "Time per decision (ms)"],
               rows, [0.14, 0.12, 0.16, 0.13, 0.11, 0.16, 0.18],
               head2=["", "No attack", "Increase over no defense", "Under attack", "Peak",
                      "Increase over no defense", ""], spans=[(1, 3), (4, 5)]))

SimpleDocTemplate("docs/fever_results_tables.pdf", pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                  topMargin=20 * mm, bottomMargin=20 * mm, title="FEVER results tables",
                  author="asifahmedutsa").build(s)
print("wrote docs/fever_results_tables.pdf")
