"""The figures the related papers show (Other Paper/experiments_summary.md), drawn from our data.

Testbed figures use the 200 preregistered v3 runs (~/loft-runs/v3_T1_<variant>_<defense>_s<seed>,
T1, tree3, table 3,500, idle 10 s, attack at 50 s, seeds 4120-4124) at the core switch s11 unless
stated. Lines are the median over the 5 seeds; bars are means with the min-max range over runs.
Detection figures use E11 (simulator, results/e11_detect) and the testbed entry logs
(~/loft-runs/e11tb_*); the block-rule sensitivity comes from the simulator selection
(results/evictblock).

 fig  what (papers that show it)
 01   table rules over time, attack vs benign, per defense (LOFT, FTMaster, FTODefender, FTOP, FloRa, ALFO, rDefender)
 02   attack-rule share Pa over time, with and without defense (SFTO-Guard, FTODefender, DMS-BTT)
 03   comparison: avg/max Pa, avg usage, overflow time, Packet-In, Table-Full (FTMaster, FTODefender, FTOP, DMS-BTT, FTShield)
 04   Packet-In rate over time: no attack / attack / defended (SFTO-Guard, FTMaster, DMS-BTT, FTShield)
 05   Packet-In loss rate per defense (rDefender)
 06   new-connection success and delay (LOFT, ALFO)
 07   per-poll decision time (FTMaster, FTOP, SFTO-Guard, rDefender)
 08   controller CPU and memory (all defense papers)
 09   offline classifier comparison, Acc/Precision/Recall/F1 (SFTO-Guard, FTMaster, FTOP, FloRa, DMS-BTT, FTShield)
 10   table composition 150 s into the attack (FTShield shows it at 45 s; here no defense has acted yet at 45 s)
 11   detection-score distribution, benign vs attack (FTODefender)
 12   block-threshold sensitivity (FTODefender TH2, FTMaster threshold)
 13   accuracy / precision / recall / F1, one panel each, every paper's detector at the same 0.1 % FPR
 14   the same at each paper's own threshold

With --v5 the testbed figures (01-08, 10) are drawn from the preregistered v5 campaign instead
(~/loft-runs/v5_T1B_*, T1B, seeds 4140-4144, 6 defenses) into results/paper_figs/v5/, plus
 15   per-seed harm and attack share, v5 against DMS-BTT and FTMaster, per attack
 16   A2 timeline: why v5 harms more than the baselines under A2 (its block expires)

    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/paper_figs.py         # writes results/paper_figs/
    PYTHONPATH=. ~/.venvs/loft/bin/python testbed/paper_figs.py --v5    # writes results/paper_figs/v5/
"""
import csv
import glob
import os
import re
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

R = os.path.expanduser("~/loft-runs")
OUT = "results/paper_figs"
CAP, T_ATT, DUR = 3500, 50.0, 300
SEEDS = [4120, 4121, 4122, 4123, 4124]
ATTACKS = ["A2", "A4", "E9P"]
DEFS = ["none", "evict", "sift", "tableguard", "rdefender", "ftmaster", "ftop", "dms-btt",
        "dualguard-portguard-hostid", "ensguard"]
NAME = {"none": "None", "evict": "EVICT", "sift": "SIFT", "tableguard": "TableGuard",
        "rdefender": "rDefender", "ftmaster": "FTMaster", "ftop": "FTOP", "dms-btt": "DMS-BTT",
        "dualguard-portguard-hostid": "FL-DualGuard", "ensguard": "EnsGuard"}
ATT_MACS = {"00:00:00:00:01:05", "00:00:00:00:01:06"}
PREFIX, DOM, HL = "v3_T1", "T1", "ensguard"     # campaign run-name prefix, domain, highlighted defense
SHOW = ["none", "ftmaster", "ftop", "dms-btt", "ensguard"]


