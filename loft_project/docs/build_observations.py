"""Builds docs/fever_observations.pdf: a short summary of observations from the final testbed campaign,
for the supervisor. Every number comes from committed results: results/testbed_prereg_final/report.md,
tests.csv and paper/*.tex, and results/tbfl (federation and detection).

    ~/.venvs/loft/bin/python docs/build_observations.py
"""
import csv
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

RES = "results/testbed_prereg_final"
FIG = f"{RES}/paper"
OUT = "docs/fever_observations.pdf"
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")

S = {
    "title": ParagraphStyle("title", fontName="LS-B", fontSize=15, leading=19, alignment=1, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="LS", fontSize=10, leading=13, alignment=1, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="LS-B", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="LS-BI", fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="LS", fontSize=10, leading=13.4, spaceAfter=5, alignment=4),
    "cap": ParagraphStyle("cap", fontName="LS", fontSize=9, leading=11.5, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="LS", fontSize=8.8, leading=10.8),
    "note": ParagraphStyle("note", fontName="LS", fontSize=8.5, leading=10.8, spaceAfter=10),
}
W = A4[0] - 40 * mm


def P(t, s="p"):
    return Paragraph(t, S[s])


def items(xs):
    return ListFlowable([ListItem(P(x), leftIndent=14) for x in xs],
                        bulletType="1", bulletFormat="(%s)", leftIndent=20, bulletFontName="LS",
                        bulletFontSize=10)


def bullets(xs):
    return ListFlowable([ListItem(P(x), leftIndent=10) for x in xs], bulletType="bullet", start="–",
                        leftIndent=14, bulletFontName="LS", bulletFontSize=10)


