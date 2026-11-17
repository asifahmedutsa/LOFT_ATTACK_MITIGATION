"""Builds docs/fever_experiments_results.pdf: the paper's experimental setup and results sections, in
plain journal form. Numbers come from results/testbed_prereg_final (tests.csv, report.md, paper/*.tex)
and results/tbfl; figures from results/testbed_prereg_final/paper. The follow-up studies come from
results/testbed_flash, results/testbed_scale and results/secagg.

    ~/.venvs/loft/bin/python docs/build_results_section.py
"""
import csv
import os
import re

from PIL import Image as PI
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

RES = "results/testbed_prereg_final"
FIG = f"{RES}/paper"
OUT = "docs/fever_experiments_results.pdf"
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")

S = {
    "h1": ParagraphStyle("h1", fontName="LS-B", fontSize=11, leading=14, spaceBefore=10, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="LS-I", fontSize=10.5, leading=13.5, spaceBefore=7, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="LS", fontSize=10.5, leading=14, spaceAfter=5, alignment=4,
                        firstLineIndent=12),
    "cap": ParagraphStyle("cap", fontName="LS", fontSize=9, leading=11.5, alignment=1, spaceBefore=3,
                          spaceAfter=10),
    "tcap": ParagraphStyle("tcap", fontName="LS", fontSize=9, leading=11.5, alignment=1, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="LS", fontSize=8.6, leading=10.4),
    "note": ParagraphStyle("note", fontName="LS", fontSize=8.3, leading=10.4, spaceBefore=3, spaceAfter=10),
}
W = A4[0] - 44 * mm


def P(t, s="p"):
    return Paragraph(t, S[s])


def bullets(xs):
    return ListFlowable([ListItem(P(x), leftIndent=10) for x in xs], bulletType="bullet", start="–",
                        leftIndent=14, bulletFontName="LS", bulletFontSize=10)


def items(xs):
    return ListFlowable([ListItem(P(x), leftIndent=14) for x in xs], bulletType="1", bulletFormat="(%s)",
                        leftIndent=20, bulletFontName="LS", bulletFontSize=10)


def table(rows, widths, caption, note=None, rules=()):
    t = Table([[P(c, "cell") for c in r] for r in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]
                          + [("LINEABOVE", (0, r), (-1, r), 0.4, colors.black) for r in rules]))
    out = [P(caption, "tcap"), t]
    out.append(P(note, "note") if note else Spacer(1, 10))
    return KeepTogether(out)


def figure(name, caption, width=W):
    w, h = PI.open(f"{FIG}/{name}.png").size
    img = Image(f"{FIG}/{name}.png", width=width, height=width * h / w)
    img.hAlign = "CENTER"
    return KeepTogether([img, P(caption, "cap")])


def tex_rows(name):
    """Body rows of one of the paper's booktabs tables."""
    rows = []
    for line in open(f"{FIG}/{name}").read().splitlines():
        if "&" in line and not line.startswith("\\"):
            c = [x.strip() for x in line.rstrip("\\ ").split("&")]
            rows.append([re.sub(r"\$|\\%|\{,\}", lambda m: {"\\%": "%", "{,}": ","}.get(m.group(), ""), x)
                         .replace("--", "–").replace("^", "").replace("{3}", "3") for x in c])
    return rows


# Table 2: hypothesis tests.
T = list(csv.DictReader(open(f"{RES}/tests.csv")))
COMP = [("ftmaster", "FTMaster"), ("ftop", "FTOP"), ("ftodefender", "FTODefender"), ("flora", "FloRa"),
        ("dms-btt-h1", "DMS-BTT"), ("rdefender", "rDefender")]
HROWS = [("H1", "T1B", "H1 Harm"), ("H2", "T1B", "H2 Occupancy"), ("H3", "T1B", "H3 New connections"),
         ("H4", "T1B", "H4 Occupancy, pooled training"), ("H5", "T1B", "H5 Occupancy, Slow and EVX"),
         ("H5", "UHt", "H5 Occupancy, UHt")]


def cell(h, tr, c):
    for r in T:
        if r["hypothesis"] == h and r["trace"] == tr and r["comparator"] in (c, c + "-pool"):
            return f"{'yes' if r['supported'] == 'True' else 'no'} ({r['wins']}/{r['n']})"
    return "–"


t2 = [["Hypothesis", "Trace"] + [n for _, n in COMP]]
t2 += [[lab, tr] + [cell(h, tr, c) for c, _ in COMP] for h, tr, lab in HROWS]
H6 = next(r for r in T if r["hypothesis"] == "H6")
NSUP = sum(r["supported"] == "True" for r in T)