def use_v5():
    """Switch the testbed figures to the preregistered v5 campaign (T1B, seeds 4140-4144)."""
    global PREFIX, DOM, HL, SHOW, SEEDS, DEFS, OUT
    PREFIX, DOM, HL, OUT = "v5_T1B", "T1B", "ensguard-v5", "results/paper_figs/v5"
    SEEDS = [4140, 4141, 4142, 4143, 4144]
    DEFS = ["none", "ensguard", "ensguard-v4lite", "ensguard-v5", "dms-btt", "ftmaster"]
    SHOW = ["none", "ftmaster", "dms-btt", "ensguard", "ensguard-v5"]
    NAME.update({"ensguard": "EnsGuard v3", "ensguard-v4lite": "EnsGuard v4-lite", "ensguard-v5": "FEVER"})


def published_only():
    """With --v5 --pub: FEVER against the published methods only (no defense, FTMaster, DMS-BTT), into
    results/paper_figs/v5pub/."""
    global DEFS, SHOW, OUT
    DEFS = ["none", "ftmaster", "dms-btt", "ensguard-v5"]
    SHOW = ["none", "ftmaster", "dms-btt", "ensguard-v5"]
    OUT = "results/paper_figs/v5pub"
    # Journal style: the explanation goes in the caption, so long in-figure titles are dropped.
    import matplotlib.axes
    import matplotlib.figure
    matplotlib.figure.Figure.suptitle = lambda self, *a, **k: None
    _st = matplotlib.axes.Axes.set_title
    matplotlib.axes.Axes.set_title = lambda self, t="", *a, **k: _st(self, t if len(str(t)) <= 40 else "", *a, **k)

# Reference categorical palette (dataviz skill), fixed order; neutrals for context marks.
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID, NEUTRAL, FREE = "#0b0b0b", "#52514e", "#e4e3df", "#9a9993", "#d9d8d3"
BENIGN, ATTACK = C[0], C[1]
plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False, "lines.linewidth": 2, "figure.dpi": 150,
    "savefig.bbox": "tight", "font.family": "DejaVu Sans"})


def run_dir(v, d, s):
    return f"{R}/{PREFIX}_{v}_{d}_s{s}"


def summary(path):
    out = {}
    for line in open(path):
        m = re.match(r"\s+(\S+)\s+(.+?)\s*$", line)
        if m:
            try:
                out[m[1]] = float(m[2])
            except ValueError:
                out[m[1]] = m[2]
    return out


def series(d, sw="s11"):
    """Per-second grid 0..DUR: total entries, attacker entries at switch sw, and Packet-In per
    second at the whole controller (controller_<DOM>.csv; the access switches send most of them)."""
    grid = np.arange(0, DUR + 1)
    rows = list(csv.DictReader(open(f"{d}/switch_{DOM}_{sw}.csv")))
    crow = list(csv.DictReader(open(f"{d}/controller_{DOM}.csv")))
    tc = np.array([float(r["t"]) for r in crow])
    pc = np.array([float(r["packet_in"]) for r in crow])
    t = np.array([float(r["t"]) for r in rows])
    ent = np.array([float(r["entries"]) for r in rows])
    att = {}
    for r in csv.DictReader(open(f"{d}/switch_{DOM}_{sw}_macs.csv")):
        if r["mac"] in ATT_MACS:
            att[float(r["t"])] = att.get(float(r["t"]), 0) + int(r["entries"])
    a = np.array([att.get(x, 0) for x in t], float)
    rate = np.diff(pc, prepend=pc[0]) / np.maximum(np.diff(tc, prepend=tc[0] - 1), 1e-3)
    f = lambda y, x=t: np.interp(grid, x, y, left=np.nan, right=np.nan)  # noqa: E731
    return grid, f(ent), f(a), f(np.maximum(rate, 0), tc)


def med(v, d, key):
    """Median over seeds of one series (index 1 entries, 2 attack entries, 3 Packet-In/s)."""
    return np.nanmedian(np.vstack([series(run_dir(v, d, s))[key] for s in SEEDS]), axis=0)


def cpu_mem(d):
    """Controller (python3.8) mean %CPU and max RSS (MB) after the attack starts."""
    def rows(p):
        out = []
        for line in open(p):
            f = line.split()
            if f and f[-1] == "python3.8" and not line.startswith("Average"):
                out.append(f)
        return out
    cpu = [float(f[-3]) for f in rows(f"{d}/cpu_pidstat.txt")]
    mem = [float(f[-3]) / 1024 for f in rows(f"{d}/mem_pidstat.txt")]
    cpu = cpu[int(T_ATT):] or cpu
    return (st.mean(cpu) if cpu else np.nan), (max(mem) if mem else np.nan)


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(f"{OUT}/{name}.{ext}")
    plt.close(fig)
    print("wrote", name)