def table(rows, widths, caption, note=None):
    t = Table([[P(c, "cell") for c in r] for r in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    out = [P(caption, "cap"), t]
    if note:
        out.append(Spacer(1, 3))
        out.append(P(note, "note"))
    else:
        out.append(Spacer(1, 10))
    return KeepTogether(out)


def figure(name, caption, width=W, head=()):
    from PIL import Image as PI
    path = f"{FIG}/{name}.png"
    w, h = PI.open(path).size
    img = Image(path, width=width, height=width * h / w)
    img.hAlign = "CENTER"
    return KeepTogether(list(head) + [img, P(caption, "cap")])


def explain(why, axes, marks, trends, exceptions, recap):
    """The six points every plot is explained by."""
    lab = [("Why this plot", why), ("Axes", axes), ("Bars and lines", marks), ("Trends", trends),
           ("Exceptions", exceptions), ("Recap", recap)]
    return [P(f"<i>{k}.</i> {v}") for k, v in lab]


# Table 1 from tests.csv: one cell per hypothesis and comparator.
T = list(csv.DictReader(open(f"{RES}/tests.csv")))
COMP = [("ftmaster", "FTMaster"), ("ftop", "FTOP"), ("ftodefender", "FTODefender"), ("flora", "FloRa"),
        ("dms-btt-h1", "DMS-BTT"), ("rdefender", "rDefender")]
HROWS = [("H1", "T1B", "Harm"), ("H2", "T1B", "Attack occupancy"), ("H3", "T1B", "New-connection success"),
         ("H4", "T1B", "Occupancy, pooled baselines"), ("H5", "T1B", "Occupancy, Slow and EVX"),
         ("H5", "UHt", "Occupancy, unseen trace")]


def cell(h, tr, c):
    for r in T:
        if r["hypothesis"] == h and r["trace"] == tr and r["comparator"] in (c, c + "-pool"):
            return f"{'yes' if r['supported'] == 'True' else 'no'} ({r['wins']}/{r['n']})"
    return "–"


t1 = [["Hypothesis", "Trace"] + [n for _, n in COMP]]
t1 += [[f"{h} {lab}", tr] + [cell(h, tr, c) for c, _ in COMP] for h, tr, lab in HROWS]
h6 = next(r for r in T if r["hypothesis"] == "H6")
supported = sum(r["supported"] == "True" for r in T)

story = [
    P("FEVER against LOFT attacks: summary of observations from the final testbed campaign", "title"),
    P("16 November 2026", "sub"),

    P("1. What was evaluated", "h1"),
    P("FEVER combines a detector trained by lossless (histogram-based) federated XGBoost across three SDN "
      "controllers with an eviction and ingress-blocking response (EvictBlock). The controllers C1, C2 and C3 "
      "each trained on their own traffic trace and their own two attacks; no rows or labels left a "
      "controller. FEVER was compared with six published defenses, reimplemented from their papers: FTMaster, "
      "FTOP, FTODefender, FloRa, DMS-BTT and rDefender."),
    P("The campaign ran on a Mininet and Ryu testbed with a three-switch tree, where the core switch s11 "
      "overflows. Two test traces were used, T1B and UHt (a trace no controller trained on), and seven "
      "attacks: G2, Spoof, Pulse, Mimic, Aware, Slow and EVX. It comprised 468 runs of 300 s with 3 to 5 seeds "
      "per cell, plus 64 reruns of DMS-BTT after a correction (amendment 3). Hypotheses H1 to H7 were "
      "preregistered and tested with one-sided paired sign tests, Holm-corrected over 33 tests."),
    P("Every attack follows the low-rate flow-table overflow pattern of DMS-BTT: in each burst the attacker "
      "re-sends packets on all its live flows, so that they are refreshed before the switch's 10 s idle "
      "timeout, and opens S new flows, until it holds M flows. Bursts are sent at 1,500 packets/s and are "
      "separated by a random gap t1. Two attackers take part, h5 on access switch s12 and h6 on s13, and "
      "start 50 s into the run. Table 1 gives each attack's parameters."),
    table([["Attack", "Source addresses", "S (flows)", "t1 (s)", "M (flows)", "Packets per refresh",
            "Packet size", "Other", "Trained on by"],
           ["G2", "attacker's own", "100", "5.5–9.0", "1,700", "1", "64 B", "–", "C2"],
           ["Spoof", "random, spoofed", "100", "5.5–9.0", "1,700", "1", "64 B", "–", "C2"],
           ["Pulse", "attacker's own", "300", "5.0–8.0", "1,700", "1", "64 B", "60 s on, 30 s off; new flows "
            "each on period", "C3"],
           ["Mimic", "pool of 256", "100", "6.0–9.5", "1,700", "1–3", "benign", "–", "C1"],
           ["Aware", "pool of 256", "100", "2.0–3.0", "1,700", "1–3", "benign", "tuned against our earlier "
            "defenses", "none"],
           ["Slow", "random, spoofed", "45", "8.0–9.8", "1,700", "1–2", "benign", "–", "none"],
           ["EVX", "attacker's own", "100", "5.5–9.0", "628", "1", "64 B", "kept below FEVER's volume limit",
            "none"]],
          [14 * mm, 23 * mm, 12 * mm, 14 * mm, 13 * mm, 15 * mm, 13 * mm, W - 128 * mm, 24 * mm],
          "Table 1. The seven attacks (per attacker; two attackers).",
          "S: new flows per burst. t1: gap between bursts, uniform in the range. M: live flows held per "
          "attacker. Pool of 256: addresses drawn from one /24 outside the network (10.254.x.0/24). Spoofed: "
          "random addresses from 1.0.0.0 to 222.255.255.255, a new one per flow. Benign packet size: drawn "
          "from the benign traffic's size distribution. G2 is DMS-BTT's second parameter group; Spoof and "
          "EVX use its S and t1. "
          "EVX's M is 0.8 times FEVER's lowest per-switch volume limit on T1B (784.5 flows on s12). "
          "Trained on by: the controller whose training data held the attack; none: no controller saw it."),


    figure("fig_t1b", "Fig. 1. Benign flows harmed, attack occupancy and new-connection success on T1B, "
                      "per attack (mean and s.d. over seeds).", width=0.8 * W,
           head=[P("2. Headline result: FEVER against six published defenses on T1B", "h1")]),
    *explain(
        "This is the paper's main comparison and the evidence for its central claim: under the same attacks, "
        "on the same testbed, FEVER protects the flow table and its users better than the published "
        "defenses. It covers H1 to H3, the preregistered tests on harm, occupancy and service, and the "
        "results section starts with it.",
        "The x-axis gives the seven attacks on the T1B trace. The y-axes, one panel each, give: the share of "
        "benign flows harmed (deleted from the table or denied an entry, %); the attack occupancy, the share "
        "of the flow table held by attack entries, averaged over the run's traffic window and over the three "
        "switches (%); and new-connection success, the share of probe connections a benign host could open "
        "during the attack (%).",
        "Each bar is the mean over seeds (3 seeds for G2, Spoof and Pulse; 5 for Mimic, Aware, Slow and EVX), "
        "and the error bar is one standard deviation. The eight bars per attack are no defense (grey), the "
        "six baselines and FEVER (orange, rightmost). FEVER's harm is too small to show as a bar, so its "
        "value is printed above its place.",
        "FEVER harms almost no benign flows (0.00–0.02 % on every attack), while the baselines harm up to "
        "12 % under Aware. On G2, Mimic, Spoof, Pulse and Aware, FEVER holds the attacker to 2–14 % of the "
        "table, against 18–50 % for most baselines. FEVER keeps new-connection success at 97–99 % on G2, "
        "Mimic, Spoof and Pulse, where most baselines fall to 11–41 %. The gap is widest on Mimic and Aware, "
        "the low-rate attacks that use a pool of addresses and benign-size packets.",
        "FTODefender holds G2, Pulse and EVX at about 0.2 % occupancy, lower than FEVER, and also keeps "
        "100 % new-connection success on them. On Slow all eight bars are alike (about 20 % occupancy), so "
        "no method defends it. On EVX FEVER is not better than the baselines (17.7 %, with a large spread), "
        "and on Aware FEVER's new-connection success, 46 %, is far below its value on the other attacks.",
        "FEVER harms fewer benign flows than every baseline and keeps new connections working, and it holds "
        "occupancy lowest on five of the seven attacks. The exceptions are FTODefender on G2, Pulse and EVX, "
        "and the two attacks no method stops well, Slow and EVX."),

    figure("fig_timeline", "Fig. 2. Attack occupancy over time on T1B under Mimic and Aware (median over 5 "
                           "seeds); the dotted line marks the attack's start.",
           head=[P("3. Key plots", "h1"), P("3.1 Attack occupancy over time", "h2")]),
    *explain(
        "Fig. 1 gives averages over the run. This plot shows how FEVER gets them: when the attack takes "
        "hold, when FEVER acts, and whether the table stays clean afterwards. Mimic and Aware are shown "
        "because they are the attacks with the largest margins.",
        "The x-axis is the controller's time in seconds (0 to 310 s); the attack starts at 50 s. The y-axis "
        "is the attack occupancy (%), as in Fig. 1, at each second.",
        "One line per method, each the median over the five seeds: no defense (grey dotted), FTMaster (blue "
        "dashed), FTODefender (yellow dash-dot), DMS-BTT (purple dash-dot) and FEVER (orange, solid). FTOP, "
        "FloRa and rDefender are left out for readability; their averages are in Fig. 1.",
        "Every line rises together once the attack fills the table, from about 63 s. On Mimic, FEVER blocks "
        "the attackers at about 130 s and the occupancy falls to zero by 140 s and stays there; the "
        "baselines keep rising to 54–60 %. On Aware the attack fills faster; FEVER blocks the first attacker "
        "at about 150 s and the second at about 205 s, after which the occupancy is zero. The baselines "
        "climb to about 65 %, the most the two attackers can hold.",
        "Before it blocks, FEVER's line lies on the no-defense line: eviction alone does not keep the "
        "attackers out, and the gain comes from blocking them. DMS-BTT is the only baseline that brings "
        "occupancy down on Aware, from about 64 to 52 % after 235 s. FTODefender stays close to no defense "
        "on both attacks.",
        "FEVER removes the attack from the table once it blocks the attacking hosts, about 80 s after the "
        "attack starts on Mimic and 100–155 s on Aware, and the table stays clean. The baselines evict "
        "attack entries but the attackers refill the table."),

    figure("fig_fl_effect", "Fig. 3. Detector trained on C3's data only against the lossless federated "
                            "detector: offline recall and the testbed outcome on T1B.",
           head=[P("3.2 Effect of federated training", "h2")]),
    *explain(
        "Federated training is the paper's main contribution. This plot isolates it: the same FEVER with "
        "two detectors, one trained on C3's data alone and one trained by lossless federation across C1 to "
        "C3. Three attacks are shown: G2, which C2 trained on and C3's detector also catches because it is "
        "close to C3's own G3; Mimic, which only C1 saw; and Aware, which no controller saw.",
        "The x-axis gives the three attacks. The four panels give the detector's recall on the T1B test rows "
        "(%, offline), and on the testbed the attack occupancy (%), the new-connection success (%) and the "
        "time from the attack's start to the first block of an attacker (s).",
        "Grey bars: detector trained on C3's data only. Orange bars: federated detector (FEVER). Testbed "
        "bars are means over seeds (3 for G2, 5 for Mimic and Aware), with one standard deviation.",
        "On G2 the two detectors agree in every panel. On Mimic the local detector catches 0.2 % of attack "
        "rows and the federated one 60.9 %; on the testbed this blocks the attackers 64 s sooner (80 against "
        "144 s), cuts occupancy from 15.7 to 4.9 % and raises new-connection success from 63 to 98 %. On "
        "Aware recall rises from 0.1 to 25.4 %, occupancy falls from 18.2 to 14.1 % and new-connection "
        "success rises from 35 to 46 %.",
        "Aware's first block is about the same with either detector (92 and 91 s), and its spread is large; "
        "the local detector never blocked in one of five runs, so its bar averages four. Over Mimic and "
        "Aware together the preregistered test of this effect (H6) is not supported: FEVER won 8 of 10 "
        "pairs, Holm p = 0.38.",
        "Federation lets a controller detect an attack only another controller has seen, and on Mimic this "
        "turns into earlier blocking, a cleaner table and working connections. On the attack no controller "
        "saw, the gain is smaller and not significant."),

    figure("fig_ablation", "Fig. 4. FEVER against its four ablations on T1B (mean and s.d. over seeds).",
           head=[P("3.3 Ablation", "h2")]),
    *explain(
        "To show which part of FEVER produces the result, each part is removed in turn and the run "
        "repeated. Reviewers ask whether the federated detector matters, or whether the blocking does all "
        "the work.",
        "The x-axis gives the three attacks used for the ablation (G2, Mimic, Aware). The panels give "
        "benign flows harmed (%), attack occupancy (%) and new-connection success (%), as in Fig. 1.",
        "Five bars per attack: full FEVER (orange) and FEVER without sharing (local detector), without the "
        "volume rule, without the detector (volume rule only) and without ingress blocking (hatched). Means "
        "over 3 seeds for G2 and 5 for Mimic and Aware, with one standard deviation.",
        "Without ingress blocking, occupancy rises to 23–35 % on all three attacks and new-connection "
        "success falls to 11–84 %. Without the volume rule, Aware's occupancy rises from 14.1 to 42.6 % and "
        "its success falls from 46 to 11 %, while G2 and Mimic do not change. Without sharing, Mimic's "
        "occupancy triples (4.9 to 15.7 %). Without the detector, occupancy doubles on G2 and almost triples "
        "on Mimic, because blocks come 35–55 s later.",
        "On Aware, FEVER without the detector does slightly better than full FEVER (occupancy 10.4 against "
        "14.1 %, success 55 against 46 %). Harm is near zero for every variant except without sharing (about "
        "3 % on Mimic and Aware) and without the volume rule (1.5 % on Aware), with large spreads across "
        "seeds.",
        "Every part is needed on at least one attack: ingress blocking everywhere, the volume rule on Aware, "
        "the detector for early blocks on G2 and Mimic, and sharing on Mimic. Blocking gives the largest "
        "single effect, which is why the paper puts its novelty in the federated detector rather than in "
        "the response."),

    P("4. Observations", "h1"),
    items([
        f"<b>The preregistered tests mostly favour FEVER.</b> {supported} of the 33 tests are supported "
        "(Table 2). The DMS-BTT correction of amendment 3 changed no test outcome.",
        "<b>FEVER harms almost no benign flows (Fig. 1).</b> On T1B, FEVER harmed 0.011 % of benign flows on average, "
        "against 1.0 % to 5.2 % for the six baselines. H1 is supported against all six. In the benign-only "
        "runs FEVER harmed no flow and blocked no benign host (H7 passes).",
        "<b>FEVER keeps new connections working.</b> Mean new-connection success during attacks on T1B was "
        "84.2 % with FEVER, against 21.0 % to 45.6 % for the baselines. H3 is supported against all six. "
        "Per attack, FEVER kept 97–99 % success on G2, Spoof, Pulse, Mimic and EVX.",
        "<b>FEVER holds attack occupancy lowest against five of six baselines.</b> On T1B the attacker held "
        "6.8 % of the table under FEVER, against 24.2 % to 35.5 % under the baselines. FTODefender is the "
        "exception: it holds G2, Pulse and EVX lower than FEVER (0.3, 0.2 and 0.2 % against 4.8, 1.9 and "
        "17.7 %), so H2 is not supported against it.",
        "<b>The largest margins are on the low-rate attacks Mimic and Aware.</b> Occupancy under FEVER was "
        "4.9 and 14.1 %, against 33–49 % for the baselines. FEVER also beat every baseline retrained on the "
        "three controllers' data pooled (H4: 9.5 % against 20.6–39.1 %).",
        "<b>FEVER does not defend against Slow and EVX.</b> On these two attacks no H5 test on T1B is "
        "supported. Slow is defended by no method (about 20 % occupancy for all). EVX defeats FEVER (17.7 %), "
        "while FTODefender, DMS-BTT and FloRa hold it at 0.2–14.3 %. On UHt, the trace no controller trained on, "
        "FEVER beat FTMaster, DMS-BTT and rDefender on every pair (7.7 % against 37.0–40.6 %).",
        "<b>Federation helps the detector on attacks a controller never saw.</b> Offline, recall on attacks "
        "seen only by another controller rose from 75.8 % (C3 alone) to 90.5 %, and on Mimic from 0.2 % to "
        "60.9 %. This equals pooled XGBoost trained on the raw rows (F1 86.5 against 86.8), at 2.6 GB of "
        "exchanged histograms and 38 s of training (Table 4, Fig. 3).",
        "<b>On the testbed, federation's benefit is clear on Mimic but not significant overall (Fig. 3).</b> With the "
        "federated detector, Mimic attackers were blocked at 80 s instead of 144 s and occupancy fell from "
        f"15.7 to 4.9 %. Over Mimic and Aware, H6 is not supported ({h6['wins']} of {h6['n']} pairs, Holm "
        "p = 0.38).",
        "<b>Each part of FEVER contributes (Fig. 4).</b> Without ingress blocking, occupancy rises to "
        "23–35 % on all three attacks tested. Without the volume rule, Aware rises from 14.1 to 42.6 %. "
        "Without the detector, blocks on G2 and Mimic come 35–55 s later. Without sharing, Mimic rises from "
        "4.9 to 15.7 %.",
        "<b>The baselines are implemented faithfully.</b> Tested as their papers test (on the attacks the "
        "training controller saw), every reimplemented baseline reaches about 99.8 % accuracy, precision, "
        "recall and F1, at or above the values in its paper (Table 3). Over all T1B attacks, FEVER's F1 is "
        "86.8 against 78.5 for each baseline trained on one controller's data.",
        "<b>FEVER is light on the controller.</b> Mean decision time was 20.8 ms, against 35–103 ms for the "
        "baselines, and controller CPU 62 % against 70–78 %. Its memory use was the highest (253 MB against "
        "191–233 MB).",
    ]),

    table(t1, [36 * mm, 11 * mm] + [(W - 47 * mm) / 6] * 6,
          "Table 2. Outcome of the preregistered tests: supported or not (paired wins of FEVER / pairs).",
          "H3 is a non-inferiority test (FEVER's probe success above the comparator's minus 5 points). H4 "
          "compares FEVER with each baseline trained on pooled data, on Mimic and Aware. H5 on UHt was "
          "preregistered against FTMaster, DMS-BTT and rDefender only. H6 (FEVER against FEVER without "
          f"sharing, Mimic and Aware): {h6['wins']}/{h6['n']}, not supported."),

    table([["Method", "Paper: Acc. / Prec. / Rec. / F1", "Ours, attacks seen in training",
            "Ours, all T1B attacks"],
           ["FTMaster", "92.5 / – / 89.5 / 91.6", "99.8 / 99.8 / 99.9 / 99.8", "75.3 / 99.8 / 64.7 / 78.5"],
           ["FTOP", "98.9 / 99.2 / 99.0 / 99.1", "99.8 / 99.8 / 99.9 / 99.8", "75.4 / 99.8 / 64.7 / 78.5"],
           ["FloRa", "99.5 / – / 98.8 / 99.9", "99.8 / 99.8 / 99.9 / 99.9", "75.3 / 99.8 / 64.7 / 78.5"],
           ["DMS-BTT", "92.4 / 92.5 / 83.1 / 87.6", "99.8 / 99.8 / 99.9 / 99.9", "75.4 / 99.8 / 64.7 / 78.5"],
           ["FEVER", "–", "99.8 / 99.7 / 99.9 / 99.8", "83.7 / 99.7 / 76.8 / 86.8"]],
          [22 * mm, 45 * mm, 50 * mm, W - 117 * mm],
          "Table 3. Detection (%) of each classifier: values reported in each paper, and ours on T1B test rows.",
          "Ours: baselines trained on C3's rows at their paper's threshold, FEVER federated. Attacks seen in "
          "training: G3 and Pulse. The papers' values come from their own datasets; FloRa's reported F1 does not agree with its own false-negative rate. FTODefender's scoring ran "
          "out of memory and rDefender has no classifier."),

    table([["Training", "Shared", "Data sent (MB)", "Time (s)", "F1 (%)", "Recall, other controllers (%)",
            "Recall, Mimic (%)"],
           ["C3 only", "nothing", "0", "–", "78.4", "75.8", "0.2"],
           ["FedAvg", "weights", "0.4", "32", "74.7", "70.7", "0.1"],
           ["FedProx", "weights", "0.4", "27", "75.9", "71.4", "1.1"],
           ["Federated XGBoost bagging", "trees", "173", "212", "78.5", "75.8", "0.1"],
           ["Lossless federated XGBoost (FEVER)", "histograms", "2,601", "38", "86.8", "90.5", "60.9"],
           ["Pooled XGBoost", "rows and labels", "27.6", "–", "86.5", "90.5", "61.1"]],
          [52 * mm, 24 * mm, 20 * mm, 14 * mm, 14 * mm, 28 * mm, W - 152 * mm],
          "Table 4. Cost and accuracy of training the detector across the three controllers."),

    KeepTogether([P("5. Where FEVER falls short", "h1"), bullets([
        "Slow is undefended and EVX defeats FEVER; FTODefender holds G2, Pulse and EVX lower than FEVER.",
        "Federation's benefit on the testbed is not significant over Mimic and Aware (H6), only clear on "
        "Mimic.",
        "The detector's false alarms on T1B benign rows are 0.79 %, against the 0.1 % budget its threshold "
        "was set for. It failed its preregistered false-alarm rule and was deployed under an amendment.",
        "Pooling raw data gives the baselines a higher F1 than FEVER at their paper's threshold (90–92 "
        "against 86.8), at 2.6–3.7 % false alarms; at FEVER's false-alarm rule they reach 81–84.",
        "Ingress blocking contributes most of FEVER's occupancy reduction and is not new; the novelty lies "
        "in the federated detector and the evaluation.",
        "Scale is small: one machine, three controllers, 300 s runs, 3 to 5 seeds. The baselines are "
        "reimplementations with documented deviations (for example DMS-BTT's tuned variant and FTODefender's "
        "block rule), and three amendments were made to the preregistration.",
    ])]),

    KeepTogether([P("6. Next steps", "h1"), bullets([
        "Secure aggregation of the exchanged histograms and a threshold set from all three controllers' "
        "benign data (plan drafted: docs/secagg_plan.md).",
        "A time-to-protection experiment: a federation round during an attack, after which the controller "
        "replaces its local detector with the federated one.",
        "The manuscript for NetSoft 2027, framed on the federated detector and the preregistered evaluation, "
        "with the limitations above and the missing related work (MWD-CFM and Tang et al., 2026).",
    ])]),
]

SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                  bottomMargin=18 * mm, title="FEVER: summary of observations").build(story)
print("written", os.path.abspath(OUT))
