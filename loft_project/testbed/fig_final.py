"""Paper table and figures of the final testbed campaign, from results/testbed_prereg_final/runs.csv
(the 300 s runs counted by testbed/analyze_final.py, amendment 1 measures).

  table_main.tex / .pdf   harm, occupancy and probe success per attack, every method (mean over seeds)
  table_overhead.tex      decision time, controller CPU and memory, Packet-In (page 2 of table_main.pdf)
  fig_t1b                 the same three measures on T1B, grouped bars per attack, mean and s.d.
  fig_uht                 the same on UHt (the three baselines run there)
  fig_pooled              FEVER against each baseline trained locally and on pooled data
  fig_ablation            FEVER against its four ablations
  fig_timeline            attack occupancy over time on Mimic and Aware (median over seeds)

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
CAP = ParagraphStyle("c", fontName="LS", fontSize=10, leading=13, spaceAfter=6)
story = [Paragraph("Table 1. Comparative experiment results.", CAP), t]


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
w = 0.82 / len(METHODS)
for i, v in enumerate(ATT["T1B"]):       # FEVER's harm is too small to see as a bar
    a, _ = ms("T1B", v, FEVER, "benign_harmed_pct")
    axs[0].text(i + ((len(METHODS) - 1) / 2 + 0.3) * w, a + 0.3, f"{a:.2f}", rotation=90, ha="center", va="bottom",
                fontsize=6.5)
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
# Table: controller overhead over all T1B runs (every attack and benign-only), mean (s.d.) per run.
OV = [("decision_ms_mean", "Decision (ms)", 1, 1), ("ctrl_cpu_pct", "CPU (\\%)", 1, 1),
      ("ctrl_rss_mb", "Memory (MB)", 0, 1), ("packet_in", "Packet-In ($10^3$)", 1, 1e3)]
OVM = ["none"] + BASE + [FEVER]


def ov(m, key, d, div):
    x = [float(r[key]) / div for r in RUNS
         if r["trace"] == "T1B" and r["method"] == m and r[key] not in ("", "None")]
    return f"{mean(x):.{d}f} ({stdev(x):.{d}f})", len(x)


tex = [r"\begin{table}[t]", r"\centering", r"\caption{Controller overhead.}", r"\label{tab:overhead}",
       r"\small", r"\setlength{\tabcolsep}{4pt}", r"\begin{tabular}{l" + "r" * len(OV) + "}", r"\toprule",
       "Method & " + " & ".join(h for _, h, _, _ in OV) + r" \\", r"\midrule"]
data2 = [["Method"] + [h.replace("\\%", "%").replace("$10^3$", "thousands") for _, h, _, _ in OV]]
for m in OVM:
    c = [ov(m, k, d, div)[0] for k, _, d, div in OV]
    tex.append(f"{LABEL[m]} & " + " & ".join(c) + r" \\")
    data2.append([LABEL[m]] + c)
tex += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
open(os.path.join(OUT, "table_overhead.tex"), "w").write("\n".join(tex))
from reportlab.platypus import PageBreak  # noqa: E402
t2 = Table(data2, colWidths=[30 * mm] + [38 * mm] * len(OV))
t2.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "LS", 9), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                        ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                        ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6)]))
story += [PageBreak(), Paragraph("Table 2. Controller overhead.", CAP), t2]
doc.build(story)

# Figure: attack occupancy over time (mean of the three switches' attack share, as in the tables),
# median over the seeds at each second. A run counted under amendment 1 is read from its _failed copy.
RUNDIR = os.path.expanduser("~/loft-runs")
with open(os.path.join(RES, "report.md")) as f:
    rep = f.read()
COUNTED = {}
for line in rep.split("## Runs counted under amendment 1", 1)[1].split("##", 1)[0].splitlines():
    if line.startswith("- "):
        n = line[2:].strip()
        COUNTED[n.rsplit(".", 1)[0]] = os.path.join(RUNDIR, "_failed", n)
ATT_MACS = {"00:00:00:00:01:05", "00:00:00:00:01:06"}
GRID = np.arange(0, 311)


def occ_series(d, cap=3500):
    out = []
    for sw in ("s11", "s12", "s13"):
        with open(os.path.join(d, f"switch_T1B_{sw}.csv")) as fh:
            ts = [float(x["t"]) for x in csv.DictReader(fh)]
        pa = dict.fromkeys(ts, 0)
        with open(os.path.join(d, f"switch_T1B_{sw}_macs.csv")) as fh:
            for x in csv.DictReader(fh):
                if x["mac"] in ATT_MACS and float(x["t"]) in pa:
                    pa[float(x["t"])] += int(x["entries"])
        out.append(np.interp(GRID, ts, [100 * pa[t] / cap for t in ts]))
    return np.mean(out, axis=0)


TM = ["none", "ftmaster", "ftodefender", "dms-btt", FEVER]
LS = {"none": (0, (1, 1.5)), "ftmaster": (0, (5, 2)), "ftodefender": (0, (3, 1.5, 1, 1.5)),
      "dms-btt": (0, (8, 2, 2, 2)), FEVER: "-"}
fig, axs = plt.subplots(1, 2, figsize=(7.16, 2.5), sharey=True)
for ax, v in zip(axs, ["A4", "E9P"]):
    for m in TM:
        ys = []
        for sd in range(4160, 4165):
            n = f"fin_T1B_{v}_{m}_s{sd}"
            ys.append(occ_series(COUNTED.get(n, os.path.join(RUNDIR, n))))
        ax.plot(GRID, np.median(ys, axis=0), color=COL[m], ls=LS[m], lw=1.6 if m == FEVER else 1.1,
                label=LABEL[m])
    ax.axvline(50, color="black", lw=0.6, ls=":")
    ax.set_title(ANAME[v])
    ax.set_xlabel("Time (s)")
    ax.set_xlim(0, 310)
    ax.yaxis.grid(True, lw=0.4, color="#dddddd")
axs[0].set_ylabel("Attack occupancy (%)")
axs[0].set_ylim(0, None)
fig.tight_layout(w_pad=1.2)
fig.legend(*axs[0].get_legend_handles_labels(), ncol=5, loc="lower center", bbox_to_anchor=(0.5, 0.98),
           handlelength=2.6)
save(fig, "fig_timeline")
print("written to", os.path.abspath(OUT))