def attack_line(ax):
    ax.axvline(T_ATT, color=NEUTRAL, lw=1, ls=":")


# ---------------------------------------------------------------- testbed time series
def fig01():
    for v in ATTACKS:
        nc = (len(DEFS) + 1) // 2
        fig, axs = plt.subplots(2, nc, figsize=(2.4 * nc, 4.6), sharex=True, sharey=True)
        for ax, d in zip(axs.flat, DEFS):
            g = np.arange(0, DUR + 1)
            tot, att = med(v, d, 1), med(v, d, 2)
            ben = np.clip(tot - att, 0, None)
            ax.fill_between(g, 0, ben, color=BENIGN, alpha=0.85, lw=0, label="benign rules")
            ax.fill_between(g, ben, ben + att, color=ATTACK, alpha=0.9, lw=0, label="attack rules")
            ax.axhline(CAP, color=INK2, lw=1, ls="--")
            attack_line(ax)
            ax.set_title(NAME[d])
            ax.set_ylim(0, CAP * 1.08)
        for ax in axs[1]:
            ax.set_xlabel("time (s)")
        for ax in axs[:, 0]:
            ax.set_ylabel("rules in s11")
        axs[0, 0].text(DUR, CAP, "capacity 3,500", ha="right", va="bottom", fontsize=7.5, color=INK2)
        h, lab = axs[0, 0].get_legend_handles_labels()
        fig.legend(h, lab, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.04))
        fig.suptitle(f"Flow-table rules over time under {v} (testbed, median of 5 seeds; attack from 50 s)",
                     y=1.09, fontsize=10)
        save(fig, f"fig01_rules_over_time_{v}")


def fig02():
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    for ax, v in zip(axs, ATTACKS):
        for i, d in enumerate(SHOW):
            pa = 100 * med(v, d, 2) / CAP
            ax.plot(np.arange(0, DUR + 1), pa, color=NEUTRAL if d == "none" else C[i],
                    lw=2, ls="--" if d == "none" else "-", label=NAME[d])
        attack_line(ax)
        ax.set_title(v)
        ax.set_xlabel("time (s)")
    axs[0].set_ylabel("attack-rule share Pa (%)")
    axs[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Attack-rule share of the s11 table over time (testbed, median of 5 seeds)", y=1.02, fontsize=10)
    save(fig, "fig02_attack_share_over_time")


def fig04():
    cases = [("benign", "none", "no attack", NEUTRAL, "--"), ("A4", "none", "A4, no defense", C[1], "-"),
             ("A4", "dms-btt", "A4, DMS-BTT", C[3], "-"), ("A4", HL, f"A4, {NAME[HL]}", C[0], "-")]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for v, d, lab, col, ls in cases:
        y = pd.Series(med(v, d, 3)).rolling(5, min_periods=1, center=True).mean()
        ax.plot(np.arange(0, DUR + 1), y, color=col, ls=ls, label=lab)
    attack_line(ax)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("Packet-In per second at the controller\n(5 s mean)")
    ax.legend(fontsize=8)
    ax.set_title("Control-channel load (testbed, median of 5 seeds)")
    save(fig, "fig04_packet_in_over_time")


def fig10():
    t = int(T_ATT + 150)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    y = np.arange(len(DEFS))
    for i, d in enumerate(DEFS):
        tot, att = [], []
        for s in SEEDS:
            _, e, a, _ = series(run_dir("A4", d, s))
            tot.append(e[t])
            att.append(a[t])
        a = 100 * np.nanmean(att) / CAP
        b = 100 * np.nanmean(tot) / CAP - a
        f = max(0.0, 100 - a - b)
        ax.barh(i, a, color=ATTACK, height=0.7, edgecolor="white", lw=1, label="attack" if i == 0 else None)
        ax.barh(i, b, left=a, color=BENIGN, height=0.7, edgecolor="white", lw=1, label="benign" if i == 0 else None)
        ax.barh(i, f, left=a + b, color=FREE, height=0.7, edgecolor="white", lw=1, label="free" if i == 0 else None)
        ax.text(101, i, f"{a:.0f} / {b:.0f} / {f:.0f}", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [NAME[d] for d in DEFS])
    ax.invert_yaxis()
    ax.set_xlim(0, 118)
    ax.set_xlabel("share of the s11 table (%)  -  labels: attack / benign / free")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.45, 1.0), fontsize=8)
    ax.set_title(f"Table composition {t - int(T_ATT)} s into A4 (testbed, mean of 5 seeds)", pad=22)
    save(fig, "fig10_table_composition")


