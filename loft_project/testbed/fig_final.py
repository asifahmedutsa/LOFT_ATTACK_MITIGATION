"""Paper table and figures of the final testbed campaign, from results/testbed_prereg_final/runs.csv
(the 300 s runs counted by testbed/analyze_final.py, amendment 1 measures).

  table_main.tex / .pdf   harm, occupancy and probe success per attack, every method (mean over seeds)
  fig_t1b                 the same three measures on T1B, grouped bars per attack, mean and s.d.
  fig_uht                 the same on UHt (the three baselines run there)
  fig_pooled              FEVER against each baseline trained locally and on pooled data
  fig_ablation            FEVER against its four ablations

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/fig_final.py
"""
import csv
import os
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results", "testbed_prereg_final")
OUT = os.path.join(RES, "paper")
os.makedirs(OUT, exist_ok=True)

FEVER = "fever-fl-ll"
BASE = ["ftmaster", "ftop", "ftodefender", "flora", "dms-btt", "rdefender"]
ABL = ["fever-ll-local", "fever-ll-novol", "fever-noml", "fever-fl-ll-noing"]
LABEL = {"none": "No defense", "ftmaster": "FTMaster", "ftop": "FTOP", "ftodefender": "FTODefender",
         "flora": "FloRa", "dms-btt": "DMS-BTT", "rdefender": "rDefender", FEVER: "FEVER",
         "fever-ll-local": "w/o sharing", "fever-ll-novol": "w/o volume rule",
         "fever-noml": "w/o detector", "fever-fl-ll-noing": "w/o ingress blocking"}
ATT = {"T1B": ["A2", "A4", "A5", "A6", "A7", "E9P", "EVX"], "UHt": ["A2", "A4", "E9P"]}
ANAME = {"A2": "G2", "A4": "Mimic", "A5": "Spoof", "A6": "Slow", "A7": "Pulse", "E9P": "Aware", "EVX": "EVX"}
MEAS = [("benign_harmed_pct", "Benign flows harmed (%)", 2),
        ("occupancy", "Attack occupancy (%)", 1),
        ("probe_post_success_pct", "New-connection success (%)", 1)]
COL = {"none": "#c8c7c2", "ftmaster": "#2a78d6", "ftop": "#1baf7a", "ftodefender": "#eda100",
       "flora": "#e87ba4", "dms-btt": "#6250d6", "rdefender": "#52514e", FEVER: "#eb6834",
       "fever-ll-local": "#2a78d6", "fever-ll-novol": "#1baf7a", "fever-noml": "#eda100",
       "fever-fl-ll-noing": "#6250d6"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "savefig.bbox": "tight",
    "savefig.dpi": 300, "pdf.fonttype": 42, "hatch.linewidth": 0.6})

with open(os.path.join(RES, "runs.csv")) as f:
    RUNS = [r for r in csv.DictReader(f) if r["length"] == "300 s"]


def vals(trace, v, m, key):
    return [float(r[key]) for r in RUNS
            if (r["trace"], r["traffic"], r["method"]) == (trace, v, m) and r[key] not in ("", "None")]


def ms(trace, v, m, key):
    x = vals(trace, v, m, key)
    if not x:
        return None, None
    return mean(x), (stdev(x) if len(x) > 1 else 0.0)


def err(a, b, hi=100.0):
    """s.d. as an error bar, kept within 0 and 100 (the measures are percentages)."""
    if a is None:
        return [[0], [0]]
    return [[min(b, a)], [min(b, hi - a)]]


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"))
    plt.close(fig)


# Table: one block per measure, rows trace x attack, columns the methods.
METHODS = ["none"] + BASE + [FEVER]


def cell(trace, v, m, key, d):
    x, _ = ms(trace, v, m, key)
    return "--" if x is None else f"{x:.{d}f}"


