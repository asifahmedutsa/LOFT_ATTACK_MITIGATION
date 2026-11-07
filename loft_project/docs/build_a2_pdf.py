"""Builds docs/fever_results_A2.pdf: the testbed results under the standard LFTO attack A2 only,
FEVER against no defense, FTMaster and DMS-BTT (v5 campaign, T1B, seeds 4140-4144). Draws two A2
figures of its own (results/paper_figs/v5pub/fig24_a2_comparison, fig25_a2_share_over_time) and
reuses the A2 versions of the other figures.

    PYTHONPATH=. ~/.venvs/loft/bin/python docs/build_a2_pdf.py
"""
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

sys.path.insert(0, "testbed")
R = os.path.expanduser("~/loft-runs")
V, P = "results/paper_figs/v5", "results/paper_figs/v5pub"
DEFS = ["none", "ftmaster", "dms-btt", "ensguard-v5"]
NAME = {"none": "None", "ftmaster": "FTMaster", "dms-btt": "DMS-BTT", "ensguard-v5": "FEVER"}
COL = {"none": "#9a9993", "ftmaster": "#2a78d6", "dms-btt": "#1baf7a", "ensguard-v5": "#eb6834"}
SEEDS = [4140, 4141, 4142, 4143, 4144]
CAP, T_ATT = 3500, 50.0
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.bbox": "tight", "font.family": "DejaVu Sans"})

runs = pd.read_csv(f"{P}/testbed_runs.csv")
a2 = runs[runs.variant == "A2"]
pre = pd.read_csv("results/testbed_prereg_v5/runs.csv")
pre2 = pre[pre.variant == "A2"]

# ---- fig24: A2 comparison panels
panels = [("harm", "Benign flows harmed (%)"), ("pa_avg", "Average attack share (%)"),
          ("pa_max", "Maximum attack share (%)"), ("usage_avg", "Average flow table usage (%)"),
          ("overflow_s", "Seconds at the table limit"), ("table_full", "Table-Full messages"),
          ("pin_lost", "Benign first packets lost (%)"), ("probe_ok", "New connections succeeding (%)")]
fig, axs = plt.subplots(2, 4, figsize=(13, 6))
x = np.arange(len(DEFS))
for ax, (k, t) in zip(axs.flat, panels):
    g = a2.groupby("defense")[k]
    m, lo, hi = g.mean().reindex(DEFS), g.min().reindex(DEFS), g.max().reindex(DEFS)
    ax.bar(x, m, color=[COL[d] for d in DEFS], width=0.68, edgecolor="white")
    ax.errorbar(x, m, yerr=[m - lo, hi - m], fmt="none", ecolor="#52514e", elinewidth=0.8, capsize=2)
    for xi, mi, hv in zip(x, m, hi):
        ax.annotate(f"{mi:.2f}" if mi < 10 else f"{mi:.0f}", (xi, hv), xytext=(0, 2), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x, [NAME[d] for d in DEFS], rotation=30, ha="right")
    ax.set_title(t, fontsize=9.5)
    ax.grid(axis="y", color="#e4e3df", lw=0.6)
    ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(f"{P}/fig24_a2_comparison.png", dpi=200)
fig.savefig(f"{P}/fig24_a2_comparison.pdf")
plt.close(fig)

# ---- fig25: attack share over time under A2
ATT = {"00:00:00:00:01:05", "00:00:00:00:01:06"}


def share(d, s):
    p = f"{R}/v5_T1B_A2_{d}_s{s}"
    t = np.array([float(r["t"]) for r in csv.DictReader(open(f"{p}/switch_T1B_s11.csv"))])
    att = {}
    for r in csv.DictReader(open(f"{p}/switch_T1B_s11_macs.csv")):
        if r["mac"] in ATT:
            att[float(r["t"])] = att.get(float(r["t"]), 0) + int(r["entries"])
    y = np.array([att.get(v, 0) for v in t], float)
    return np.interp(np.arange(0, 301), t, 100 * y / CAP, left=np.nan, right=np.nan)


fig, ax = plt.subplots(figsize=(7.5, 3.4))
for d in DEFS:
    y = np.nanmedian(np.vstack([share(d, s) for s in SEEDS]), axis=0)
    ax.plot(np.arange(0, 301), y, color=COL[d], lw=1.8, ls="--" if d == "none" else "-", label=NAME[d])