# ---------------------------------------------------------------- testbed per-run metrics
def per_run():
    rows = []
    for v in ATTACKS + ["benign"]:
        for d in DEFS:
            for s in SEEDS:
                p = run_dir(v, d, s)
                sm = summary(f"{p}/summary.txt")
                cpu, mem = cpu_mem(p)
                dec = [float(r["decision_ms"]) for r in csv.DictReader(open(f"{p}/switch_{DOM}_s11.csv"))
                       if float(r["t"]) >= T_ATT]
                rows.append(dict(variant=v, defense=d, seed=s,
                                 pa_avg=sm.get("attack_share_avg_pct_s11"), pa_max=sm.get("attack_share_max_pct_s11"),
                                 usage_avg=sm.get("table_usage_avg_pct_s11"), overflow_s=sm.get("overflow_s_post_s11"),
                                 first_overflow_s=sm.get("first_overflow_s_s11"),
                                 table_full=sm.get("table_full_s11"), packet_in=sm.get("packet_in"),
                                 pin_lost=sm.get("benign_packet_in_lost_pct"), harm=sm.get("benign_harmed_pct"),
                                 probe_ok=sm.get("probe_post_success_pct"),
                                 probe_ms=sm.get("probe_post_connect_ms_median"),
                                 decision_ms_median=np.median(dec) if dec else np.nan,
                                 decision_ms_p95=np.percentile(dec, 95) if dec else np.nan,
                                 cpu_pct=cpu, mem_mb=mem))
    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/testbed_runs.csv", index=False)
    return df