tex = [r"\begin{table*}[t]", r"\centering", r"\caption{Comparative experiment results.}",
       r"\label{tab:main}", r"\small", r"\setlength{\tabcolsep}{4pt}",
       r"\begin{tabular}{ll" + "r" * len(METHODS) + "}", r"\toprule",
       "Trace & Attack & " + " & ".join(LABEL[m] for m in METHODS) + r" \\"]
rows_pdf = []
for key, title, d in MEAS:
    tex += [r"\midrule", rf"\multicolumn{{{2 + len(METHODS)}}}{{l}}{{\textit{{{title.replace('%', chr(92) + '%')}}}}} \\", r"\midrule"]
    rows_pdf.append(("head", title))
    for trace in ("T1B", "UHt"):
        for i, v in enumerate(ATT[trace]):
            c = [cell(trace, v, m, key, d) for m in METHODS]
            tex.append(f"{trace if i == 0 else ''} & {ANAME[v]} & " + " & ".join(c) + r" \\")
            rows_pdf.append(("row", [trace if i == 0 else "", ANAME[v]] + c))
tex += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
open(os.path.join(OUT, "table_main.tex"), "w").write("\n".join(tex))

# The same table as a PDF, to read without LaTeX.
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle  # noqa: E402

FD = "/usr/share/fonts/truetype/liberation/"
for n, fn in (("LS", "LiberationSerif-Regular.ttf"), ("LS-I", "LiberationSerif-Italic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + fn))
data = [["Trace", "Attack"] + [LABEL[m] for m in METHODS]]
style = [("FONT", (0, 0), (-1, -1), "LS", 9), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
         ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black), ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
         ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6)]
for kind, x in rows_pdf:
    r = len(data)
    if kind == "head":
        data.append([x] + [""] * (len(METHODS) + 1))
        style += [("SPAN", (0, r), (-1, r)), ("FONT", (0, r), (-1, r), "LS-I", 9),
                  ("LINEABOVE", (0, r), (-1, r), 0.5, colors.black),
                  ("LINEBELOW", (0, r), (-1, r), 0.5, colors.black), ("ALIGN", (0, r), (-1, r), "LEFT")]
    else:
        data.append(x)
t = Table(data, colWidths=[13 * mm, 15 * mm] + [24 * mm] * len(METHODS), repeatRows=1)
t.setStyle(TableStyle(style))
doc = SimpleDocTemplate(os.path.join(OUT, "table_main.pdf"), pagesize=landscape(A4),
                        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=12 * mm)
doc.build([Paragraph("Table 1. Comparative experiment results.",
                     ParagraphStyle("c", fontName="LS", fontSize=10, leading=13, spaceAfter=6)), t])


def grouped(ax, trace, atts, methods, key, width=0.82, hatch=None):
    n = len(methods)
    w = width / n
    x = np.arange(len(atts))
    for j, m in enumerate(methods):
        mm_ = [ms(trace, v, m, key) for v in atts]
        y = [a if a is not None else np.nan for a, _ in mm_]
        e = np.hstack([err(a, b) for a, b in mm_])
        ax.bar(x + (j - (n - 1) / 2) * w, y, w, yerr=e, color=COL[m], edgecolor="black", lw=0.4,
               hatch=(hatch or {}).get(m), label=LABEL[m],
               error_kw=dict(elinewidth=0.6, capsize=1.2, capthick=0.6, ecolor="black"))
    ax.set_xticks(x)
    ax.set_xticklabels([ANAME[v] for v in atts])
    ax.yaxis.grid(True, lw=0.4, color="#dddddd")
    ax.set_axisbelow(True)


# Figure: T1B, three measures stacked.
fig, axs = plt.subplots(3, 1, figsize=(7.16, 6.6), sharex=True)
for ax, (key, title, _) in zip(axs, MEAS):
    grouped(ax, "T1B", ATT["T1B"], METHODS, key)
    ax.set_ylabel(title)
axs[2].set_ylim(0, 105)
axs[0].legend(ncol=8, loc="lower center", bbox_to_anchor=(0.5, 1.02), handlelength=1.2, columnspacing=0.9)
fig.align_ylabels(axs)
save(fig, "fig_t1b")

