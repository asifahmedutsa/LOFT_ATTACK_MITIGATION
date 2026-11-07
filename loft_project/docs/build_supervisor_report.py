"""Builds docs/supervisor_report.pdf: the whole project for the supervisor in one document
(architecture, setup, results, strengths, weaknesses, next tests). Every number comes from the
committed results files named in the text; figures come from results/paper_figs and docs/.

    ~/.venvs/loft/bin/python docs/build_supervisor_report.py
"""
import os

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

OUT = "docs/supervisor_report.pdf"
FIG = "results/paper_figs"
FIG5 = "results/paper_figs/v5"
FD = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data/fonts/ttf")
for name, f in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"),
                ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf")):
    pdfmetrics.registerFont(TTFont(name, os.path.join(FD, f)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

INK, MUTED, ACC, LINE, BAND = (colors.HexColor(x) for x in
                               ("#1f2933", "#52606d", "#1d5fa8", "#d9d8d3", "#eef3fa"))
GOOD, BAD = colors.HexColor("#e3f2ea"), colors.HexColor("#fbe7e2")
S = {
    "title": ParagraphStyle("title", fontName="DV-B", fontSize=20, leading=25, textColor=INK, spaceAfter=6),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=11, leading=15, textColor=MUTED, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="DV-B", fontSize=15, leading=19, textColor=ACC, spaceBefore=6, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="DV-B", fontSize=11.5, leading=15, textColor=INK, spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="DV", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5, alignment=TA_LEFT),
    "small": ParagraphStyle("small", fontName="DV", fontSize=8, leading=10.5, textColor=MUTED, spaceAfter=4),
    "cap": ParagraphStyle("cap", fontName="DV-I", fontSize=8.2, leading=11, textColor=MUTED, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=8.2, leading=10.4, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="DV-B", fontSize=8.2, leading=10.4, textColor=INK),
    "h3": ParagraphStyle("h3", fontName="DV-B", fontSize=9.6, leading=13, textColor=ACC, spaceBefore=2, spaceAfter=2),
    "box": ParagraphStyle("box", fontName="DV", fontSize=9.6, leading=13.6, textColor=INK),
}
W = A4[0] - 36 * mm


def P(t, s="p"):
    return Paragraph(t, S[s])


def bullets(items, s="p"):
    return ListFlowable([ListItem(P(t, s), leftIndent=10, value="•") for t in items],
                        bulletType="bullet", start="•", leftIndent=12, bulletFontName="DV",
                        bulletFontSize=8, spaceAfter=4)


def table(rows, widths=None, head=True, tint=None):
    data = [[P(str(c), "cellb" if (head and i == 0) else "cell") for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * W for w in widths] if widths else None, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), BAND))
    for (r, c) in (tint or []):
        st.append(("BACKGROUND", (0, r), (-1, r), c))
    t.setStyle(TableStyle(st))
    return t


def fig(path, cap, w=1.0):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize()
    width = W * w
    return KeepTogether([Image(path, width=width, height=width * ih / iw), P(cap, "cap")])


def shows(points):
    """The 'What this shows' block under a figure, kept on one page."""
    return [KeepTogether([P("What this shows", "h3"), bullets(points, "p")])]