def bars(ax, df, key, title, fmt="{:.1f}", hl=None):
    hl = hl or HL
    g = df.groupby("defense")[key]
    m, lo, hi = g.mean().reindex(DEFS), g.min().reindex(DEFS), g.max().reindex(DEFS)
    x = np.arange(len(DEFS))
    cols = [C[1] if d == hl else (NEUTRAL if d == "none" else C[0]) for d in DEFS]
    ax.bar(x, m, color=cols, width=0.72, edgecolor="white", lw=1)
    ax.errorbar(x, m, yerr=[m - lo, hi - m], fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
    ax.set_xticks(x, [NAME[d] for d in DEFS], rotation=45, ha="right")
    ax.set_title(title)
    ax.grid(axis="x", visible=False)
    for xi, mi, hv in zip(x, m, hi):
        if np.isfinite(mi):
            ax.annotate(fmt.format(mi), (xi, hv), xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom", fontsize=6.5, color=INK)


def fig03(df):
    a = df[df.variant.isin(ATTACKS)].copy()
    a["packet_in_k"] = a.packet_in / 1000
    fig, axs = plt.subplots(2, 3, figsize=(12, 6.6))
    for ax, (k, t, f) in zip(axs.flat, [
            ("pa_avg", "average attack share Pa (%)", "{:.1f}"), ("pa_max", "maximum attack share Pa (%)", "{:.0f}"),
            ("usage_avg", "average table usage (%)", "{:.0f}"), ("overflow_s", "seconds at the limit after attack", "{:.0f}"),
            ("packet_in_k", "Packet-In messages (thousands)", "{:.0f}"), ("table_full", "Table-Full messages (s11)", "{:.0f}")]):
        bars(ax, a, k, t, f)
    fig.suptitle("Defense comparison on the testbed (A2, A4, E9P x 5 seeds; bar = mean, whisker = min-max)",
                 fontsize=10)
    fig.tight_layout()
    if "evict" in DEFS:
        fig.text(0.01, -0.01, "EVICT replaces entries when the table is full, so the switch sends no Table-Full "
                 "message (the papers report NA).", fontsize=7.5, color=INK2)
    save(fig, "fig03_comparison")
    g = a.groupby("defense")[["pa_avg", "pa_max", "usage_avg", "overflow_s", "packet_in", "table_full",
                              "pin_lost", "harm", "probe_ok", "decision_ms_median", "cpu_pct", "mem_mb"]].mean()
    g.reindex(DEFS).rename(index=NAME).round(2).to_csv(f"{OUT}/comparison_table.csv")


def dots(ax, df, key, xlabel):
    y = np.arange(len(DEFS))
    for i, v in enumerate(ATTACKS):
        m = df[df.variant == v].groupby("defense")[key].mean().reindex(DEFS)
        ax.plot(m, y + (i - 1) * 0.22, "o", ms=6, color=C[i], label=v, mec="white", mew=1)
    ax.set_yticks(y, [NAME[d] for d in DEFS])
    if not ax.yaxis_inverted():
        ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)


def fig05(df):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    dots(axs[0], df, "pin_lost", "benign first packets lost at the controller (%)")
    dots(axs[1], df, "harm", "benign flows harmed (%)")
    axs[0].legend(title="attack", fontsize=8, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.suptitle("Packet-In loss rate and benign harm (testbed, mean of 5 seeds)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig05_packet_in_loss")


def fig06(df):
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    dots(axs[0], df, "probe_ok", "new connections that succeed after the attack starts (%)")
    dots(axs[1], df, "probe_ms", "median connect time of new connections (ms)")
    axs[0].legend(title="attack", fontsize=8, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.suptitle("Service to new flows (testbed probe, one new TCP connection every 0.5 s)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig06_new_flow_service")


def fig07():
    fig, ax = plt.subplots(figsize=(8, 3.6))
    data = []
    for d in DEFS:
        x = []
        for v in ATTACKS:
            for s in SEEDS:
                x += [float(r["decision_ms"]) for r in csv.DictReader(open(f"{run_dir(v, d, s)}/switch_{DOM}_s11.csv"))
                      if float(r["t"]) >= T_ATT]
        data.append(np.maximum(x, 0.1))
    b = ax.boxplot(data, whis=(5, 95), showfliers=False, patch_artist=True, widths=0.6,
                   medianprops=dict(color=INK, lw=1.5))
    for p, d in zip(b["boxes"], DEFS):
        p.set(facecolor=C[1] if d == HL else C[0], alpha=0.85, edgecolor="white")
    ax.set_yscale("log")
    ax.set_xticks(np.arange(1, len(DEFS) + 1), [NAME[d] for d in DEFS], rotation=45, ha="right")
    ax.set_ylabel("decision time per poll (ms, log)")
    ax.grid(axis="x", visible=False)
    ax.set_title("Per-poll processing time at s11 under attack (box 25-75 %, whiskers 5-95 %)")
    save(fig, "fig07_decision_time")


def fig08(df):
    a = df[df.variant.isin(ATTACKS)]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.6))
    bars(axs[0], a, "cpu_pct", "controller CPU under attack (% of one core)", "{:.0f}")
    bars(axs[1], a, "mem_mb", "controller memory, peak RSS (MB)", "{:.0f}")
    fig.suptitle("Controller overhead (testbed, A2/A4/E9P x 5 seeds)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig08_cpu_memory")


# ---------------------------------------------------------------- detection
def fig09():
    t = pd.read_csv("results/e11_detect/table_main.csv")
    t = t[t.op == "fpr0.1"]
    dets = ["ftop", "ftmaster", "flora", "dms-btt", "fl-dualguard", "ensguard"]
    lab = {"ftop": "FTOP", "ftmaster": "FTMaster", "flora": "FloRa", "dms-btt": "DMS-BTT",
           "fl-dualguard": "FL-DualGuard", "ensguard": "EnsGuard"}
    mets = [("accuracy", "Accuracy"), ("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]
    exps = [("seen-local", "attacks this controller trained on"),
            ("seen-remote", "attacks only another controller saw"), ("unseen-all", "attacks no controller saw")]
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
    w = 0.2
    for ax, (e, et) in zip(axs, exps):
        x = np.arange(len(dets))
        for j, (k, kl) in enumerate(mets):
            vals = [t[(t.detector == d) & (t.exposure == e)][k].mean() for d in dets]
            ax.bar(x + (j - 1.5) * w, vals, w * 0.92, color=C[j], label=kl, edgecolor="white", lw=0.5)
        ax.set_xticks(x, [lab[d] for d in dets], rotation=30, ha="right")
        ax.set_title(et)
        ax.set_ylim(0, 105)
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("%")
    axs[0].legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.08), fontsize=8)
    fig.suptitle("Per-rule classification at a 0.1 % benign false-positive rate (E11, simulator D1-D3)",
                 y=1.1, fontsize=10)
    save(fig, "fig09_classifier_comparison")


def fig13(op="fpr0.1"):
    """One panel per metric (accuracy, precision, recall, F1): each paper's detector against the
    others, grouped by exposure. op fpr0.1: every detector at the same 0.1 % benign false-positive
    rate; op paper: each at its own paper's threshold (0.5 for the baselines, the deployed tau
    for EnsGuard and FL-DualGuard)."""
    t = pd.read_csv("results/e11_detect/table_main.csv")
    t = t[t.op == op]
    dets = ["ftop", "ftmaster", "flora", "dms-btt", "fl-dualguard", "ensguard"]
    lab = {"ftop": "FTOP", "ftmaster": "FTMaster", "flora": "FloRa", "dms-btt": "DMS-BTT",
           "fl-dualguard": "FL-DualGuard", "ensguard": "EnsGuard"}
    exps = [("seen-local", "seen by this\ncontroller"), ("seen-remote", "seen only by\nanother controller"),
            ("unseen-all", "seen by no\ncontroller")]
    fig, axs = plt.subplots(2, 2, figsize=(12, 7.2), sharey=True)
    w = 0.13
    x = np.arange(len(exps))
    for ax, (k, kl) in zip(axs.flat, [("accuracy", "Accuracy"), ("precision", "Precision"),
                                      ("recall", "Recall"), ("f1", "F1 score")]):
        for j, d in enumerate(dets):
            vals = [t[(t.detector == d) & (t.exposure == e)][k].mean() for e, _ in exps]
            b = ax.bar(x + (j - 2.5) * w, vals, w * 0.92, color=C[j], label=lab[d], edgecolor="white", lw=0.5)
            for xi, v in zip(x + (j - 2.5) * w, vals):
                ax.text(xi, v + 1, f"{v:.0f}", ha="center", va="bottom", fontsize=6, color=INK, rotation=90)
        ax.set_xticks(x, [e for _, e in exps])
        ax.set_title(kl, fontsize=10, weight="bold")
        ax.set_ylim(0, 118)
        ax.set_yticks(range(0, 101, 20))
        ax.grid(axis="x", visible=False)
    for ax in axs[:, 0]:
        ax.set_ylabel("%")
    h, l_ = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l_, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 1.0), fontsize=8.5)
    sub = ("every detector at the same 0.1 % benign false-positive rate" if op == "fpr0.1" else
           "each detector at its own paper's threshold (baselines 0.5; EnsGuard and FL-DualGuard: deployed tau)")
    fig.suptitle(f"Per-rule detection by metric (E11, simulator D1-D3): {sub}", y=1.04, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "fig13_metrics_by_paper" if op == "fpr0.1" else "fig14_metrics_by_paper_own_threshold")