ov = tex_rows("table_overhead.tex")
fc = tex_rows("table_fedcost.tex")
dt = tex_rows("table_detect.tex")
th = tex_rows("table_threshold.tex")
th[0] = ["Model", "Threshold rule", "Threshold", "FA, T1B", "FA, UHt", "Recall", "F1", "Recall, Mimic",
         "Recall, Aware"]
R8 = [i for i, r in enumerate(th) if i > 1 and r[0]]

# Table 6: flash crowds (results/testbed_flash/runs.csv).
FL = list(csv.DictReader(open("results/testbed_flash/runs.csv")))
FLM = [("none", "No defense"), ("fever-fl-ll", "FEVER")] + COMP


def fmean(m, k, d):
    x = [float(r[k]) for r in FL if r["method"] == m]
    return f"{sum(x) / len(x):.{d}f}"


t6 = [["Method", "Harm (%)", "Lost first packets (%)", "New connections (%)", "Benign hosts blocked",
       "Benign deletes/min"]]
t6 += [[n, fmean(m, "benign_harmed_pct", 3), fmean(m, "benign_packet_in_lost_pct", 1),
        fmean(m, "probe_post_success_pct", 1),
        str(int(sum(float(r["hosts_blocked_benign"]) + float(r["ingress_drops"]) for r in FL if r["method"] == m))),
        fmean(m, "benign_deleted_per_min", 1)] for m, n in FLM]