def note(text, bg=BAND):
    t = Table([[P(text, "box")]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def footer(c, doc):
    c.saveState()
    c.setFont("DV", 7.5)
    c.setFillColor(MUTED)
    c.drawString(18 * mm, 10 * mm, "EnsGuard: federated defense against low-rate flow-table overflow  ·  status report, 7 November 2026")
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")
    c.restoreState()


s = []
# ------------------------------------------------------------------ 0. summary
s += [P("EnsGuard: federated defense against low-rate flow-table overflow", "title"),
      P("Status report for the supervisor: architecture, experiments, results, strengths, weaknesses and the next tests. 7 November 2026.", "sub"),
      P("The short version", "h1"),
      bullets([
          "<b>What we built.</b> EnsGuard lets several SDN controllers share trained detectors instead of raw traffic. Each controller scores every flow-table entry every second, evicts suspicious entries, blocks hosts that keep getting evicted, and falls back to a fair share of the table per port.",
          "<b>Clear win (offline, simulator).</b> EnsGuard is the best detector at recognising attacks a controller never trained on. At a 0.1 % false-alarm rate it catches 98.7 % of attacks seen only by another controller, where the published detectors fall to 79-82 %. It catches 48.5 % of an attack no controller saw, against 34.4 % for our earlier FL-DualGuard and 9.5-24.9 % for FTOP, FTMaster, FloRa and DMS-BTT.",
          "<b>Newest result: FEVER on the testbed (preregistered, 120 runs, 7 November).</b> On traffic no model was trained on, FEVER has the lowest benign harm (0.49 % mean, against DMS-BTT 1.71 % and FTMaster 4.80 %) and half the attacker share of every other defense (22 % against 42-46 %). Under the disguised attacks A4 and E9P it is better than both published methods in every run (harm 0.10-0.32 % against 2-10 %), and it is the only defense that blocks the attackers. It blocked no innocent host. Under the standard attack A2 it is close but behind (harm 1.05 % against about 0.02 %), because its 60 s block expires and the attackers return. 4 of 7 preregistered tests and all 3 guards pass; the harm tests against DMS-BTT and FTMaster fail on A2 (Section 4.12).",
          "<b>Earlier testbed campaign (v3, preregistered, 200 runs).</b> EnsGuard v3 beats the classic defenses (EVICT, SIFT, TableGuard) on how much of the table the attacker holds: 14 of 15 paired runs each, Holm-adjusted p = 0.004. It does <b>not</b> beat the modern ML defenses (DMS-BTT, FTMaster, FTOP, rDefender, FL-DualGuard) on harm to normal users or on the attacker's share. It blocked an innocent host in 4 of its 20 runs.",
          "<b>Why the testbed is harder.</b> Per-entry logs recorded on the testbed show that the simulator already predicts the problem. On the real trace traffic (bigFlows), the disguised attacks A4 and E9P score lower than the noisiest normal traffic, so <i>every</i> detector misses them, ours and the published ones. Poll jitter on the testbed is not the cause.",
          "<b>A fix we tried, with rules fixed in advance, failed.</b> Adding the trace domain as a fourth federated controller (trained on its normal traffic plus one standard attack) did not catch A4. It also cut detection of unseen attacks from 48.5 % to 14.9 %. We stopped as the rules required; this is a useful negative result.",
          "<b>Proposed paper.</b> An honest paper: federated detection that generalises offline; the v3 testbed comparison with eight other defenses and why it fell short; the negative v4 result; and FEVER, which closes most of the gap on a clean train/test split. Draft: docs/paper_optionA.md.",
      ]),
      P("How to read this report", "h2"),
      P("Section 1 explains the attack. Section 2 walks through the architecture step by step. Section 3 describes how we tested. Section 4 gives the results with figures (4.12 is the newest, FEVER). Section 5 lists where EnsGuard does well and where it needs work. Section 6 proposes the next tests. Section 7 compares our experiments with the related papers. The appendix has the remaining figures and a glossary."),
      PageBreak()]

# ------------------------------------------------------------------ 1. problem
s += [P("1. The problem: low-rate flow-table overflow (LOFT)", "h1"),
      P("An SDN switch keeps a <b>flow table</b>: a list of rules saying where each connection's packets go. Our tables hold 3,500 rules. A rule disappears after 10 s without traffic (the <i>idle timeout</i>). When a packet has no rule, the switch asks the controller (a <b>Packet-In</b>), and the controller installs a new rule."),
      P("A LOFT attacker opens many fake connections and sends one small packet on each just before its 10 s timeout. Each fake rule stays alive at almost no traffic cost. The table slowly fills; when it is full, normal users' new connections are refused or delayed. Because the traffic rate is tiny, rate-based DDoS alarms do not fire."),
      P("Attack variants we test", "h2"),
      table([["Variant", "How it behaves", "Closest attack in the literature"],
             ["A2 (standard)", "100 new rules per burst, a burst every 5.5-9 s, one 64-byte packet per rule, from the attacker's own address", "The original LOFT attack; the attack groups of the Tang et al. papers and DMS-BTT"],
             ["A4 (mimicry)", "Same speed as A2, but 1-3 packets per refresh sized like normal traffic, from a pool of addresses", "rDefender's advanced low-rate attack (trace replay)"],
             ["E9P (adaptive)", "Refreshes every 2-3 s with normal-looking packets; the best attack our search found against six of our seven defenses", "ALFO's adaptive attack"],
             ["A1, A3, A5, A6, A7", "Other speeds, spoofed sources, a slow fill (A6, never trained on by anyone) and an on/off pulse", "Used in the simulator"]],
            [0.17, 0.5, 0.33]),
      Spacer(1, 6),
      note("<b>Important.</b> A2 is the attack the other papers test. A4 and E9P are harder, disguised versions that only two of the twelve related papers (rDefender and ALFO) test in any form. Our results on A4 and E9P therefore go beyond what the other papers report, and cannot be compared with their published numbers."),
      PageBreak()]

# ------------------------------------------------------------------ 2. architecture
s += [P("2. FEVER architecture, step by step", "h1"),
      P("<b>FEVER</b> (Federated Eviction and Volume-based Enforcement against overflow Rules) is the current version of EnsGuard (v5 in run names and result files).", "p"),
      fig("docs/fever_architecture.png", "Figure A. FEVER: attack detection and attack mitigation run on each controller every 1 s poll; the shared detector they use comes from federated training (bottom). v3, the version of the first testbed campaign, used RF + CatBoost and had no volume rule (Section 4.11)."),
      fig("docs/fever_flowchart.png", "Figure A2. The FEVER framework as a flowchart, in the style of the related papers. TH1 = 70 % and TH2 = 90 % table occupancy; τ is the per-controller score threshold; volume blocking blocks a host holding more than X entries and at least 3 times the median host's.", 0.9),
      P("Offline: building the shared detector", "h2"),
      bullets([
          "<b>Step 1. Each controller trains locally.</b> Controllers D1, D2 and D3 each collect labelled flow-table entries from their own network. Each has seen different attacks: D1 saw A1 and A4, D2 saw A2 and A5, D3 saw A3 and A7. Nobody saw A6 or E9P.",
          "<b>Step 2. One model per controller.</b> Each trains a CatBoost model on 17 features. (v3 also trained a Random Forest; dropping it kept the accuracy and made scoring about 5 times faster.)",
          "<b>Step 3. Models are shared, data is not.</b> Each controller uploads its trained model; the shared detector is the average attack probability of the 3 models. A controller benefits from attacks only the others have seen.",
          "<b>Step 4. Each controller sets its own settings from its own normal traffic.</b> The alarm threshold τ flags only 0.1 % of its normal entries; the volume limit X is 1.5 times the busiest normal host. On the testbed both come from the training part of the trace only (T1A): τ = 0.620, X = 785-800 entries per switch.",
      ]),
      P("Online: the loop every second on every switch", "h2"),
      bullets([
          "<b>01 Read flow statistics</b> from the switch: per-entry packets, bytes, age, source MAC and port, and how full the table is.",
          "<b>02 Compute 17 features</b> per entry, only for entries whose counters changed since the last poll: 11 about the flow (rate, gaps between packets, sizes), 3 about its source host, 3 about the table (occupancy, churn).",
          "<b>03 Score</b> each entry with the 3 shared CatBoost models (only while the table is at least 70 % full, or a host is on probation).",
          "<b>04 Evict</b> every entry scoring at least τ.",
          "<b>05 Block rule A (detector).</b> A host whose evictions in the last 10 s are at least 50, at least 3 times the median host's (counting the median as at least 10), and at least 20 % of its own entries is blocked. This catches attacks the model recognises, such as A2.",
          "<b>06 Block rule B (volume, new in FEVER, no ML).</b> While the table is at least 90 % full, a host holding more than X entries and at least 3 times the median host's is blocked. This catches disguised attacks the model misses (A4, E9P). Either rule blocks a host for 60 s, doubling on repeat (at most 240 s).",
          "<b>07 PortGuard fallback.</b> If the table is still at least 90 % full, each access port gets a weighted fair share, trimming the highest-scoring entries first. This bounds any attacker both rules miss.",
      ]),
      fig("docs/fever_federated_topology.png", "Figure B. Experiment topology. Domains D1-D3 each train a CatBoost model on their own benign traffic and the attacks they have seen, and share only the model. The shared detector is deployed in the test domain, the Mininet testbed replaying the bigFlows trace. Every domain has the same tree: a controller, core switch S1 to the server, access switches S2 and S3 with two users and one attacker each.", 0.85),
      P("Why this design", "h2"),
      bullets([
          "<b>Federation</b> addresses the main gap in the literature: per-controller detectors are trained and tested on the same attacks and fail on attacks seen elsewhere.",
          "<b>CatBoost only:</b> v3 averaged RF and CatBoost; CatBoost alone generalises about as well at a fifth of the cost (Section 4.1), which matters on a saturated controller.",
          "<b>Evict, then block, then fair share</b> mirrors the published systems (FTMaster, FTODefender and FloRa evict and block). FEVER adds two parts that do not depend on the detector: the volume rule and the fair-share fallback.",
      ]),
      PageBreak()]

# ------------------------------------------------------------------ 3. how we tested
s += [P("3. How we tested", "h1"),
      P("Three kinds of experiment", "h2"),
      table([["Experiment", "Where", "What it answers"],
             ["E11: same-data detection benchmark", "Simulator data (domains D1-D3), offline", "Which detector recognises attacks it did not train on? Every detector is trained and scored on identical rows."],
             ["Simulator online test", "Our simulator LOFT-Bench, fresh seeds 26000-26004, run once", "How well does the full defense protect users when everything is simulated?"],
             ["Preregistered testbed campaign (v3)", "Real Mininet + Open vSwitch + Ryu testbed, seeds 4120-4124", "Does EnsGuard beat 8 other defenses on a real OpenFlow controller? 200 runs."],
             ["Testbed entry logs", "12 extra testbed runs with per-entry logging, seeds 4131-4133", "Why do testbed and simulator disagree?"],
             ["v4 trial", "Simulator + the 12 testbed logs", "Does adding the trace controller to the federation fix the miss?"],
             ["Preregistered testbed campaign (FEVER)", "Same testbed; trace split into T1A (train) and T1B (test); fresh seeds 4140-4144", "Does FEVER beat v3, v4-lite, DMS-BTT and FTMaster on traffic nobody trained on? 120 runs."]],
            [0.28, 0.32, 0.40]),
      P("Testbed setup", "h2"),
      bullets([
          "One 4-core laptop; Mininet, Open vSwitch, Ryu with OpenFlow 1.3; one controller per run.",
          "Topology: core switch s11 to the server, access switches s12 and s13 with 3 hosts each, one attacker per access switch. All tables 3,500 rules, idle timeout 10 s, all monitored.",
          "Normal traffic: the real bigFlows trace (as in DMS-BTT), replayed at half speed. The speed was fixed in advance as the fastest at which a no-attack run loses at most 0.25 % of first packets.",
          "Each run: 300 s, attack starting at 50 s. A probe opens a new TCP connection every 0.5 s to measure what a new user experiences.",
          "Ten defenses: none, EVICT, SIFT, TableGuard, rDefender, FTMaster, FTOP, DMS-BTT, FL-DualGuard (our earlier system) and EnsGuard. Four traffic types (A2, A4, E9P, normal only) x 5 seeds = 200 runs.",
      ]),
      P("Preregistration (fixed before any defense ran on the test seeds)", "h2"),
      table([["Hypothesis", "Statement", "Test"],
             ["H1", "EnsGuard harms fewer normal flows than each of the 8 comparators", "one-sided exact sign test over 15 paired attack runs, ties count against, Holm correction over the 8"],
             ["H2", "EnsGuard keeps a lower average attacker share of the core table than each of the 8", "same"],
             ["H3", "With no attack: mean harm at most 0.5 % and lost first packets at most 1 %", "descriptive"],
             ["H4", "No normal host is ever blocked in EnsGuard's 20 runs", "descriptive"]],
            [0.12, 0.5, 0.38]),
      P("Main measures", "h2"),
      bullets([
          "<b>Harm to users:</b> normal flows harmed (refused, dropped or first packet lost); lost first packets at the controller; new-connection success and connect time.",
          "<b>Table measures used by the other papers:</b> attacker share of the table (Pa, average and maximum); table usage; seconds the table was full; Packet-In and Table-Full message counts; processing time; CPU and memory.",
          "<b>Detection:</b> accuracy, precision, recall, F1, false-positive rate, PR-AUC.",
      ]),
      PageBreak()]

# ------------------------------------------------------------------ 4. results
s += [P("4. Results so far", "h1"),
      P("4.1 Offline detection (E11): EnsGuard's clearest win", "h2"),
      P("Recall at a 0.1 % false-alarm rate, by whether the scoring controller trained on the attack (results/e11_detect/table_main.csv)."),
      table([["Detector", "Attack seen by this controller", "Seen only by another controller", "Seen by no controller", "PR-AUC, seen by none"],
             ["FTOP", "92.0 %", "79.4 %", "9.5 %", "42.2"],
             ["FTMaster", "92.4 %", "81.3 %", "15.0 %", "43.6"],
             ["FloRa", "97.5 %", "82.2 %", "24.9 %", "55.0"],
             ["DMS-BTT", "92.3 %", "81.6 %", "14.3 %", "39.6"],
             ["FL-DualGuard (ours, earlier)", "97.4 %", "96.7 %", "34.4 %", "93.3"],
             ["EnsGuard", "99.2 %", "98.7 %", "48.5 %", "92.7"]],
            [0.28, 0.18, 0.2, 0.17, 0.17], tint=[(6, GOOD)]),
      Spacer(1, 6),
      fig(f"{FIG}/fig09_classifier_comparison.png", "Figure 9. Accuracy, precision, recall and F1 by attack exposure. All detectors are near-perfect on attacks they trained on; only the federated ones keep it on attacks seen elsewhere."),
      *shows([
          "<b>Left panel (attacks this controller trained on):</b> all six detectors score 92-100 % on every metric. This is the setting every related paper reports, and it is why their published accuracies are all near 99 %. On this setting nobody clearly wins.",
          "<b>Middle panel (attacks only another controller saw):</b> the four per-controller detectors (FTOP, FTMaster, FloRa, DMS-BTT) drop to about 80 % recall and 84 % precision, because their own training data never contained these attacks. The two federated detectors stay at 97-99 % because they include models trained by the controllers that did see them.",
          "<b>Right panel (an attack no controller saw, A6):</b> recall falls for everyone, but EnsGuard keeps the most (48 %). Precision of the per-controller detectors drops to about 35 %: at a fixed 0.1 % false-alarm rate they flag about as many normal entries as before but catch few attack entries, so most of their flags are wrong.",
      ]),
      P("<b>Cost of the two-model ensemble</b> (results/e1_pair/cost.csv): scoring 10,000 entries takes 71.8 ms with the RF and 18.9 ms with CatBoost. The RF is about 80 % of EnsGuard's scoring time, but alone it is the weakest at new attacks (F1 77.3 against 84.0 for CatBoost alone and 84.3 for both). CatBoost alone keeps almost all the benefit at about a fifth of the cost; this is a candidate improvement (Section 6)."),
      PageBreak(),
      P("4.2 Accuracy, precision, recall and F1 against each paper", "h2"),
      P("The same benchmark (E11), drawn with one panel per metric so each paper's detector can be compared directly with the others. Figure 13 puts every detector at the same 0.1 % false-alarm rate, which is the fair comparison. Figure 14 uses each paper's own threshold (0.5 for the published detectors, the deployed threshold for ours), which is how each would actually run."),
      fig(f"{FIG}/fig13_metrics_by_paper.png", "Figure 13. Every detector at the same 0.1 % benign false-positive rate. EnsGuard (dark green) is highest or tied on all four metrics in all three groups."),
      *shows([
          "<b>Accuracy</b> hides the problem: it stays above 80 % for everyone even on the unseen attack, because most entries are normal and are classified correctly. This is why accuracy alone, as most papers report it, says little about LOFT detection.",
          "<b>Precision:</b> on attacks they trained on, everyone is at about 100 %. On attacks seen elsewhere or nowhere, only the two federated detectors keep precision near 99 %; the per-controller detectors fall to 84 % and 35 %.",
          "<b>Recall</b> is where the detectors really differ. On attacks seen elsewhere: EnsGuard 99 %, FL-DualGuard 97 %, the four published detectors 79-82 %. On the unseen attack: EnsGuard 48 %, FL-DualGuard 34 %, FloRa 25 %, FTMaster 15 %, DMS-BTT 14 %, FTOP 9 %.",
          "<b>F1</b> combines the two: on the unseen attack EnsGuard 64 against FL-DualGuard 51 and 15-28 for the published detectors.",
      ]),
      fig(f"{FIG}/fig14_metrics_by_paper_own_threshold.png", "Figure 14. Each detector at its own paper's threshold."),
      *shows([
          "At their own thresholds the published detectors flag more (1.3-1.4 % false alarms for FTOP, FTMaster and DMS-BTT, 0.25 % for FloRa), so their recall on seen attacks rises to about 97 %, but on the unseen attack it is still only 19-27 %.",
          "<b>One honest caveat:</b> at its own deployed threshold, our earlier FL-DualGuard catches more of the unseen attack than EnsGuard (69 % against 48 %, F1 80 against 64). It pays for that with about 8 times as many false alarms (1.1 % against 0.13 %). EnsGuard was deliberately run at the stricter 0.1 % budget.",
      ]),
      P("What the papers themselves report (on their own data, not comparable with ours)", "h3"),
      table([["Paper", "What was classified", "Accuracy", "Precision", "Recall", "F1"],
             ["FTMaster", "per rule (XGBoost)", "92.5 %", "n/r", "89.5 % (FNR 10.5 %)", "91.6 %"],
             ["FTOP", "per rule (Random Forest)", "98.9 %", "99.2 %", "99.0 %", "99.1 %"],
             ["FloRa", "per flow (CatBoost)", "99.5 %", "n/r", "98.8 % (FNR 1.2 %)", "99.9 % (inconsistent with its FNR)"],
             ["DMS-BTT", "per flow, mixed attack groups (CatBoost)", "92.4 %", "92.5 %", "83.1 %", "87.6 %"],
             ["EnsGuard (ours, E11)", "per entry, attacks this controller trained on", "99.6 %", "99.8 %", "99.2 %", "99.4 %"]],
            [0.2, 0.3, 0.11, 0.11, 0.14, 0.14]),
      P("Each paper tests only attacks its detector trained on, on its own traffic and attack generator; n/r = not reported. Our numbers are on the comparable 'seen by this controller' setting. The papers do not report the other two settings at all.", "small"),
      PageBreak(),
      P("4.3 Simulator online test: the best system in simulation", "h2"),
      P("All of D1-D3 with the full defense (evict, block, PortGuard), every attack, on fresh seeds run once.", "p"),
      table([["Attack", "EnsGuard harm", "EnsGuard attacker share", "For comparison"],
             ["A2", "0.36 %", "2.0 %", ""],
             ["A4", "0.73 %", "5.0 %", "DMS-BTT with blocklist: harm 20.5 %, share 39.3 %"],
             ["A6 (unseen)", "0.37 %", "5.3 %", ""],
             ["E9P", "2.0 %", "26.2 %", "FL-DualGuard 1.1 % harm; without PortGuard EnsGuard's harm is 37.7 %"],
             ["normal only", "0.08 %", "0", "no normal host blocked"]],
            [0.16, 0.18, 0.22, 0.44]),
      P("Source: results/evictblock/test_summary.csv (domains D1-D3, fresh seeds 26000-26004, run once).", "small"),
      *shows([
          "In the simulator, EnsGuard keeps normal-user harm below 1 % for A2, A4 and A6, and about 2 % for the adaptive E9P, while DMS-BTT's harm under A4 is 20.5 %.",
          "PortGuard matters most for E9P: without it EnsGuard's harm rises to 37.7 %, because the detector misses most E9P entries and only the fair share stops the attacker.",
          "These are the results that motivated the testbed campaign. The testbed (next sections) did not reproduce them, for reasons explained in 4.9.",
      ]),
      PageBreak()]

s += [P("4.4 Testbed: the preregistered hypotheses", "h2"),
      table([["Hypothesis", "Result", "Detail"],
             ["H1 lower harm", "Not supported against any of the 8", "EnsGuard mean harm 3.76 %; DMS-BTT 3.31 %, FL-DualGuard 4.06 %, FTMaster 4.60 %, FTOP 5.14 %, EVICT 5.19 %, rDefender 6.16 %, TableGuard 8.93 %, SIFT 9.49 %"],
             ["H2 lower attacker share", "Supported against EVICT, SIFT, TableGuard only", "14 of 15 wins each, Holm p = 0.004. EnsGuard 41.2 % against DMS-BTT 39.9 %, FTMaster 41.2 %, rDefender 42.0 %, FTOP 43.5 %, FL-DualGuard 46.7 %"],
             ["H3 clean without attack", "Passes", "harm 0.00 %, lost first packets 0.04 %"],
             ["H4 no innocent host blocked", "Fails", "a normal host was blocked in 4 of 20 runs"]],
            [0.2, 0.25, 0.55], tint=[(1, BAD), (2, GOOD), (3, GOOD), (4, BAD)]),
      P("Source: results/testbed_prereg_v3/report.md.", "small"),
      *shows([
          "The test is strict: EnsGuard must win at least 12 of the 15 paired runs against a comparator, after correcting for testing 8 comparators. It does so only against the three classic defenses.",
          "Against DMS-BTT, EnsGuard wins only 6 of 15 runs on harm and 5 of 15 on attacker share, so DMS-BTT is slightly better on average; against FTMaster, FTOP, rDefender and FL-DualGuard the results are mixed (6-11 wins).",
          "H3 shows EnsGuard causes no harm when there is no attack. H4 failing is the clearest defect: blocking an innocent host cuts that user off for 60 s or more.",
      ]),
      P("4.5 Testbed comparison in the other papers' format", "h2"),
      fig(f"{FIG}/fig03_comparison.png", "Figure 3. The comparison table of FTMaster, FTODefender, FTOP and DMS-BTT, measured on our testbed (A2, A4, E9P x 5 seeds; bar = mean, whisker = min-max; EnsGuard in orange). EnsGuard is in the leading group on average attacker share and table usage, and has the fewest Packet-Ins, but no clear overall win."),
      *shows([
          "<b>Average attacker share:</b> without a defense the attacker holds 59 % of the core table. EVICT, SIFT and TableGuard barely help (53-61 %). The ML defenses and rDefender cut it to 40-47 %; EnsGuard (41 %) is in that group with DMS-BTT (40 %) and FTMaster (41 %).",
          "<b>Maximum attacker share:</b> every defense still lets the attacker reach 76-90 % at some point; DMS-BTT and FL-DualGuard have the lowest peaks (76-77 %), EnsGuard 82 %.",
          "<b>Seconds at the limit and Table-Full messages:</b> without a defense the table is full for 47 s and the switch sends about 3,000 Table-Full errors. FL-DualGuard (2 s, 77 messages), DMS-BTT (4 s, 225) and EnsGuard (5 s, 332) almost eliminate overflow. EVICT sends no Table-Full only because it replaces entries instead of refusing them; its table is full for the longest (74 s).",
          "<b>Packet-In messages:</b> EnsGuard has the fewest (61 k against 70 k with no defense), so it puts the least load on the controller.",
          "The whiskers are long for every defense: results vary a lot between attacks and seeds, which is why 5 seeds give limited statistical power.",
      ]),
      PageBreak(),
      P("4.6 How the table fills over time", "h2"),
      fig(f"{FIG}/fig01_rules_over_time_A4.png", "Figure 1 (A4). Normal (blue) and attack (orange) rules in the core switch under the mimicry attack. Every defense slows the attacker a little; rDefender and FTOP clear the table most visibly; EnsGuard keeps the table slightly below full but the attacker holds most of it."),
      *shows([
          "Before 50 s only normal rules exist (about 1,000 of 3,500). From 50 s the attacker adds 100 rules per burst; with no defense the orange area grows until the table is full near 200 s and normal rules are squeezed to about 400.",
          "No defense removes A4: because A4's packets look normal, the detectors score them low. The sharp drops for rDefender (about 200 s) and FTOP are their random or score-based deletions; the attacker refills the space within about a minute.",
          "With EnsGuard the total stays a little lower (about 3,000) mostly because PortGuard caps each port's share, not because the detector finds A4.",
      ]),
      fig(f"{FIG}/fig02_attack_share_over_time.png", "Figure 2. Attacker share over time. Under A2, EnsGuard removes the attacker for long stretches (about 120-190 s and again near 280 s). Under A4 and E9P it stays near 75 %, close to no defense, because the detector does not fire; DMS-BTT does better on E9P (about 50 %)."),
      *shows([
          "<b>A2 (standard attack):</b> FTMaster and EnsGuard remove the attacker completely for long stretches (share at 0 %). The attacker returns when its block expires (EnsGuard, about 210 s) and is removed again. DMS-BTT and FTOP only reduce it, with spikes back up to 50-70 %.",
          "<b>A4 and E9P (disguised):</b> the curves of all defenses stay close to the no-defense line (grey) for the first 100 s of the attack, which shows that none of the detectors recognises these attacks early. Later, DMS-BTT and FTOP pull E9P down to about 50 % for part of the run.",
      ]),
      PageBreak(),
      P("4.7 What users experience", "h2"),
      fig(f"{FIG}/fig05_packet_in_loss.png", "Figure 5. Left: first packets of normal flows lost at the overloaded controller. EnsGuard loses the most under E9P (48 %) because its scoring is slow. Right: normal flows harmed. EnsGuard is the best under E9P (0.9 %) but poor under A4 (7.6 %, against 8.6 % with no defense)."),
      *shows([
          "<b>Lost first packets</b> measures controller overload: a new flow's first packet waits at the controller, and if the controller is too busy it is dropped. Losses rise from A2 (5-21 %) to E9P (28-48 %) for every defense, because E9P sends the most packets.",
          "EnsGuard loses the most under E9P because its scoring takes the longest per poll (Figure 7); while it scores, Packet-Ins queue up.",
          "<b>Benign harm</b> combines refused flows, flows dropped by a block and lost first packets. EnsGuard is best under E9P (0.9 %), where its fair-share fallback protects normal users; under A4 it harms 7.6 % because it evicts some normal entries and blocked busy normal hosts.",
      ]),
      fig(f"{FIG}/fig06_new_flow_service.png", "Figure 6. New-connection probe. Under A2, EnsGuard lets the most new connections through (38 %). Under E9P every defense is equally poor (about 12 %): the controller is saturated."),
      *shows([
          "This probe is what a new user feels: a TCP connection opened every 0.5 s after the attack starts.",
          "Under A2 and A4 only 27-38 % of new connections succeed with any defense, against 100 % with no attack. The table and controller are under so much pressure that defenses only partly restore service.",
          "Connect times of successful connections (right) are 160-380 ms for everyone, against about 45 ms without attack. EnsGuard has among the fastest under A2 and A4 (about 190-210 ms).",
      ]),
      PageBreak(),
      P("4.8 Cost on the controller", "h2"),
      fig(f"{FIG}/fig07_decision_time.png", "Figure 7. Processing time per poll. EnsGuard is the slowest and most variable (median 135 ms over the three attacks; 160 ms under A4, 232 ms under E9P)."),
      *shows([
          "Each box shows the time the controller spends on one 1 s poll: reading statistics, computing features, scoring and acting. Medians are 20-50 ms for most defenses.",
          "EnsGuard's box stretches from about 13 ms to 230 ms: when the table is below 70 % it does not score; when it is full it scores 3,500 entries with six models, which takes 200+ ms.",
          "This is the main cost of the ensemble, and why v4-lite tests CatBoost alone (5 times faster, Section 4.11).",
      ]),
      fig(f"{FIG}/fig08_cpu_memory.png", "Figure 8. Controller CPU and memory. Every defense runs the controller at about 93 % of one core under attack, so CPU does not separate them; EnsGuard uses the most memory (about 315 MB)."),
      *shows([
          "The controller runs on one core; at about 93 % it is saturated under every defense, including no defense. The laptop, not the defense, is the bottleneck, so CPU cannot rank the defenses here.",
          "Memory separates them: EnsGuard holds six models (about 315 MB peak against 220-255 MB for the others). This is acceptable for a controller but would grow with more controllers in the federation.",
      ]),
      PageBreak(),
      P("4.9 Why the testbed disagrees with the simulator", "h2"),
      P("We recorded every entry's counters on the testbed in 12 extra runs (logging costs 0.17 ms per poll and did not change the results) and scored every detector on exactly those rows, next to the simulator's version of the same traffic (results/e11_testbed/report.md)."),
      fig(f"{FIG}/fig11_score_distribution.png", "Figure 11. EnsGuard's score for normal (blue) and attack (orange) entries on the testbed. A2's attack entries sit above the 0.64 threshold. A4's and E9P's sit below it, inside the normal traffic's tail, so they are not caught."),
      *shows([
          "Blue bars: normal entries; orange: attack entries; dashed line: the alarm threshold. Anything right of the line is evicted. The vertical axis is logarithmic, so the small blue bars at the right still matter: they are the 0.1 % of normal entries the threshold allows.",
          "A2's attack entries pile up at 0.8-1.0, well right of the line, so A2 is caught. A4's pile up at 0.2-0.35 and E9P's at 0-0.3: they look more normal than the noisiest normal entries, so no threshold can catch them without also evicting many normal entries.",
      ]),
      bullets([
          "<b>The testbed reproduces the simulator.</b> Every detector catches A2 (simulator 81-99 %, testbed 49-95 %) and misses A4 and E9P (at most 1.3 %) in both.",
          "<b>The simulator already predicted it.</b> On the trace's normal traffic, the top 0.1 % of normal scores (0.67) lies above the median A4 score (0.34). On domain D1, which trained on A4, the same detector catches 96.6 % of A4. The cause is a mismatch between the training domains and the real trace (domain shift).",
          "<b>Poll jitter is not the cause.</b> Rebuilding the features on a perfect 1 s clock changes recall very little.",
          "<b>Ranking still works, thresholds do not.</b> On A4 the attack entries still rank high (PR-AUC about 89 for EnsGuard, DMS-BTT and FTOP federated) but below the noisiest normal entries.",
          "<b>On the testbed, PortGuard does most of EnsGuard's attacker removal under A4 and E9P.</b> The block rule's median falls to 0 when few entries are evicted, which is how busy normal hosts got blocked (H4).",
      ]),
      PageBreak(),
      P("4.10 The v4 trial: a preregistered negative result", "h2"),
      P("Hypothesis: if the miss is domain shift, give the trace domain its own controller in the federation, trained on its normal traffic plus the standard attack A2 (never A4 or E9P). Pass/fail rules were written before training (docs/v4_plan.md): A4 recall at least 30 % in the simulator and on the testbed; false alarms at most 0.5 %; A2 recall not lower; unseen-attack recall at least 46.5 %."),
      table([["Detector", "A4 caught (simulator / testbed)", "Unseen attacks caught (E11)", "Passes"],
             ["v3 (D1-D3)", "0 % / 0 %", "48.5 %", "no"],
             ["v4 (trace controller joins, RF + CatBoost)", "0 % / 0 %", "14.9 %", "no"],
             ["v4, CatBoost only", "0 % / 0 %", "21.0 %", "no"]],
            [0.4, 0.24, 0.22, 0.14], tint=[(2, BAD), (3, BAD)]),
      Spacer(1, 6),
      bullets([
          "The new controller's model learned that only A2's tiny fixed packets are an attack, so its vote pushed A4 further toward 'normal' (median A4 score fell from 0.34 to 0.25 in the simulator).",
          "Because the shared detector is a plain average, a controller that knows only one easy attack dilutes what the others learned: on D1, unseen-attack recall fell from 45.9 % to 0.2 %.",
          "As fixed in advance we stopped: no retuning and no testbed campaign for this detector. <b>Lesson:</b> in federated detection, a client's attack exposure matters as much as its normal data, and plain averaging gives a narrowly trained client a full vote.",
      ]),
      PageBreak()]

s += [P("4.11 From v3 to FEVER: what changed", "h2"),
      P("Each change below was chosen on development data with a rule fixed beforehand, then frozen before the FEVER test runs (docs/v4lite_plan.md, docs/v5_plan.md).", "p"),
      table([["Version", "Change", "Why"],
             ["v4-lite", "CatBoost only (the D1-D3 CatBoost members of v3)", "same generalisation as RF + CatBoost, about 5 times faster scoring (20 against 104 ms per 10k entries)"],
             ["v4-lite", "block rule with a floor: median at least 10 evictions, and at least 20 % of the host's own entries flagged", "the v3 rule's median fell to 0 and blocked busy innocent hosts (H4)"],
             ["v4-lite", "score only entries whose counters changed since the last poll; exact 8-bit CatBoost scorer", "cuts the per-poll decision time on the saturated controller"],
             ["FEVER", "clean split of the trace: every T1 model and threshold (ours, DMS-BTT's, FTMaster's) trained on the first 40 % (T1A), tests on the last 60 % (T1B)", "in v3 the baselines' T1 models had seen the test traffic"],
             ["FEVER", "volume block: a host holding more than X entries (1.5 x the busiest benign host on T1A: 785-800 per switch) and at least 3 x the median host, while the table is at least 90 % full, is blocked", "a detector-independent rule for the disguised attacks the detector misses"],
             ["dropped", "a local T1A model, and a univ2 client in the federation", "no gain on A4/E9P; the univ2 client cut unseen-attack recall from 51 % to 8.6 % (dilution, as in v4)"]],
            [0.12, 0.5, 0.38]),
      P("Development check before the test (T1B, seeds 4134-4136): A4 harm 0.01-0.04 %, both attackers blocked, benign runs clean.", "small"),
      PageBreak(),
      P("4.12 The FEVER campaign: preregistered result (7 November)", "h2"),
      P("Six defenses (none, EnsGuard v3, v4-lite, FEVER, DMS-BTT, FTMaster) x A2, A4, E9P and benign x fresh seeds 4140-4144 = 120 runs on T1B, the part of the trace no model or threshold was trained on. Hypotheses, seeds and tests were committed before any test run (results/testbed_prereg_v5/preregistration.json). One run (v4-lite, E9P, seed 4142) ended early and was rerun once with the same seed, as preregistered. Source: results/testbed_prereg_v5/report.md."),
      table([["Hypothesis", "FEVER wins / 15", "Result", "Means: FEVER vs comparator"],
             ["H1 harm vs DMS-BTT", "10", "not supported (p = 0.30)", "0.49 % vs 1.71 %; FEVER loses all 5 A2 pairs"],
             ["H1 harm vs FTMaster", "10", "not supported (p = 0.30)", "0.49 % vs 4.80 %; FEVER loses all 5 A2 pairs"],
             ["H2 attacker share vs DMS-BTT", "15", "supported (Holm p = 0.0001)", "21.9 % vs 41.9 %"],
             ["H2 attacker share vs FTMaster", "11", "not supported (p = 0.059)", "21.9 % vs 45.5 %; FEVER wins 1 of 5 A2 pairs"],
             ["H3 harm vs v3", "12", "supported (p = 0.018)", "0.49 % vs 3.48 %"],
             ["H4 decision time vs v3", "12", "supported (p = 0.018)", "54 vs 127 ms (mean per poll)"],
             ["H8 attacker share vs v4-lite (the volume block)", "12", "supported (p = 0.018)", "21.9 % vs 43.4 %"],
             ["H5 no innocent host blocked", "-", "pass", "0 of FEVER's 20 runs"],
             ["H6 benign runs clean", "-", "pass", "harm 0.00 %, lost first packets 0.12 %"],
             ["H7 new-connection success not worse than v3", "-", "pass", "0 of 15 pairs more than 5 points worse"]],
            [0.34, 0.12, 0.24, 0.30], tint=[(1, BAD), (2, BAD), (3, GOOD), (4, BAD), (5, GOOD), (6, GOOD), (7, GOOD), (8, GOOD), (9, GOOD), (10, GOOD)]),
      Spacer(1, 6),
      table([["Attack", "v3 harm", "v4-lite harm", "FEVER harm", "DMS-BTT harm", "FTMaster harm", "FEVER share", "DMS-BTT share", "FTMaster share"],
             ["A2", "2.64 %", "0.13 %", "1.05 %", "0.02 %", "0.01 %", "12.6 %", "18.7 %", "10.0 %"],
             ["A4", "5.59 %", "1.68 %", "0.32 %", "2.09 %", "4.16 %", "27.2 %", "47.6 %", "53.4 %"],
             ["E9P", "2.21 %", "2.97 %", "0.10 %", "3.01 %", "10.22 %", "26.0 %", "59.3 %", "73.3 %"]],
            [0.08, 0.1, 0.12, 0.1, 0.12, 0.12, 0.1, 0.13, 0.13]),
      P("Mean of 5 seeds; share = average attacker share of the core table s11. FEVER blocked both attackers in all 15 attack runs; v3 blocked 6 innocent hosts; neither baseline blocked an attacker.", "small"),
      fig(f"{FIG5}/fig15_per_attack_per_seed.png", "Figure 15. FEVER campaign per attack: bar = mean of 5 seeds, dot = one seed. FEVER in orange."),
      *shows([
          "<b>A4 and E9P (top middle and right):</b> FEVER's harm is at most 0.08 % in 8 of its 10 runs (0.32 % and 0.10 % mean; the worst run is 1.46 %), while DMS-BTT (2.1 % and 3.0 %) and FTMaster (4.2 % and 10.2 %) leave several percent of normal flows harmed. FEVER is lower than both baselines in every seed.",
          "<b>A2 (top left):</b> the two baselines are at almost exactly 0 % in every seed; FEVER is at about 1 % in four seeds and 0.02 % in one. This is the only place FEVER is worse, and the reason H1 fails: a tie or a small loss counts against FEVER in the sign test.",
          "<b>Attacker share (bottom):</b> FEVER halves it under A4 and E9P (26-27 % against 48-73 %). Under A2 all ML defenses keep it low (10-19 %); FTMaster is slightly lower than FEVER (10 % against 13 %), which is why H2 against FTMaster misses by one pair.",
          "<b>Progress across our own versions:</b> v3 to v4-lite cuts harm (better block rule, faster scoring); v4-lite to FEVER halves the attacker share under A4 and E9P (the volume block).",
      ]),
      PageBreak(),
      fig(f"{FIG5}/fig16_a2_block_expiry.png", "Figure 16. Why FEVER harms more under A2 (seed 4141): core-table entries over time for FEVER and the two baselines."),
      *shows([
          "FEVER blocks both attackers at 119 s, and its table drops to about 850 entries. No harm has occurred so far.",
          "At 179 s the 60 s block expires, the attackers return, and the controller is overloaded (event queue at its limit, decisions take about 1 s instead of 30 ms). FEVER's table fills to 3,500 at 210 s and stays full until about 225 s: 617 normal flows are refused, which is all of this run's 0.84 % harm.",
          "DMS-BTT and FTMaster never block anyone. They delete attack entries every second, which keeps their tables at 2,400-2,800 at most, so they never fill. They do this well on A2 because they were trained on A2 traffic from this same network (T1A); on A4 and E9P, which they never saw, they fail.",
          "<b>Likely fix (v6, not yet tested):</b> keep a block while the host is still sending (the drop rule's packet counter shows this), or re-block a returning host at a lower bar. This needs a new preregistration and fresh seeds.",
      ]),
      fig(f"{FIG5}/fig03_comparison.png", "Figure 3 (FEVER campaign). The related papers' comparison table, measured on T1B (A2, A4, E9P x 5 seeds; FEVER in orange)."),
      *shows([
          "<b>Average attacker share and table usage:</b> FEVER is clearly lowest (22 % and 40 %); every other defense is at 42-46 % and 56-61 %.",
          "<b>Maximum share:</b> about the same for all defenses (78-85 %), because every defense lets the attacker build up before acting.",
          "<b>Seconds at the limit:</b> FEVER has the fewest (3 s), against 7 s for DMS-BTT and 29 s for FTMaster.",
          "<b>Packet-In messages:</b> FEVER has the most (119 k). Its controller loses the fewest first packets (20 % against 28-34 %), so more Packet-Ins actually reach and are handled by the controller; the count measures load, not failure.",
      ]),
      PageBreak(),
      fig(f"{FIG5}/fig02_attack_share_over_time.png", "Figure 2 (FEVER campaign). Attacker share of s11 over time, median of 5 seeds."),
      *shows([
          "Under A4 and E9P, FEVER (pink) drops the attacker to 0 % once the volume block fires (about 125-180 s), while every other curve stays near the no-defense line. The share creeps back after the block expires, but the table no longer fills.",
          "Under A2, FEVER removes the attacker at about 120 s, the attacker returns at about 190-250 s (block expiry, Figure 16), and is removed again. FTMaster keeps it at 0 % from 150 s on.",
      ]),
      fig(f"{FIG5}/fig05_packet_in_loss.png", "Figure 5 (FEVER campaign). Lost first packets (left) and benign harm (right), mean of 5 seeds."),
      *shows([
          "FEVER loses the fewest first packets under A4 (16 % against 26-33 % for the others) and E9P (29 % against 37-57 %), because changed-entry scoring keeps its poll at about 12-15 ms and its blocks remove the attacker's Packet-Ins.",
          "Under A2, FTMaster loses the fewest (10 %); FEVER is in the middle (14 %).",
      ]),
      PageBreak(),
      fig(f"{FIG5}/fig07_decision_time.png", "Figure 7 (FEVER campaign). Per-poll processing time at s11 under attack."),
      *shows(["FEVER's median poll takes about 13 ms, the fastest of the six (DMS-BTT 65 ms, FTMaster 72 ms, v3 123 ms): the result of CatBoost only, the exact 8-bit scorer and scoring only changed entries (H4 supported)."]),
      fig(f"{FIG5}/fig06_new_flow_service.png", "Figure 6 (FEVER campaign). New-connection probe."),
      *shows(["New users still suffer under every defense: 27-47 % of new connections succeed under A2, about 30 % under A4 and 12 % under E9P. FEVER is best under A2 (47 %) and level with the others under A4 and E9P. The controller, not the table, is the bottleneck for new users (Section 6, test 4)."]),
      PageBreak()]

# ------------------------------------------------------------------ 5. good / bad
s += [P("5. Where EnsGuard does well, and where it needs work", "h1"),
      P("Current system: FEVER (Section 4.12). Rows marked v3 are from the earlier campaign; where FEVER fixed a v3 problem it says so.", "p"),
      P("Does well", "h2"),
      table([["What", "Evidence"],
             ["Detecting attacks a controller never trained on (offline)", "98.7 % on attacks seen only elsewhere (others 79-82 %); 48.5 % on an attack nobody saw (next best 34.4 %)"],
             ["Disguised and adaptive attacks on the testbed (FEVER)", "A4 harm 0.32 %, E9P 0.10 %, against 2.1-10.2 % for DMS-BTT and FTMaster; better in every run"],
             ["Keeps the attacker out of the table (FEVER)", "average attacker share 22 % against 42-46 %; H2 vs DMS-BTT 15 of 15; H8 vs v4-lite 12 of 15"],
             ["Removes the attacker (FEVER)", "both attackers blocked in all 15 attack runs; neither baseline blocks anyone"],
             ["No innocent host blocked (FEVER)", "0 in 20 runs (v3 blocked 6 in this campaign; fixed by the floored block rule)"],
             ["Fast decisions (FEVER)", "about 13 ms median per poll, 54 ms mean, against 123 / 127 ms for v3 (H4 supported)"],
             ["Fewest lost first packets under A4 and E9P (FEVER)", "A4 16 % against 26-33 %; E9P 29 % against 37-57 %"],
             ["Clear improvement over v3", "harm 0.49 % against 3.48 % (H3 supported)"],
             ["No side effects without an attack", "harm 0.00 %, lost first packets 0.12 % (H6)"]],
            [0.42, 0.58], tint=[(i, GOOD) for i in range(1, 10)]),
      P("Needs work", "h2"),
      table([["What", "Evidence", "Likely cause"],
             ["Standard attack A2: behind the per-flow baselines on harm", "1.05 % against 0.02 % (DMS-BTT) and 0.01 % (FTMaster); loses all 5 A2 pairs, so H1 fails", "the 60 s block expires and the attackers fill the table before the re-block (Figure 16)"],
             ["Attacker share under A2 slightly above FTMaster", "13 % against 10 %; H2 vs FTMaster 11 of 15, one pair short", "same"],
             ["The volume rule may carry most of the gain", "v4-lite (same detector, no volume rule) never blocks under A4/E9P; no volume-only run yet", "untested ablation; a reviewer will ask"],
             ["The volume rule could be evaded", "an attacker holding fewer than X (about 800) entries per switch is never volume-blocked", "untested adaptive attacker"],
             ["Detector still misses A4 and E9P on the trace domain", "A4/E9P recall about 0 % for every detector (Section 4.9)", "domain shift"],
             ["New users still suffer under attack", "only 12-47 % of new connections succeed with any defense", "the single controller saturates (87-98 % of one core)"],
             ["Narrow testbed scope", "one trace, one topology, one laptop, 5 seeds", "hardware limits"]],
            [0.3, 0.4, 0.3], tint=[(i, BAD) for i in range(1, 8)]),
      PageBreak()]

# ------------------------------------------------------------------ 6. next tests
s += [P("6. Tests we can run next", "h1"),
      P("Ordered by expected value. As before, every design choice is made on development seeds and then tested once on fresh seeds under a new preregistration.", "p"),
      table([["#", "Test", "What it would show", "Effort"],
             ["1", "<b>Volume-only ablation:</b> FEVER with the detector switched off (block by volume only)", "Whether the federated detector adds anything on the testbed. An offline replay of the FEVER recordings suggests volume-only blocks the attackers 100-175 s after the attack starts with no innocent block, later than FEVER under A2 (about 70 s)", "9 development runs (about 50 min), then part of the next campaign"],
             ["2", "<b>v6: hold the block while the attacker keeps sending</b> (release only after, say, 30 s of silence on the drop rule), or re-block a returning host at a lower bar", "Removes the A2 harm (all of it occurred after a block expired)", "small code change; development check; about 7 h campaign with FEVER, v6, DMS-BTT, FTMaster"],
             ["3", "<b>Adaptive attacker below the volume limit</b> (at most X entries per switch, more attacker hosts)", "Robustness of the volume rule; the obvious reviewer attack", "new attack variant; a few hours"],
             ["4", "<b>Relieve the controller:</b> an OpenFlow meter on Packet-Ins per access port, or the controller on a separate machine", "How much of the remaining harm to new users is controller saturation (affects every defense)", "about 1 day"],
             ["5", "<b>Exposure-aware federation</b> (weight each controller's vote by the attacks it has seen, or a local combiner)", "Whether federation can help the trace domain without dilution (the v4 and univ2 lesson)", "offline first, about 0.5 day"],
             ["6", "<b>A second trace domain</b> (univ2) as a separate test network, not a federation client", "Whether FEVER's testbed result holds on other traffic", "one overnight run"],
             ["7", "<b>Flash crowds</b> (FTOP's benign-overflow test)", "Whether the volume rule wrongly blocks a sudden legitimate surge", "a few hours"],
             ["8", "<b>More seeds</b> for the key cells", "More power: with 5 seeds a win needs 12 of 15 paired runs", "one night per 50 runs"]],
            [0.04, 0.38, 0.38, 0.2]),
      Spacer(1, 6),
      note("<b>My recommendation.</b> Tests 1 and 2 together answer the two questions a reviewer will ask first (is the ML needed, and can the A2 gap be closed) in about one day. Test 3 should follow before submission."),
      PageBreak()]

# ------------------------------------------------------------------ 7. vs papers
s += [P("7. How our experiments compare with the related papers", "h1"),
      table([["Paper", "Attacks tested", "Platform", "Our equivalent"],
             ["SFTO-Guard, FTMaster, FTODefender, FTOP, DMS-BTT (Tang et al.)", "standard LOFT with different period / step / maximum; FTODefender also spoofed sources", "Mininet + Ryu + OVS", "A2 (and A5); same platform, same table size and timeout"],
             ["FloRa", "standard LOFT at 4 rates", "Mininet + Raspberry Pi", "A2"],
             ["FTShield", "standard LOFT plus floods", "Tofino P4 hardware", "A2"],
             ["rDefender", "advanced low-rate attack replaying real traffic", "Dell hardware switch + Mininet", "A4"],
             ["ALFO-Guard", "attack adapting to the eviction policy", "Mininet + Ryu", "E9P (adapts to our defenses' parameters)"],
             ["LOFT (Cao et al.)", "the original attack; no defense", "EdgeCore hardware", "A2"]],
            [0.3, 0.3, 0.18, 0.22]),
      Spacer(1, 6),
      bullets([
          "On <b>A2</b>, the attack the other papers test, every ML defense works on our testbed. In the FEVER campaign FTMaster and DMS-BTT have the lowest harm (about 0.01-0.02 %); FEVER is close behind (1.05 %) and best for new connections (47 %).",
          "On <b>A4 and E9P</b>, which most papers do not test, every <i>detector</i> fails on the trace domain. This agrees with rDefender and ALFO, which also found that feature-based detectors degrade under disguised and adaptive attacks. FEVER still protects users there through its volume block (harm 0.10-0.32 % against 2-10 %).",
          "None of the related papers tests attacks held out from training or seen by a different controller. Our E11 benchmark fills that gap, and it is where EnsGuard clearly leads.",
          "Our numbers come from our reimplementations on one setup, so they are comparable with each other but not with the numbers printed in the papers (each paper re-runs its baselines under its own setup).",
      ]),
      P("Limitations to mention", "h2"),
      bullets([
          "One laptop and one controller: the controller saturates under attack, which affects every defense.",
          "One trace domain on the testbed; the synthetic domains are simulator-only.",
          "Reimplemented baselines; attacks from our own generator; 5 test seeds per cell.",
          "Section 4.9, Figure 16 and the per-attack breakdowns are exploratory; 4.4, 4.10 and the hypothesis table of 4.12 are preregistered.",
      ]),
      PageBreak()]

# ------------------------------------------------------------------ appendix
s += [P("Appendix: remaining figures", "h1"),
      fig(f"{FIG}/fig01_rules_over_time_A2.png", "Figure 1 (A2). Rules over time under the standard attack."),
      *shows(["Under A2 the ML defenses clear most orange (attack) rules: FTMaster and EnsGuard keep the table mostly blue; rDefender, SIFT and TableGuard leave large orange areas. This is the attack on which the ML detectors work."]),
      fig(f"{FIG}/fig01_rules_over_time_E9P.png", "Figure 1 (E9P). Rules over time under the adaptive attack."),
      *shows(["E9P fills the table faster than A2 or A4 (it refreshes every 2-3 s). Every defense lets it take most of the table; DMS-BTT, FTOP and rDefender cut it back for parts of the run, EnsGuard mainly through PortGuard's per-port cap."]),
      PageBreak(),
      fig(f"{FIG}/fig04_packet_in_over_time.png", "Figure 4. Packet-Ins per second at the controller under A4. With EnsGuard the load returns to near the no-attack level after about 200 s.", 0.8),
      *shows(["Without attack the controller handles about 130-150 Packet-Ins per second. Under A4 this rises to 250-350 with no defense or DMS-BTT; with EnsGuard it falls back to about 100-150 after 200 s, most likely because PortGuard's drop rules stop the attacker's new flows at the switch."]),
      fig(f"{FIG}/fig10_table_composition.png", "Figure 10. Table composition 150 s into A4 (attack / normal / free). rDefender keeps the most free space.", 0.8),
      *shows(["150 s into A4, the attacker holds 76-80 % of the table under the classic defenses and FTMaster, 68-70 % under DMS-BTT, FL-DualGuard and EnsGuard, 56 % under FTOP and 33 % under rDefender, whose random deletions free the most space (57 % free). Free space is what lets new users connect."]),
      fig(f"{FIG}/fig12_block_rule_sensitivity.png", "Figure 12. Block-rule settings in the simulator (development seeds). A looser threshold halves the attacker's share at slightly higher harm. On the simulator no setting blocked a normal host; on the testbed the chosen one did."),
      *shows(["The block rule's two numbers (minimum evictions n and ratio to the median host k) change attacker occupancy by only a few points; the alarm budget matters more. In the simulator, which uses dedicated ports and synthetic traffic, no setting blocks a normal host, which is why the H4 failure was not foreseen; the testbed replay (4.11) now reproduces it."]),
      PageBreak(),
      P("Glossary", "h1"),
      table([["Term", "Meaning"],
             ["Flow table", "the switch's list of forwarding rules; ours hold 3,500"],
             ["Idle timeout", "a rule is removed after 10 s without packets"],
             ["Packet-In", "a switch's question to the controller about a packet with no rule"],
             ["Table-Full", "the switch's error message when it cannot add a rule"],
             ["Attacker share (Pa)", "the share of the table held by attack rules"],
             ["Benign harm", "the share of normal flows refused, dropped by a block, or whose first packet was lost"],
             ["Recall", "the share of attack entries the detector flags"],
             ["False-positive rate", "the share of normal entries the detector flags"],
             ["PR-AUC", "how well the detector ranks attack entries above normal ones, independent of the threshold"],
             ["τ (threshold)", "the score above which an entry is evicted; set per controller so 0.1 % of its normal entries would be flagged"],
             ["Federated / model sharing", "controllers exchange trained models, never their traffic"],
             ["Preregistration", "hypotheses, seeds and tests written down before the test runs, so results cannot be tuned afterwards"],
             ["Holm correction", "adjusts p-values when one hypothesis is tested against several comparators"],
             ["Domain shift", "the deployment traffic differs from the training traffic, so learned thresholds no longer fit"],
             ["T1A / T1B", "the first 40 % / last 60 % of the bigFlows trace; every model is trained on T1A and tested on T1B"],
             ["Volume block", "FEVER's second block rule: block a host holding far more entries than any normal host, independent of the detector"]],
            [0.28, 0.72]),
      Spacer(1, 8),
      P("Sources: docs/paper_optionA.md (full draft), results/e11_detect, results/evictblock, results/testbed_prereg_v3, results/testbed_prereg_v5, results/e11_testbed, results/v4, results/v4lite, results/v5, results/paper_figs (v3 campaign) and results/paper_figs/v5. Code: loftbench/ (simulator and detectors), testbed/ (Ryu application and scripts).", "small")]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                        bottomMargin=18 * mm, title="EnsGuard status report", author="asifahmedutsa")
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print("wrote", OUT)