def fig11():
    cache = f"{OUT}/scores_ensguard_testbed.npz"
    if not os.path.exists(cache):
        sys.path.insert(0, "testbed")
        import entrylog
        import e11_testbed as E
        score, tau = E.detectors()["ensguard"]
        out = {}
        for v, s, d in E.tb_runs(os.path.expanduser("~/loft-runs/e11tb_T1_*_none_s*")):
            for sw in E.SWITCHES:
                b = entrylog.build(d, sw=sw, frac=0.05, seed=s)
                b = {k: x[b["t"] >= T_ATT] for k, x in b.items()} if v != "benign" else b
                p = score(b)
                out.setdefault(f"{v}_benign", []).append(p[b["y"] == 0])
                if v != "benign":
                    out.setdefault(f"{v}_attack", []).append(p[b["y"] == 1])
        np.savez_compressed(cache, tau=tau, **{k: np.concatenate(x) for k, x in out.items()})
    z = np.load(cache)
    tau = float(z["tau"])
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    bins = np.linspace(0, 1, 41)
    for ax, v in zip(axs, ATTACKS):
        for k, col, lab in ((f"{v}_benign", BENIGN, "benign entries"), (f"{v}_attack", ATTACK, "attack entries")):
            x = z[k]
            ax.hist(x, bins=bins, weights=np.full(len(x), 100 / max(len(x), 1)), color=col, alpha=0.75,
                    label=lab, edgecolor="white", lw=0.4)
        ax.axvline(tau, color=INK, lw=1.2, ls="--")
        ax.set_title(f"{v} (median attack score {np.median(z[f'{v}_attack']):.2f})")
        ax.set_xlabel("EnsGuard score")
        ax.set_yscale("log")
    axs[0].set_ylabel("% of entries (log)")
    axs[0].legend(fontsize=8, loc="upper center")
    axs[2].annotate(f"deployed threshold {tau:.2f}", (tau, 30), xytext=(-6, 0), textcoords="offset points",
                    ha="right", fontsize=7.5, color=INK)
    fig.suptitle("Detection-score distribution on the testbed (T1 entry logs, defense off, seeds 4131-4133)",
                 y=1.02, fontsize=10)
    save(fig, "fig11_score_distribution")


