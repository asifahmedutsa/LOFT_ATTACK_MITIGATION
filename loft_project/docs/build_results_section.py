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
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

story = [
    P("5. Experimental setup", "h1"),

    P("5.1. Testbed", "h2"),
    P("All experiments run on a Mininet testbed with Open vSwitch switches and a Ryu controller. The "
      "network is a three-switch tree: a core switch s11 and two access switches, s12 and s13. Each switch "
      "holds at most 3,500 flow entries with an idle timeout of 10 s, and the controller polls flow "
      "statistics every second. Four benign hosts replay real traffic, and two attackers, h5 on s12 and h6 "
      "on s13, start at 50 s. A probe host opens new connections throughout the run to measure the service "
      "a new benign flow receives. Each run lasts 300 s."),

    P("5.2. Traffic and training", "h2"),
    P("Benign traffic comes from two packet captures. T1B is a part of bigFlows replayed at 600 packets/s, "
      "and UHt is part 6 of univ2 replayed at 1,000 packets/s. Three controllers hold their own training "
      "recordings from the testbed: C1 on univ2 with the attacks G1 and Mimic, C2 on univ2 with G2 and "
      "Spoof, and C3 on bigFlows with G3 and Pulse. No controller trained on the univ2 part used in UHt."),
    P("FEVER's detector is trained by lossless federated XGBoost over the three controllers (300 trees, "
      "depth 6, 256 bins per feature). For every tree node the controllers exchange only their per-bin "
      "sums of gradients and hessians; no row or label leaves a controller. The decision threshold gives "
      "0.1 % false alarms on C3's benign validation runs. FEVER evicts the entries its detector flags and "
      "blocks a host at its access port once its evictions or its share of the table exceed fixed limits."),

    P("5.3. Attacks", "h2"),
    P("All attacks follow the low-rate flow table overflow pattern used by DMS-BTT. In each burst the "
      "attacker re-sends packets on its live flows, refreshing them before the idle timeout, and opens S "
      "new flows until it holds M flows. Bursts are sent at 1,500 packets/s with a random gap t1 between "
      "them. Table 1 lists the seven attacks. Aware, Slow and EVX were seen by no controller in training; "
      "EVX keeps each attacker below FEVER's volume limit."),
    table([["Attack", "Source addresses", "S", "t1 (s)", "M", "Packets per refresh", "Packet size",
            "Other", "Trained on by"],
           ["G2", "own", "100", "5.5–9.0", "1,700", "1", "64 B", "–", "C2"],
           ["Spoof", "spoofed", "100", "5.5–9.0", "1,700", "1", "64 B", "–", "C2"],
           ["Pulse", "own", "300", "5.0–8.0", "1,700", "1", "64 B", "60 s on, 30 s off", "C3"],
           ["Mimic", "pool of 256", "100", "6.0–9.5", "1,700", "1–3", "benign", "–", "C1"],
           ["Aware", "pool of 256", "100", "2.0–3.0", "1,700", "1–3", "benign", "–", "none"],
           ["Slow", "spoofed", "45", "8.0–9.8", "1,700", "1–2", "benign", "–", "none"],
           ["EVX", "own", "100", "5.5–9.0", "628", "1", "64 B", "below volume limit", "none"]],
          [14 * mm, 22 * mm, 10 * mm, 15 * mm, 12 * mm, 17 * mm, 14 * mm, W - 128 * mm, 24 * mm],
          "Table 1. Attack parameters (per attacker).",
          "S: new flows per burst; t1: gap between bursts; M: flows held per attacker; benign: packet sizes "
          "drawn from the benign traffic."),

    P("5.4. Compared methods", "h2"),
    P("FEVER is compared with no defense and with six published defenses, reimplemented from their papers: "
      "FTMaster, FTOP, FTODefender, FloRa, DMS-BTT and rDefender. The classifiers of the learning-based "
      "defenses are trained on C3's recordings, since each paper trains on one network. For a comparison at "
      "equal data, they are also trained on the pooled recordings of C1 to C3. Four ablations of FEVER "
      "remove, in turn, the federated training (detector trained on C3 only), the volume rule, the detector, "
      "and ingress blocking."),

    P("5.5. Metrics", "h2"),
    P("Benign harm is the share of benign flows refused at least once, never installed, dropped by a rule, "
      "or whose first packet was lost. Attack occupancy is the share of the flow table held by attack "
      "entries, averaged over the traffic window and the three switches. New-connection success is the "
      "share of probe connections that succeed after the attack starts. We also report the time from the "
      "attack's start to the first block of an attacker, the controller's decision time, CPU and memory, "
      "and the number of Packet-In messages. Detectors are scored offline by accuracy, precision, recall, "
      "F1 and false alarms on the T1B test recordings."),

    P("5.6. Procedure", "h2"),
    P("Each combination of trace, attack and method runs with three seeds (G2, Spoof, Pulse and all UHt "
      "cells) or five seeds (Mimic, Aware, Slow and EVX), 532 runs in total. The hypotheses, measures and "
      "tests were fixed before the runs. Each hypothesis is tested by a one-sided sign test over seed-paired "
      "runs, with Holm's correction over the 33 tests at a level of 0.05. Two further studies, each fixed "
      "in advance in the same way, were run afterwards on T1B: benign flash crowds without an attacker (24 "
      "runs, seeds 4165 to 4167) and four or eight colluding attackers (54 runs, seeds 4184 to 4186)."),

    P("6. Results", "h1"),

    P("6.1. Comparison with published defenses", "h2"),
    P("Fig. 1 compares the eight methods on T1B and Table 2 gives the outcome of the hypothesis tests; "
      f"{NSUP} of the 33 tests are supported. FEVER harmed 0.011 % of benign flows on average, against 1.0 % "
      "to 5.2 % for the baselines, and harmed none in the runs without an attack. It kept new-connection "
      "success at 84.2 % on average and at 97 % to 99 % on G2, Spoof, Pulse and Mimic, where most baselines "
      "fell to between 11 % and 41 %. The attacker held 6.8 % of the table under FEVER and 24.2 % to 35.5 % "
      "under the baselines."),
    P("The largest differences occur under Mimic and Aware, which use a pool of addresses and benign packet "
      "sizes: FEVER held them to 4.9 % and 14.1 %, against 33 % to 49 % for the baselines. FEVER also held a "
      "lower occupancy than every baseline trained on the pooled data (9.5 % against 20.6 % to 39.1 %). "
      "FTODefender held G2, Pulse and EVX lower than FEVER, at about 0.2 %, so FEVER's occupancy is not "
      "lower than FTODefender's overall. No method defended against Slow, where every method left about "
      "20 % of the table to the attacker, and EVX evaded FEVER's volume rule (17.7 %). On UHt, FEVER held "
      "the attacker to 7.7 % against 37.0 % to 40.6 % for FTMaster, DMS-BTT and rDefender."),
    figure("fig_t1b", "Fig. 1. Benign flows harmed, attack occupancy and new-connection success on T1B "
                      "(mean and standard deviation over seeds).", width=0.86 * W),
    table(t2, [34 * mm, 10 * mm] + [(W - 44 * mm) / 6] * 6,
          "Table 2. Outcome of the hypothesis tests (wins of FEVER / pairs).",
          "H3 is a non-inferiority test with a margin of 5 points. H5 on UHt covers FTMaster, DMS-BTT and "
          f"rDefender. H6, FEVER against FEVER trained on C3 only on Mimic and Aware: {H6['wins']}/{H6['n']}, "
          "not supported."),

    P("6.2. Occupancy over time", "h2"),
    P("Fig. 2 shows the attack occupancy over time under Mimic and Aware. Until FEVER blocks the attackers "
      "its curve follows the curve without defense, so eviction alone does not hold the attack back. Under "
      "Mimic FEVER blocked both attackers about 80 s after the attack started and the occupancy fell to "
      "zero within 10 s. Under Aware the two attackers were blocked about 100 s and 155 s after the start. "
      "The baselines kept evicting attack entries, but the attackers refilled the table, which reached "
      "54 % to 60 % under Mimic and about 65 % under Aware. DMS-BTT was the only baseline that lowered the "
      "occupancy under Aware, to about 52 % after 235 s."),
    figure("fig_timeline", "Fig. 2. Attack occupancy over time on T1B (median over five seeds). The dotted "
                           "line marks the start of the attack."),

    P("6.3. Effect of federated training", "h2"),
    P("Fig. 3 compares FEVER with its detector trained on C3's recordings only. Offline, federated training "
      "raised the recall on attacks seen only by another controller from 75.8 % to 90.5 %, and on Mimic "
      "from 0.2 % to 60.9 %. On the testbed this blocked the Mimic attackers 64 s earlier, lowered the "
      "occupancy from 15.7 % to 4.9 % and raised new-connection success from 63 % to 98 %. Under G2, which "
      "C3's detector already recognises, both detectors behave alike. Under Aware the gain was smaller "
      f"(14.1 % against 18.2 %), and over Mimic and Aware together the test H6 is not supported ({H6['wins']} "
      "of 10 pairs, p = 0.38 after correction)."),
    P("Table 3 compares federated training schemes on the same data. FedAvg, FedProx and federated bagging "
      "of XGBoost trees gain nothing over local training on the attacks a controller did not see. Lossless "
      "federated XGBoost matches XGBoost trained on the pooled rows, at the cost of 2.6 GB of exchanged "
      "histograms and 38 s of training. Its version with secure aggregation (Section 6.9) gives the same "
      "detector."),
    figure("fig_fl_effect", "Fig. 3. Detector trained on C3 only against the federated detector: offline "
                            "recall and testbed outcome on T1B."),
    table([["Training", "Shared", "Rounds", "Data (MB)", "Time (s)", "F1", "Recall, other ctrl.",
            "Recall, Mimic"]] + [r for r in fc[1:]],
          [50 * mm, 23 * mm, 13 * mm, 17 * mm, 14 * mm, 12 * mm, 21 * mm, W - 150 * mm],
          "Table 3. Cost and accuracy (%) of training the detector over the three controllers."),

    P("6.4. Ablation", "h2"),
    P("Fig. 4 shows FEVER with each part removed. Without ingress blocking the occupancy rose to 23 % to "
      "35 % under all three attacks. Without the volume rule it rose from 14.1 % to 42.6 % under Aware, "
      "while G2 and Mimic were unaffected. Without the detector the first block came 35 s to 55 s later "
      "under G2 and Mimic and the occupancy doubled. Without federated training the occupancy under Mimic "
      "rose from 4.9 % to 15.7 %. Under Aware, FEVER without the detector did slightly better than full "
      "FEVER (10.4 % against 14.1 %)."),
    figure("fig_ablation", "Fig. 4. FEVER and its ablations on T1B (mean and standard deviation over seeds)."),

    P("6.5. Detection accuracy", "h2"),
    P("Table 4 scores each classifier on the T1B test recordings. On the attacks the training controller saw "
      "(G3 and Pulse), every reimplemented classifier reaches about 99.8 % on all four measures, at or above "
      "the values reported in its paper. Over all attacks, the classifiers trained on C3 alone reach an F1 "
      "of 78.5 %, since they miss Mimic, Slow and Aware, while FEVER's federated detector reaches 86.8 %. "
      "Trained on the pooled rows, the baselines reach 90.3 % to 91.9 %, with 2.6 % to 3.7 % false alarms "
      "against FEVER's 0.79 %."),
    table(dt, [20 * mm, 27 * mm, 21 * mm, 19 * mm] + [(W - 87 * mm) / 5] * 5,
          "Table 4. Detection on the T1B test recordings (%).",
          "FA: false alarms on benign-only recordings. FTODefender could not be scored (out of memory); "
          "rDefender has no classifier.",
          rules=[5, 9, 10]),

    P("6.6. Overhead", "h2"),
    P("Table 5 gives the controller's cost over all T1B runs. FEVER took 20.8 ms per decision, close to no "
      "defense and below every baseline, and used the least CPU. It used the most memory, 253 MB, for its "
      "300-tree model."),
    table([["Method", "Decision (ms)", "CPU (%)", "Memory (MB)", "Packet-In (10³)"]] + ov[1:],
          [32 * mm] + [(W - 32 * mm) / 4] * 4,
          "Table 5. Controller overhead on T1B, mean (standard deviation) per run."),

    P("6.7. Benign flash crowds", "h2"),
    P("A defense that limits each host's share of the table may block a benign host whose traffic rises "
      "suddenly. We added to the T1B replay three crowds of 12 s per run, each at eight times the replay's "
      "own rate of new flows, with sources spread over the four benign hosts and no attacker. The burst "
      "size was chosen before the runs as the smallest of four, six and eight times that filled 90 % of the "
      "core switch's table; none did, and the largest crowd reached 2,625 entries, so the study ran at eight "
      "times. Table 6 gives the results. No method blocked a benign host. FEVER harmed no benign flow and "
      "kept 57.2 % of new connections working, against 57.9 % without a defense; in every method about "
      "a fifth of the first packets were lost, which comes from the load on the controller and not from the "
      "defense. FTODefender deleted 182 benign entries a minute and cut new-connection success to 20.6 %."),
    table(t6, [30 * mm] + [(W - 30 * mm) / 5] * 5,
          "Table 6. Benign flash crowds on T1B, mean over three seeds (blocks are totals)."),

    P("6.8. More colluding attackers", "h2"),
    P("Table 7 repeats G2 and EVX with four and eight attackers, each on its own host and split between the "
      "two access switches, beside the campaign's two. Under G2, FEVER's occupancy stayed below FTMaster's and "
      "DMS-BTT's in all six seed-paired runs (p = 0.047 after Holm's correction for each), but not below "
      "FTODefender's, which stayed near 0.3 % at every n at a harm of about 0.25 %. FEVER blocked every "
      "attacker in all twelve G2 runs and no benign host in any run. Under EVX each attacker keeps below "
      "FEVER's volume limit, which let two attackers pass in the campaign. With four or more, the attackers "
      "together fill the core table beyond the level at which FEVER starts to evict, its detector's "
      "evictions fall on the attackers, and the eviction rule blocked 32 of the 36 EVX attackers. At eight "
      "attackers the controller ran at about 80 % CPU, blocks came 50 s to 190 s after the attack started, "
      "and FEVER's harm rose to 0.9 % under G2 and 2.0 % under EVX, against 16.3 % and 12.1 % without a "
      "defense."),
    table(t7, [27 * mm, 8 * mm] + [(W - 35 * mm) / 6] * 6,
          "Table 7. G2 and EVX with n attackers on T1B, mean over seeds (n = 2 from the campaign).",
          rules=R7),

    P("6.9. Secure aggregation and a federated threshold", "h2"),
    P("In FEVER's federated training each controller sends the gradient and hessian sums of its rows, per "
      "histogram bin, in the clear, and these sums describe its traffic. We added the pairwise additive "
      "masks of Bonawitz et al. (2017). Each pair of controllers agrees on a key by X25519 key exchange; for "
      "every message, each controller adds a ChaCha20 stream per pair key to its sums, with opposite signs "
      "within a pair, so that the masks cancel and the aggregator learns only the total. The sums are "
      "encoded in fixed point (scale 2<super>40</super>, modulo 2<super>64</super>), so the cancellation is "
      "exact. XGBoost's allreduce offers no hook for the masks, so we wrote a histogram gradient-boosting "
      "trainer with the same settings (300 trees, depth 6, 256 bins), in which the bin cuts are also taken "
      "from securely summed counts. Masked and unmasked training, each repeated with fresh keys, gave the "
      "same model bit for bit, and the same scores on all 1.46 million T1B test rows. The trainer agrees "
      "with lossless federated XGBoost on 99.0 % of the test rows, at an F1 of 86.76 % against 86.79 % "
      "(Table 3). Masking added 2.1 % to the training time and no bytes. The trainer is slower than XGBoost "
      "(796 s against 38 s) and sends 6.3 GB against 2.6 GB, because it is written in NumPy and sends the "
      "histogram of every node where XGBoost subtracts one child's from its parent's."),
    P("The same masked sum lets the controllers set the alarm threshold on their benign scores together "
      "without revealing them: each counts its scores over a public grid of 10,000 cells in log-odds, and "
      "the threshold is the lowest cell edge at which 0.1 % of the pooled rows lie above it. Table 8 "
      "compares it with the deployed rule (C3's rows only) and with the highest of the three controllers' "
      "own thresholds, which needs no masking but reveals each threshold. On the deployed model the "
      "federated threshold lowered the false alarms on T1B from 0.79 % to 0.69 % at 0.44 points of recall, "
      "and the highest local threshold to 0.56 % at 0.99 points. No rule reached the 0.1 % target, since "
      "none of the calibration captures is T1B. This is one comparison and not a test."),
    table(th, [36 * mm, 34 * mm, 16 * mm] + [(W - 86 * mm) / 6] * 6,
          "Table 8. Alarm threshold of the federated detector on the T1B test recordings (%).",
          "FA: false alarms on benign-only recordings. Each rule targets 0.1 %. UHt: a capture no controller "
          "trained on.",
          rules=R8),

    P("6.10. Summary of findings", "h2"),
    P("The experiments support seven findings. (i) FEVER protects benign traffic better than the six published "
      "defenses: it harmed 0.011 % of benign flows against 1.0 % to 5.2 %, and kept 84.2 % of new connections "
      "working against 21.0 % to 45.6 %; both results hold against every baseline. (ii) FEVER held the "
      "attacker to the smallest share of the flow table against five of the six baselines (6.8 % against "
      "24.2 % to 35.5 %); FTODefender held G2, Pulse and EVX lower. (iii) The gain is largest under the "
      "low-rate attacks that imitate benign traffic, Mimic and Aware, and it holds against baselines trained "
      "on the pooled data of all three controllers and on the UHt capture that no controller trained on. "
      "(iv) Federated training lets a controller detect an attack that only another controller has seen: "
      "under Mimic, recall rose from 0.2 % to 60.9 %, the attackers were blocked 64 s earlier and the "
      "occupancy fell from 15.7 % to 4.9 %, without any rows or labels leaving a controller. Lossless "
      "federated XGBoost matches training on pooled data, which FedAvg, FedProx and federated bagging do "
      "not, and with pairwise masking the controllers' histograms stay hidden from one another at 2 % more "
      "training time. (v) Every part of FEVER is needed on at least one attack, and blocking at the ingress port gives "
      "the largest single effect. (vi) FEVER blocked no benign host under flash crowds, and with "
      "four or eight colluding attackers it still blocked the attackers and kept a lower occupancy than "
      "FTMaster and DMS-BTT, though more slowly at eight. (vii) Two attacks remain open: no method defends "
      "against Slow, and two EVX attackers evade FEVER's volume rule. FEVER is also the lightest of the eight methods in decision time and CPU, "
      "at the price of the largest memory use."),
]

SimpleDocTemplate(OUT, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm,
                  bottomMargin=20 * mm, title="Experimental setup and results").build(story)
print("written", os.path.abspath(OUT))