# Table 7: more attackers (results/testbed_scale/report.md, means only).
SC, sec = {}, None
for line in open("results/testbed_scale/report.md"):
    if line.startswith("## "):
        sec = line[3:].strip()
    elif sec in ("G2", "EVX") and line.startswith("| ") and not line.startswith("| Method"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        SC[(sec, c[0], c[1])] = [x.split(" (")[0] for x in c[2:]]
t7 = [["Method", "n", "G2 occupancy (%)", "G2 harm (%)", "G2 attackers blocked", "EVX occupancy (%)",
       "EVX harm (%)", "EVX attackers blocked"]]
for lab in ("No defense", "FEVER", "FTMaster", "FTODefender", "DMS-BTT"):
    first = True
    for n in ("2", "4", "8"):
        if ("G2", lab, n) in SC:
            g, e = SC[("G2", lab, n)], SC[("EVX", lab, n)]
            t7.append([lab if first else "", n, g[0], g[1], g[4], e[0], e[1], e[4]])
            first = False
R7 = [i for i, r in enumerate(t7) if i > 1 and r[0]]

keep = [0] + [i for i, r in enumerate(dt) if i and (r[2].startswith("0.5") or r[0] == "FEVER")]
dt = [dt[i] for i in keep]
dt[0] = ["Method", "Training", "Threshold", "Test attacks", "Acc.", "Prec.", "Rec.", "F1", "FA"]

# Short tables: the columns the text uses.
fc_s = [["Training", "Data sent (MB)", "Time (s)", "F1 (%)", "Recall, Mimic (%)"]] + \
       [[r[0], r[3], r[4], r[5], r[7]] for r in fc[1:] if "secure" not in r[0]]
t6_s = [[r[0], r[1], r[3], r[4]] for r in t6]
t6_s[0] = ["Method", "Harm (%)", "New connections (%)", "Benign hosts blocked"]
t7_s = [["Method", "Attackers", "G2 occupancy (%)", "EVX occupancy (%)", "Attackers blocked, G2", "Attackers blocked, EVX"]]
t7_s += [[r[0], r[1], r[2], r[5], r[4], r[7]] for r in t7[1:]]

story = [
    P("5. Experimental setup", "h1"),
    P("We use a Mininet testbed with Open vSwitch and a Ryu controller. The network is a tree of three "
      "switches: a core switch s11 and two access switches. Each table holds 3,500 entries with an idle "
      "timeout of 10 s, and the controller reads the flow statistics every second. Four hosts replay real "
      "traffic, two attackers start at 50 s, and one host opens a new connection every 0.5 s to measure "
      "the service a new flow receives. Each run lasts 300 s."),
    P("Benign traffic comes from two captures: T1B (bigFlows) and UHt (univ2, which no controller trained "
      "on). Three controllers, C1 to C3, each record their own training data with two attacks. FEVER's "
      "detector is trained across the three by lossless federated XGBoost: the controllers exchange only "
      "histogram sums, never rows or labels. FEVER evicts the entries its detector flags and blocks a "
      "host at its access port when its evictions or its share of the table are far above the other "
      "hosts'."),
    P("Table 1 lists the seven attacks. All keep their flows alive by sending a packet on each before the "
      "idle timeout. Aware, Slow and EVX were seen by no controller in training."),
    table([["Attack", "Source addresses", "Flows per attacker", "Gap between bursts (s)", "Seen in training by"],
           ["G2", "own", "1,700", "5.5–9.0", "C2"],
           ["Spoof", "spoofed", "1,700", "5.5–9.0", "C2"],
           ["Pulse", "own, on 60 s / off 30 s", "1,700", "5.0–8.0", "C3"],
           ["Mimic", "pool of 256, benign sizes", "1,700", "6.0–9.5", "C1"],
           ["Aware", "pool of 256, benign sizes", "1,700", "2.0–3.0", "none"],
           ["Slow", "spoofed, benign sizes", "1,700", "8.0–9.8", "none"],
           ["EVX", "own, below FEVER's volume limit", "628", "5.5–9.0", "none"]],
          [16 * mm, 55 * mm, 27 * mm, 33 * mm, W - 131 * mm],
          "Table 1. The attacks (two attackers per run)."),
    P("FEVER is compared with no defense and six published defenses that we reimplemented: FTMaster, FTOP, "
      "FTODefender, FloRa, DMS-BTT and rDefender. We measure three things: <i>harm</i>, the share of benign "
      "flows that are refused or lose packets; <i>occupancy</i>, the share of the table held by the "
      "attackers; and <i>new-connection success</i>. There are 532 runs with three to five seeds each. The "
      "hypotheses and tests (one-sided sign tests, Holm-corrected over 33 tests) were fixed before the runs."),

    P("6. Results", "h1"),
    P("6.1. FEVER against published defenses", "h2"),
    P(f"On average FEVER did best on all three measures (Fig. 1), and {NSUP} of the 33 tests are supported (Table 2)."),
    bullets([
        "<b>Harm:</b> FEVER harmed 0.011 % of benign flows; the baselines harmed 1.0 % to 5.2 %.",
        "<b>New connections:</b> 84 % succeeded under FEVER, 21 % to 46 % under the baselines.",
        "<b>Occupancy:</b> the attackers held 6.8 % of the table under FEVER, 24 % to 36 % under the "
        "baselines. The gap is largest under Mimic and Aware (5 % and 14 % against 33 % to 49 %).",
        "<b>Exceptions:</b> FTODefender held G2, Pulse and EVX lower than FEVER, at the cost of 3.4 % harm. "
        "No method stopped Slow (about 20 % for all), and two EVX attackers stayed below FEVER's volume "
        "limit (17.7 %).",
        "<b>Unseen capture:</b> on UHt, FEVER held the attackers to 7.7 % against 37 % to 41 %.",
    ]),
    figure("fig_t1b", "Fig. 1. Harm, attack occupancy and new-connection success on T1B (mean and standard "
                      "deviation over seeds).", width=0.86 * W),
    table(t2, [34 * mm, 10 * mm] + [(W - 44 * mm) / 6] * 6,
          "Table 2. Hypothesis tests: supported or not (wins of FEVER / pairs)."),

    P("6.2. Occupancy over time", "h2"),
    P("Under the baselines the attackers refill the table as fast as it is cleaned, and it reaches 54 % to "
      "65 % (Fig. 2). Under FEVER the attack entries disappear once the attackers are blocked: after about "
      "80 s under Mimic and after 100 s to 155 s under Aware."),
    figure("fig_timeline", "Fig. 2. Attack occupancy over time on T1B (median over five seeds)."),

    P("6.3. Effect of federated training", "h2"),
    P("Federated training lets a controller detect an attack that only another controller has seen. On "
      "Mimic, recall rose from 0.2 % (C3's data only) to 61 %; on the testbed the attackers were blocked "
      "64 s earlier and the occupancy fell from 15.7 % to 4.9 % (Fig. 3). Under Aware the gain was smaller, "
      f"so the test over Mimic and Aware together is not supported ({H6['wins']} of 10 pairs)."),
    P("FedAvg, FedProx and federated tree bagging do not help on unseen attacks (Table 3). Lossless "
      "federated XGBoost matches training on the pooled data, for 2.6 GB of exchanged sums and 38 s."),
    figure("fig_fl_effect", "Fig. 3. Detector trained on C3 only against the federated detector."),
    table(fc_s, [70 * mm] + [(W - 70 * mm) / 4] * 4,
          "Table 3. Cost and accuracy of training the detector over the three controllers."),

    P("6.4. Ablation", "h2"),
    P("Each part of FEVER matters on at least one attack (Fig. 4). Ingress blocking matters most: without "
      "it the occupancy rose to 23 % to 35 %. Without the volume rule, Aware rose from 14 % to 43 %. "
      "Without the detector, blocks came 35 s to 55 s later. Without federated training, Mimic rose from "
      "4.9 % to 15.7 %."),
    figure("fig_ablation", "Fig. 4. FEVER with each part removed, on T1B."),

    P("6.5. Detection and overhead", "h2"),
    P("On the attacks their training data contained, the reimplemented classifiers reach about 99.8 % "
      "accuracy, in line with their papers. Over all attacks they reach an F1 of 78.5 %, against 86.8 % for "
      "FEVER's federated detector. FEVER was also the fastest (20.8 ms per decision) and used the least "
      "controller CPU (62 %), but the most memory (253 MB)."),

    P("6.6. Benign flash crowds", "h2"),
    P("We added three sudden crowds of new benign flows to each run, with no attacker. No method blocked a "
      "benign host, and FEVER harmed no benign flow (Table 4). FTODefender deleted many benign entries and "
      "cut new-connection success to 21 %."),
    table(t6_s, [40 * mm] + [(W - 40 * mm) / 3] * 3,
          "Table 4. Benign flash crowds on T1B (mean over three seeds; blocks are totals)."),

    P("6.7. More colluding attackers", "h2"),
    P("With four and eight attackers, FEVER still blocked every G2 attacker and held the table below "
      "FTMaster and DMS-BTT in all paired runs (Table 5). EVX attackers, which slip past FEVER's volume "
      "rule when there are two, were caught by the eviction rule when there were four or more (32 of 36). "
      "With eight attackers, blocks came later because the controller was near its limit."),
    table(t7_s, [27 * mm, 18 * mm] + [(W - 45 * mm) / 4] * 4,
          "Table 5. G2 and EVX with more attackers on T1B (mean over seeds).", rules=R7),

    P("6.8. Summary of findings", "h2"),
    items([
        "<b>Benign traffic is protected best under FEVER.</b> FEVER harmed 0.011 % of benign flows, against "
        "1.0 % to 5.2 % for the six published defenses, and kept 84 % of new connections working, against "
        "21 % to 46 %. Both results are supported against every baseline.",
        "<b>The attackers hold the smallest share of the table under FEVER against five of six "
        "baselines.</b> They held 6.8 % of the table under FEVER and 24 % to 36 % under the baselines. "
        "FTODefender held G2, Pulse and EVX lower (about 0.2 %), but harmed 3.4 % of benign flows.",
        "<b>The gain is largest on attacks that imitate benign traffic.</b> Under Mimic and Aware FEVER held "
        "the attackers to 4.9 % and 14.1 %, against 33 % to 49 %. It stayed ahead of baselines trained on "
        "the pooled data of all three controllers (9.5 % against 21 % to 39 %) and on the UHt capture no "
        "controller trained on (7.7 % against 37 % to 41 %).",
        "<b>Federated training detects attacks that only another controller has seen.</b> Recall on such "
        "attacks rose from 75.8 % to 90.5 %, and on Mimic from 0.2 % to 61 %, without any rows or labels "
        "leaving a controller. On the testbed, Mimic attackers were blocked 64 s earlier and their share of "
        "the table fell from 15.7 % to 4.9 %. FedAvg, FedProx and federated bagging gave no such gain; "
        "lossless federated XGBoost matched pooled training for 2.6 GB of exchanged sums and 38 s.",
        "<b>Ingress blocking is the most important part of FEVER.</b> Without it the attackers kept 23 % to "
        "35 % of the table. The volume rule is needed against Aware, where the attackers' share rose from 14 % "
        "to 43 % without it, and "
        "the detector makes blocks come 35 s to 55 s earlier.",
        "<b>FEVER does not block benign hosts and copes with more attackers.</b> Under benign flash crowds "
        "no method blocked a benign host and FEVER harmed no benign flow. With four and eight attackers, "
        "FEVER blocked every G2 attacker, held the table below FTMaster and DMS-BTT in all paired runs, and "
        "caught 32 of 36 EVX attackers.",
        "<b>FEVER is the lightest defense on the controller.</b> It took 20.8 ms per decision, close to no "
        "defense (19.4 ms) and faster than every baseline, and used the least CPU (62 %), at the price of "
        "the largest memory use (253 MB).",
        "<b>Two attacks remain open.</b> No method stopped Slow, which left about 20 % of the table to the "
        "attackers under every method, and two EVX attackers stayed below FEVER's volume limit (17.7 %).",
    ]),
]

SimpleDocTemplate(OUT, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm,
                  bottomMargin=20 * mm, title="Experimental setup and results").build(story)
print("written", os.path.abspath(OUT))