def fig12():
    s = pd.read_csv("results/evictblock/select_summary.csv")
    s = s[s.defense.str.startswith("eb-ens")].copy()
    p = s.defense.str.extract(r"b(?P<b>[\d.]+)-n(?P<n>\d+)f(?P<k>[\d.]+)")
    s = pd.concat([s, p], axis=1)
    s["budget"] = (100 * s.b.astype(float)).map(lambda x: f"{x:g} %")
    s["rule"] = "n>=" + s.n + ", k=" + s.k
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4))
    rules = sorted(s.rule.unique(), key=lambda r: (int(r.split(",")[0][3:]), float(r.split("=")[-1])))
    x = np.arange(len(rules))
    for j, bud in enumerate(sorted(s.budget.unique())):
        q = s[s.budget == bud].set_index("rule").reindex(rules)
        for ax, (k, t) in zip(axs, [("attack_occ_pct", "attack occupancy (%)"), ("harm_pct", "benign harm (%)"),
                                     ("benign_deletes", "benign entries deleted per run")]):
            ax.bar(x + (j - 0.5) * 0.38, q[k], 0.36, color=C[j], label=f"tau budget {bud}", edgecolor="white")
            ax.set_title(t)
            ax.set_xticks(x, rules, rotation=30, ha="right")
            ax.grid(axis="x", visible=False)
    axs[0].legend(fontsize=8)
    fig.suptitle("Sensitivity of EnsGuard's block rule (simulator development seeds 2000-2002, D1-D3)",
                 y=1.02, fontsize=10)
    save(fig, "fig12_block_rule_sensitivity")


# ---------------------------------------------------------------- v5 campaign only
def fig15(df):
    """Per attack: benign harm and attack share, mean bar plus one dot per seed."""
    show = DEFS
    fig, axs = plt.subplots(2, 3, figsize=(12, 6.2))
    x = np.arange(len(show))
    for j, v in enumerate(ATTACKS):
        a = df[df.variant == v]
        for ax, (k, t) in zip(axs[:, j], [("harm", "benign flows harmed (%)"), ("pa_avg", "average attack share s11 (%)")]):
            m = a.groupby("defense")[k].mean().reindex(show)
            cols = [C[1] if d == HL else (NEUTRAL if d == "none" else C[0]) for d in show]
            ax.bar(x, m, color=cols, width=0.7, edgecolor="white", lw=1, alpha=0.85)
            for i, d in enumerate(show):
                y = a[a.defense == d][k].values
                ax.plot(np.full(len(y), i) + np.linspace(-0.18, 0.18, len(y)), y, "o", ms=3.5, color=INK, mec="white", mew=0.5)
                ax.annotate(f"{m[d]:.2f}" if k == "harm" else f"{m[d]:.0f}", (i, max(y.max(), m[d])), xytext=(0, 2),
                            textcoords="offset points", ha="center", va="bottom", fontsize=6.5, color=INK)
            ax.set_xticks(x, [NAME[d] for d in show], rotation=40, ha="right")
            ax.grid(axis="x", visible=False)
            ax.set_title(f"{v}: {t}")
    fig.suptitle("FEVER campaign per attack (testbed, T1B; bar = mean of 5 seeds, dot = one seed)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig15_per_attack_per_seed")