ax.axvline(T_ATT, color="#9a9993", lw=0.8, ls=":")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Attack-rule share of the flow table (%)")
ax.set_xlim(0, 300)
ax.set_ylim(0, 100)
ax.legend(fontsize=8, frameon=False)
ax.grid(color="#e4e3df", lw=0.6)
fig.savefig(f"{P}/fig25_a2_share_over_time.png", dpi=200)
fig.savefig(f"{P}/fig25_a2_share_over_time.pdf")
plt.close(fig)

# ---- PDF
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
TITLE = ParagraphStyle("t", fontName="LS-B", fontSize=15, leading=19, spaceAfter=10)
CAPS = ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, alignment=1, spaceBefore=4, spaceAfter=16)
TCAP = ParagraphStyle("tc", fontName="LS", fontSize=9.5, leading=12, spaceAfter=4)
CELL = ParagraphStyle("x", fontName="LS", fontSize=9, leading=11, alignment=1)
CELL_L = ParagraphStyle("xl", parent=CELL, alignment=0)
W, H = A4[0] - 40 * mm, A4[1] - 50 * mm


def image(path, maxh=H * 0.6):
    iw, ih = ImageReader(path).getSize()
    sc = min(W / iw, maxh / ih)
    return Image(path, width=iw * sc, height=ih * sc)


rows = []
for d in DEFS:
    g, q = a2[a2.defense == d], pre2[pre2.defense == d]
    rows.append([NAME[d], f"{g.harm.mean():.2f}", f"{g.pa_avg.mean():.1f}", f"{g.pa_max.mean():.1f}",
                 f"{g.usage_avg.mean():.1f}", f"{g.pin_lost.mean():.1f}", f"{g.probe_ok.mean():.1f}",
                 f"{int(q.hosts_blocked_attack.sum())} / {2 * len(q)}", f"{g.decision_ms_median.mean():.0f}"])
head = ["Method", "Benign flows harmed (%)", "Average attack share (%)", "Maximum attack share (%)",
        "Average flow table usage (%)", "First packets lost (%)", "New connections succeeding (%)",
        "Attackers blocked", "Decision time (ms)"]
for c in (1, 2, 3, 4, 5, 8):                     # best value (lowest) in bold
    vals = [float(r[c]) for r in rows[1:]]
    for r in rows[1:]:
        if float(r[c]) == min(vals):
            r[c] = f"<b>{r[c]}</b>"
vals = [float(r[6]) for r in rows[1:]]
for r in rows[1:]:
    if float(r[6]) == max(vals):
        r[6] = f"<b>{r[6]}</b>"
data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle("h", parent=CELL, fontSize=8.4, leading=10)) for h in head]]
data += [[Paragraph(r[0], CELL_L)] + [Paragraph(v, CELL) for v in r[1:]] for r in rows]
t = Table(data, colWidths=[w * W for w in (0.12, 0.11, 0.11, 0.11, 0.12, 0.1, 0.12, 0.11, 0.1)])
t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                       ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                       ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))

figs = [(f"{P}/fig24_a2_comparison.png", "Comparison of the defenses under A2 (five runs each; bar: mean, whisker: range)."),
        (f"{P}/fig01_rules_over_time_A2.png", "Benign and attack rules in the flow table over time under A2."),
        (f"{P}/fig25_a2_share_over_time.png", "Attack-rule share of the flow table over time under A2 (median of five runs)."),
        (f"{V}/fig20_malicious_share_A2.png", "Percentage of malicious flows in the flow table with FEVER under A2."),
        (f"{P}/fig16_a2_block_expiry.png", "Flow-table entries over time under A2."),
        (f"{V}/fig17_states_A2.png", "Distribution of FN and of the entries held per host before and after the A2 attack."),
        (f"{V}/fig19_messages_A2.png", "The quantity of Packet-In and Table-Full messages under A2."),
        (f"{V}/fig21_cpu_A2.png", "CPU usage of the controller under A2."),
        (f"{V}/fig22_overhead_A2.png", "System overhead of deploying FEVER under A2.")]
story = [Paragraph("FEVER: results under the A2 attack", TITLE),
         KeepTogether([Paragraph("<b>Table 1</b><br/>Comparison with published methods under A2.", TCAP), t, Spacer(1, 16)])]
for i, (path, cap) in enumerate(figs, 1):
    story.append(KeepTogether([image(path), Paragraph(f"<b>Fig. {i}.</b> {cap}", CAPS)]))
SimpleDocTemplate("docs/fever_results_A2.pdf", pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                  topMargin=20 * mm, bottomMargin=20 * mm, title="FEVER A2 results", author="asifahmedutsa").build(story)
print("wrote docs/fever_results_A2.pdf")