# Figure: UHt.
UM = ["none", "ftmaster", "dms-btt", "rdefender", FEVER]
fig, axs = plt.subplots(1, 3, figsize=(7.16, 2.4))
for ax, (key, title, _) in zip(axs, MEAS):
    grouped(ax, "UHt", ATT["UHt"], UM, key)
    ax.set_title(title)
axs[2].set_ylim(0, 105)
fig.tight_layout(w_pad=1.5)
fig.legend(*axs[0].get_legend_handles_labels(), ncol=5, loc="lower center", bbox_to_anchor=(0.5, 0.98),
           handlelength=1.2)
save(fig, "fig_uht")

# Figure: pooled training. Per attack, each baseline trained locally (plain) and on the pooled data
# of all controllers (hatched), FEVER as the last bar.
PA = ["A4", "E9P", "A6", "EVX"]
PB = ["ftmaster", "ftop", "ftodefender", "flora", "dms-btt"]
fig, axs = plt.subplots(2, 4, figsize=(7.16, 3.9), sharey="row")
for col, v in enumerate(PA):
    for row, (key, title, _) in enumerate(MEAS[1:]):
        ax = axs[row, col]
        x = np.arange(len(PB) + 1)
        for j, m in enumerate(PB):
            for k, mm_name in enumerate((m, m + "-pool")):
                a, b = ms("T1B", v, mm_name, key)
                ax.bar(j + (k - 0.5) * 0.38, a, 0.38, yerr=err(a, b), color=COL[m], edgecolor="black", lw=0.4,
                       hatch="////" if k else None,
                       error_kw=dict(elinewidth=0.6, capsize=1.2, capthick=0.6))
        a, b = ms("T1B", v, FEVER, key)
        ax.bar(len(PB), a, 0.5, yerr=err(a, b), color=COL[FEVER], edgecolor="black", lw=0.4,
               error_kw=dict(elinewidth=0.6, capsize=1.2, capthick=0.6))
        ax.set_xticks(x)
        ax.set_xticklabels([LABEL[m] for m in PB] + ["FEVER"], rotation=55, ha="right", fontsize=7.5)
        ax.yaxis.grid(True, lw=0.4, color="#dddddd")
        ax.set_axisbelow(True)
        if row == 0:
            ax.set_title(ANAME[v])
            ax.set_xticklabels([])
        if col == 0:
            ax.set_ylabel(title)
axs[1, 0].set_ylim(0, 105)
from matplotlib.patches import Patch  # noqa: E402
fig.legend(handles=[Patch(facecolor="white", edgecolor="black", lw=0.4, label="local training"),
                    Patch(facecolor="white", edgecolor="black", lw=0.4, hatch="////", label="pooled training")],
           ncol=2, loc="lower center", bbox_to_anchor=(0.5, 0.99))
fig.align_ylabels(axs[:, 0])
fig.tight_layout(h_pad=0.6, w_pad=0.6)
save(fig, "fig_pooled")

# Figure: ablations.
AM = [FEVER] + ABL
HAT = {"fever-ll-local": "////", "fever-ll-novol": "\\\\\\\\", "fever-noml": "xxxx", "fever-fl-ll-noing": "...."}
fig, axs = plt.subplots(1, 3, figsize=(7.16, 2.4))
for ax, (key, title, _) in zip(axs, MEAS):
    grouped(ax, "T1B", ["A2", "A4", "E9P"], AM, key, hatch=HAT)
    ax.set_title(title)
axs[2].set_ylim(0, 105)
fig.tight_layout(w_pad=1.5)
fig.legend(*axs[0].get_legend_handles_labels(), ncol=5, loc="lower center", bbox_to_anchor=(0.5, 0.98),
           handlelength=1.6, columnspacing=1.0)
save(fig, "fig_ablation")
print("written to", os.path.abspath(OUT))