def fig16(seed=4141):
    """A2, one seed: core-table entries over time for v5 and the two baselines, with v5's block,
    its expiry and the time its table was full."""
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    g = np.arange(0, DUR + 1)
    for d, col in (("dms-btt", C[3]), ("ftmaster", C[2]), (HL, C[1])):
        _, e, a, _ = series(run_dir("A2", d, seed))
        ax.plot(g, e, color=col, lw=1.8, label=f"{NAME[d]}: all entries")
        if d == HL:
            ax.fill_between(g, 0, a, color=col, alpha=0.25, lw=0, label=f"{NAME[d]}: attacker entries")
    rows = list(csv.DictReader(open(f"{run_dir('A2', HL, seed)}/controller_{DOM}.csv")))
    t_blk = next(float(r["t"]) for r in rows if float(r["drop_rules"]) > 0)
    t_full = [float(r["t"]) for r in rows if float(r["entries"]) >= 0.98 * CAP]
    ax.axhline(CAP, color=INK2, lw=1, ls="--")
    attack_line(ax)
    for t, lab in ((t_blk, "FEVER blocks\nboth attackers"), (t_blk + 60, "60 s block\nexpires")):
        ax.axvline(t, color=INK2, lw=1, ls=":")
        ax.text(t + 2, CAP * 0.97, lab, fontsize=7.5, color=INK2, va="top")
    if t_full:
        ax.axvspan(min(t_full), max(t_full), color=C[7], alpha=0.12, lw=0)
        ax.text(max(t_full) + 2, CAP * 1.03, "FEVER table full: new benign flows refused", fontsize=7.5, color=C[7])
    ax.set_xlim(0, DUR)
    ax.set_ylim(0, CAP * 1.12)
    ax.set_xlabel("time (s); attack from 50 s")
    ax.set_ylabel("entries in s11")
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=4)
    ax.set_title(f"Why FEVER harms more than the baselines under A2 (testbed, seed {seed})")
    save(fig, "fig16_a2_block_expiry")


def main():
    only = set(sys.argv[1:])
    if "--v5" in only:
        only.discard("--v5")
        use_v5()
        if "--pub" in only:
            only.discard("--pub")
            published_only()
        os.makedirs(OUT, exist_ok=True)
        want = lambda n: not only or n in only  # noqa: E731
        for n, f in (("01", fig01), ("02", fig02), ("04", fig04), ("10", fig10), ("07", fig07), ("16", fig16)):
            if want(n):
                f()
        df = per_run()
        for n, f in (("03", fig03), ("05", fig05), ("06", fig06), ("08", fig08), ("15", fig15)):
            if want(n):
                f(df)
        return
    os.makedirs(OUT, exist_ok=True)
    want = lambda n: not only or n in only  # noqa: E731
    if want("01"):
        fig01()
    if want("02"):
        fig02()
    if want("04"):
        fig04()
    if want("10"):
        fig10()
    if only & {"03", "05", "06", "08"} or not only:
        df = per_run()
        for n, f in (("03", fig03), ("05", fig05), ("06", fig06), ("08", fig08)):
            if want(n):
                f(df)
    if want("07"):
        fig07()
    if want("09"):
        fig09()
    if want("11"):
        fig11()
    if want("12"):
        fig12()
    if want("13"):
        fig13("fpr0.1")
    if want("14"):
        fig13("paper")


if __name__ == "__main__":
    main()
