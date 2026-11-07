"""Builds docs/fever_guide.pdf: FEVER explained in plain words for the supervisor meeting
(the attack, the gaps, the contributions, the architecture step by step, the setup, the results
and what is left), with the project's figures.

    PYTHONPATH=. ~/.venvs/loft/bin/python docs/build_fever_guide.py
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
TITLE = ParagraphStyle("t", fontName="LS-B", fontSize=17, leading=21, spaceAfter=4)
SUB = ParagraphStyle("s", fontName="LS-I", fontSize=10.5, leading=13, spaceAfter=14)
H1 = ParagraphStyle("h1", fontName="LS-B", fontSize=13.5, leading=17, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="LS-B", fontSize=11.2, leading=14, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("b", fontName="LS", fontSize=10.5, leading=14, spaceAfter=6)
CAP = ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, alignment=1, spaceBefore=3, spaceAfter=12)
CELL = ParagraphStyle("x", fontName="LS", fontSize=9.3, leading=11.5)
HEAD = ParagraphStyle("hd", parent=CELL, fontName="LS-B")
W = A4[0] - 44 * mm
nfig = [0]
ntab = [0]


def P(t, st=BODY):
    return Paragraph(t, st)


def bullets(items):
    return ListFlowable([ListItem(P(i), leftIndent=12, value="•") for i in items], bulletType="bullet",
                        start="•", leftIndent=12, bulletFontName="LS", bulletFontSize=10)


def steps(items):
    return ListFlowable([ListItem(P(i), leftIndent=16) for i in items], bulletType="1", leftIndent=16,
                        bulletFontName="LS", bulletFontSize=10.5)


def fig(path, cap, w=1.0, maxh=150 * mm):
    nfig[0] += 1
    iw, ih = ImageReader(path).getSize()
    sc = min(W * w / iw, maxh / ih)
    return KeepTogether([Image(path, width=iw * sc, height=ih * sc), P(f"<b>Fig. {nfig[0]}.</b> {cap}", CAP)])


def notitle(path):
    """A table image without its own "Table n / caption" lines: crop above the first full-width rule."""
    from PIL import Image as PImage
    im = PImage.open(path).convert("L")
    w, h = im.size
    px = im.load()
    for y in range(h):
        if sum(px[x, y] < 100 for x in range(0, w, 4)) > 0.8 * w / 4:
            break
    os.makedirs("results/fever_guide", exist_ok=True)
    out = "results/fever_guide/" + os.path.basename(path)
    im.crop((0, max(0, y - 4), w, h)).save(out)
    return out


def table(cap, rows, widths, head=None):
    ntab[0] += 1
    data = [[P(f"<b>{c}</b>", HEAD) for c in rows[0]]] + [[P(str(c), CELL) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return KeepTogether(([P(head, H1)] if head else []) +
                        [P(f"<b>Table {ntab[0]}.</b> {cap}", ParagraphStyle("tc", parent=BODY, spaceAfter=3)), t,
                         Spacer(1, 10)])


V6, V6P = "results/paper_figs/v6", "results/paper_figs/v6pub"
s = [P("FEVER: a plain explanation", TITLE),
     P("Federated Eviction and Volume-based Enforcement against overflow Rules. Notes for the supervisor "
       "meeting, 7 November 2026.", SUB)]

# ---------------------------------------------------------------- 1
s += [P("1. The problem: low-rate flow-table overflow (LOFT)", H1),
      P("In software-defined networking (SDN), a switch does not decide where packets go by itself. It keeps a "
        "<b>flow table</b>, a list of rules, one rule per connection. When a packet arrives that matches no rule, "
        "the switch asks the <b>controller</b> (this request is called a <b>Packet-In</b>), the controller decides, "
        "and it installs a new rule. In our setup a table holds <b>3,500 rules</b>, and a rule is deleted after "
        "<b>10 s without any packet</b> (the idle timeout)."),
      P("A LOFT attacker opens many fake connections, so the switch creates many rules for it. On each fake "
        "connection it sends one tiny packet just before the 10 s timeout. Each fake rule therefore never expires, "
        "and it costs the attacker almost nothing. Slowly the table fills with attack rules. When it is full, a "
        "normal user's new connection finds no space: it is refused or delayed. Because the attacker sends only a "
        "few small packets per second, ordinary DDoS alarms, which look for high traffic rates, never fire."),
      fig("docs/loft_attack_explained.png",
          "(a) A normal rule is removed 10 s after its last packet. (b) A LOFT rule receives one packet just before "
          "the timeout, so it stays. (c) Our testbed with no defense: attack rules (orange) push out normal rules "
          "(blue) until the table is full.", 1.0, 92 * mm),
      P("We test three versions of the attack on the testbed:"),
      table("The attacks used on the testbed.",
            [["Attack", "What it does", "Why we use it"],
             ["A2 (standard)", "100 new rules per burst, a burst every 5.5-9 s, one 64-byte packet per rule, "
              "from its own address", "The attack all related papers test"],
             ["A4 (disguised)", "Same pace, but 1-3 packets per refresh with normal-looking sizes, from a pool "
              "of addresses", "Imitates normal traffic, like rDefender's advanced attack"],
             ["E9P (defense-aware)", "Refreshes every 2-3 s with normal-looking packets; chosen by a search as "
              "the hardest attack against our defenses' settings", "Similar in spirit to ALFO's adaptive attack"]],
            [0.17, 0.53, 0.30]),
      PageBreak()]

# ---------------------------------------------------------------- 2
s += [P("2. What earlier defenses miss", H1),
      P("The related papers (SFTO-Guard, FTMaster, FTODefender, FTOP, DMS-BTT, FloRa, FTShield, rDefender, "
        "ALFO-Guard) mostly train a machine-learning model that looks at each rule and decides whether it belongs "
        "to an attacker. They then delete the attack rules, and some also block the attacker. They work well on "
        "the attack they were trained on. Five things are missing:"),
      table("Gaps in previous work.",
            [["Gap", "In plain words"],
             ["1. Each controller learns alone", "A controller only knows the attacks it has seen itself. If a "
              "neighbouring network saw a new attack, this controller still cannot recognise it."],
             ["2. Tested on the attacks they trained on", "Papers report about 99 % accuracy, but on the same kind "
              "of attack used for training. On attacks seen elsewhere the same detectors fall to about 80 %, and "
              "on a new attack to 9-25 % (Section 6.1)."],
             ["3. Disguised attacks hardly tested", "Only rDefender and ALFO test attackers who imitate normal "
              "traffic. A detector that judges how packets look fails against them."],
             ["4. Harm to users not measured", "Most papers report how full the table is, not how many normal "
              "users were refused or how overloaded the controller became."],
             ["5. Same data for training and testing", "Trace-based papers often train and test on the same "
              "capture, which makes results look better than on new traffic."]],
            [0.33, 0.67]),
      P("3. Our idea and contributions", H1),
      P("<b>The idea in one sentence.</b> Let the controllers share what they have learned (their trained models, "
        "never their traffic), and add a simple rule that does not depend on machine learning: a host that holds "
        "far more rules than anyone else is blocked, whatever its packets look like."),
      steps([
          "<b>Federated detection across controllers.</b> Each controller trains a model on its own attacks and "
          "shares the model. Every controller can then recognise attacks only the others have seen. No related "
          "paper does this.",
          "<b>Evaluation by exposure.</b> We test every detector on three groups: attacks seen in training, attacks "
          "seen only by another controller, and an attack nobody saw. This shows how detectors behave on attacks "
          "they did not train on.",
          "<b>Two signals that cover each other.</b> The detector judges <i>what a rule looks like</i>; the volume "
          "rule judges <i>how many rules a host holds</i>. When an attacker imitates normal traffic, the detector "
          "fails, but the attacker still has to hold many rules to fill the table, so the volume rule catches it.",
          "<b>A cost for the attacker.</b> To stay under the volume limit (about 800 rules per host), an attacker "
          "needs at least 4 colluding hosts on one switch to fill the table (to be tested).",
          "<b>A careful evaluation.</b> A real testbed, a clean split of the traffic into training and test parts, "
          "hypotheses fixed before the test runs, and measures of harm to users.",
      ]),
      P("<b>What is not new</b>, and should not be claimed: deleting suspicious rules, blocking the attacking host "
        "(also permanently), a fair share of the table per port, and tree-based classifiers. These all appear in "
        "earlier papers. The name FEVER stands for <b>F</b>ederated <b>E</b>viction and <b>V</b>olume-based "
        "<b>E</b>nforcement against overflow <b>R</b>ules."),
      PageBreak()]

# ---------------------------------------------------------------- 4
s += [P("4. How FEVER works", H1),
      P("FEVER has two halves. <b>Offline</b>, the controllers build a shared detector together. <b>Online</b>, "
        "every controller runs the same short loop once per second on each of its switches."),
      P("4.1 Offline: building the shared detector", H2),
      fig("docs/fever_federated_training.png",
          "Federated training: (1) each controller trains locally, (2) uploads its model, (3) the models are "
          "combined, (4) every controller downloads the shared detector.", 0.85, 105 * mm),
      steps([
          "<b>Three controllers with different experience.</b> D1 has seen attacks A1 and A4, D2 has seen A2 and A5, "
          "D3 has seen A3 and A7. Nobody has seen A6 or E9P; we keep those to test new attacks.",
          "<b>Each trains a CatBoost model</b> (a fast tree-based classifier) on its own normal traffic and attacks. "
          "Each rule is described by 17 numbers (features): 11 about the connection (packet rate, gaps between "
          "packets, packet sizes), 3 about the host that created it, and 3 about the table (how full it is, how "
          "fast it changes).",
          "<b>Models are shared, data is not.</b> The shared detector runs all three models on a rule and takes the "
          "average of their attack probabilities. If any one controller has seen this kind of attack, its model "
          "gives a high score and lifts the average. (This is model sharing; it is not FedAvg, which averages the "
          "models' weights.)",
          "<b>Each controller sets its own limits from its own normal traffic:</b> the score threshold τ = 0.620, "
          "chosen so that only 1 in 1,000 normal rules scores above it, and the volume limit X of about 800 rules, "
          "1.5 times the busiest normal host ever seen. On the testbed both come from the training part of the "
          "traffic only.",
      ]),
      PageBreak(),
      P("4.2 Online: the loop every second", H2),
      fig("docs/fever_architecture.png",
          "FEVER architecture: attack detection (left) and attack mitigation (right) on each controller; the "
          "shared detector comes from federated training (bottom).", 0.92, 130 * mm),
      P("Read the left column from top to bottom, then the right column from bottom to top:"),
      table("The online loop, step by step, and why each step is there.",
            [["Step", "What happens", "Why"],
             ["1 Poll", "Read every rule's counters (packets, bytes, age, source host and port) and how full the "
              "table is.", "Everything below needs these numbers."],
             ["2 Gate (TH1)", "Continue only if the table is at least 70 % full.", "Below 70 % there is no danger; "
              "this saves controller time."],
             ["3 Features", "Compute the 17 features, only for rules whose counters changed.", "Scoring unchanged "
              "rules again is wasted work."],
             ["4 Score", "The three shared models score each rule.", "Recognise attack rules, including attacks "
              "only other controllers saw."],
             ["5 Evict", "Delete every rule scoring at least τ.", "Frees space at once."],
             ["6 Block rule A", "Block a host whose evictions in 10 s are at least 50, at least 3 times the median "
              "host's (counted as at least 10), and at least 20 % of its own rules.", "Otherwise the attacker simply "
              "creates new rules. The floors keep a busy normal host from being blocked over a few false alarms."],
             ["7 Block rule B (volume)", "If the table is at least 90 % full (TH2): block a host holding more than X "
              "rules and at least 3 times the median host's.", "Catches disguised attackers the detector cannot "
              "see: whatever they look like, they must hold many rules."],
             ["8 Fair share", "If the table is still at least 90 % full, each port keeps a weighted fair share; the "
              "highest-scoring rules above it are removed.", "A safety net for anything both rules miss."]],
            [0.17, 0.45, 0.38]),
      P("<b>Blocking</b> means a drop rule at the host's switch port: its packets no longer reach the table or the "
        "controller. In the current version (v6) the block is <b>permanent</b>. The earlier version (v5) released "
        "the host after 60 s, and under A2 the attackers came back and filled the table again (Section 6.3)."),
      fig("docs/fever_flowchart.png", "The same loop as a flowchart (TH1 = 70 %, TH2 = 90 %).", 0.92, 110 * mm),
      PageBreak(),
      P("4.3 What happens during an attack", H2),
      P("<b>Under A2 (standard).</b> The attack rules accumulate until the table passes 70 %. The detector "
        "recognises them (D2 trained on A2), so they are evicted. Each attacker's evictions soon pass 50 in 10 s and "
        "stand far above everyone else's, so block rule A blocks both attackers, about 70 s after the attack starts. "
        "Their rules disappear and, because the block is permanent, they never return."),
      P("<b>Under A4 and E9P (disguised).</b> The attack rules look normal, so the detector scores them low and "
        "evicts few. The table keeps filling. Once it passes 90 %, each attacker holds far more than X rules, far "
        "more than any normal host, and block rule B blocks it, about 70-125 s after the attack starts."),
      fig(f"{V6}/fig20_malicious_share_A2.png",
          "Share of attack rules in the table with FEVER under A2 (one testbed run): it rises until both "
          "attackers are blocked, then stays near 0 %.", 0.8, 70 * mm),
      PageBreak()]

# ---------------------------------------------------------------- 5
s += [P("5. How we tested", H1),
      P("5.1 Detection benchmark (offline)", H2),
      P("Every detector, ours and the published ones, is trained and scored on exactly the same data from three "
        "simulated networks (D1-D3), at a false-alarm rate of 0.1 %. We report each detector on attacks seen in "
        "training, attacks seen only by another controller, and an attack nobody saw."),
      P("5.2 Testbed (online)", H2),
      bullets([
          "<b>Software:</b> Mininet (a virtual network on one laptop), Open vSwitch, the Ryu controller, OpenFlow "
          "1.3. Flow table 3,500 rules, idle timeout 10 s, the same as the Tang et al. papers.",
          "<b>Topology:</b> a core switch connected to the server, two access switches, each with two normal users "
          "and one attacker (Fig. 6 and Fig. 7).",
          "<b>Normal traffic:</b> a real traffic capture (bigFlows) replayed. Its first 40 % (T1A) is used only for "
          "training models and setting limits, for every method; its last 60 % (T1B) only for testing.",
          "<b>Each run</b> lasts 300 s; the attack starts at 50 s. Five runs per case (seeds 4140-4144), one run at "
          "a time on an otherwise idle laptop.",
          "<b>Preregistration:</b> the hypotheses and tests were written down and committed before the test runs.",
          "<b>Methods compared:</b> no defense, FTMaster, DMS-BTT, rDefender, FEVER (and earlier EVICT, SIFT, "
          "TableGuard, FTOP and our older versions). All were reimplemented and retrained on T1A. Our DMS-BTT has "
          "a 60 s blocklist that the original paper does not have, so it is stronger than published.",
      ]),
      fig("docs/fever_federated_topology.png",
          "Experiment topology: three domains train and share models; the shared detector is used in the test "
          "domain (the testbed).", 0.8, 105 * mm),
      fig("docs/fever_testbed_topology.png", "Network topology of the testbed.", 0.7, 90 * mm),
      table("What we measure.",
            [["Measure", "Meaning", "Better"],
             ["Benign flows harmed", "Normal connections refused or failed", "lower; the most important"],
             ["Attacker share", "Part of the core table held by attack rules", "lower"],
             ["Lost first packets", "Normal Packet-In requests the overloaded controller drops", "lower"],
             ["New connections succeeding", "A probe keeps opening new connections; how many work", "higher"],
             ["Decision time", "Time the controller needs per poll", "lower"],
             ["Innocent hosts blocked", "Normal users wrongly cut off", "must be 0"]],
            [0.27, 0.53, 0.20]),
      PageBreak()]

# ---------------------------------------------------------------- 6
s += [P("6. Results", H1),
      P("6.1 Detection: sharing models helps on attacks a controller never saw", H2),
      fig(notitle("docs/fever_table_detection.png"), "Detection results at a 0.1 % false-alarm rate (same data for all).",
          1.0, 60 * mm),
      bullets([
          "On attacks used in training, every detector is good (F1 95-99 %).",
          "On attacks seen only by another controller, FEVER keeps 98.6 % recall; the published detectors fall to "
          "79-82 %. This is the direct benefit of sharing models.",
          "On the attack nobody saw, FEVER catches 51 %, the others 9-25 %.",
      ]),
      P("6.2 Testbed: FEVER against the published methods", H2),
      table("Testbed results, mean of five runs per attack (A2, A4, E9P); FEVER with permanent blocking (v6).",
            [["", "FEVER", "DMS-BTT", "FTMaster", "No defense"],
             ["Benign flows harmed (all attacks)", "<b>0.01 %</b>", "1.71 %", "4.80 %", "10.13 %"],
             ["Benign flows harmed under A2", "<b>0.01 %</b>", "0.02 %", "0.01 %", "-"],
             ["Benign flows harmed under A4", "<b>0.02 %</b>", "2.09 %", "4.16 %", "-"],
             ["Benign flows harmed under E9P", "<b>0.00 %</b>", "3.01 %", "10.22 %", "-"],
             ["Attacker share of the table", "<b>11.9 %</b>", "41.9 %", "45.5 %", "62.1 %"],
             ["Lost first packets", "<b>9.6 %</b>", "32.6 %", "27.8 %", "-"],
             ["New connections succeeding", "<b>37.3 %</b>", "23.4 %", "23.7 %", "-"],
             ["Attackers blocked", "30 of 30", "0", "0", "-"],
             ["Innocent hosts blocked", "0", "0", "0", "-"]],
            [0.38, 0.155, 0.155, 0.155, 0.155]),
      P("FEVER is best or tied on every measure under every attack. Under A2 it ties the two published methods on "
        "harm and is better on everything else; under the disguised attacks it is far better."),
      fig(f"{V6P}/fig25_a2_share_over_time.png",
          "Attacker share of the table over time under A2 (median of five runs). FEVER drops it to 0 % at about "
          "120 s and keeps it there.", 0.9, 75 * mm),
      fig(f"{V6P}/fig03_comparison.png", "Comparison under all three attacks (bar: mean; whisker: range).",
          1.0, 100 * mm),
      PageBreak(),
      P("6.3 Why permanent blocking (v5 against v6)", H2),
      P("In the preregistered campaign (120 runs), FEVER blocked a host for only 60 s. It already won under A4 and "
        "E9P, but lost under A2 (harm 1.05 % against 0.01-0.02 %): when the block expired, the attackers came back "
        "and filled the table again. Version v6 changes only this one setting: a blocked host stays blocked, as in "
        "FTMaster, FTODefender and FloRa. The change and its acceptance test were written down before running it."),
      table("FEVER v5 (60 s block) and v6 (permanent block) on the same runs.",
            [["", "v6", "v5"],
             ["Benign flows harmed under A2", "0.01 %", "1.05 %"],
             ["Benign flows harmed, all attacks", "0.01 %", "0.49 %"],
             ["Attacker share", "11.9 %", "21.9 %"],
             ["Lost first packets", "9.6 %", "19.8 %"],
             ["Innocent hosts blocked", "0", "0"]],
            [0.5, 0.25, 0.25]),
      P("6.4 Which part does what (ablation)", H2),
      fig(f"{V6}/fig23_ablation.png",
          "Ablation (60 s-block version, three runs per attack): FEVER, FEVER without the volume rule, FEVER "
          "without the detector, and rDefender.", 1.0, 70 * mm),
      bullets([
          "<b>Without the volume rule</b>, harm under A4 and E9P rises to 1.11 % and 3.89 % and the attackers are "
          "never blocked: the volume rule is what stops disguised attacks.",
          "<b>Without the detector</b>, the A2 attackers are blocked at about 130 s instead of 71 s and keep 30 % of "
          "the table instead of 11 %: the detector stops standard attacks faster.",
          "So the two signals cover each other's blind spot.",
      ]),
      P("6.5 Cost", H2),
      fig(notitle("docs/fever_overhead_table1.png"), "Controller overhead on the testbed.", 1.0, 50 * mm),
      P("FEVER decides in about 11 ms per poll (DMS-BTT 65 ms, FTMaster 72 ms) and adds about 1 % CPU without an "
        "attack. It uses the most memory (+75 MB peak), because three models are loaded.")]

# ---------------------------------------------------------------- 7
s += [P("7. What we still need to do", H1),
      table("Open points.",
            [["Weak point", "What we will do"],
             ["The v6 result is not yet a clean test: v6 was designed after seeing the A2 result and ran on the same "
              "seeds.", "One final campaign on new seeds (4160-4164) with every method, about 160 runs (14 h)."],
             ["FTODefender, FTOP and FloRa are not yet in the testbed comparison.", "FTODefender is implemented; "
              "train it on T1A, then include all three in the final campaign."],
             ["A wrongly blocked host is cut off for good. The busiest normal host holds about 580 rules against a "
              "limit of about 800.", "Test a busy but legitimate host (for example a NAT gateway). Later: release "
              "a host with a cap on its rules."],
             ["An attacker could spread over many hosts to stay under the volume limit.", "Adaptive-attacker test, "
              "and write up the cost (at least 4 hosts per switch)."],
             ["On the testbed, the shared detector does not catch disguised attacks; the volume rule does.",
              "Present federation (offline evidence) and the volume rule (testbed evidence) as separate "
              "contributions."],
             ["New users still suffer under every defense (37 % of new connections succeed).", "The single controller "
              "is overloaded; test a Packet-In rate limit or a separate controller machine."],
             ["Narrow scope: one laptop, one trace, one topology, five seeds, 300 s runs.", "A second trace as a "
              "separate test network; more seeds; state it in the limitations."]],
            [0.52, 0.48]),
      P("Target venue: NetSoft 2027 (deadline around late January 2027)."),
      P("8. Questions to expect", H1),
      table("Likely questions and short answers.",
            [["Question", "Answer"],
             ["Is this really federated learning?", "It is federated model sharing: models are trained locally and "
              "shared, and their predictions are averaged. Not FedAvg. No traffic leaves a network."],
             ["Why not use only the volume rule?", "Without the detector, standard attacks are blocked about 60 s "
              "later and keep three times more of the table (Section 6.4)."],
             ["Why did v5 lose under A2?", "Its 60 s block expired, the attackers returned and refilled the table. "
              "Permanent blocking fixed it."],
             ["Is permanent blocking safe?", "No innocent host was blocked in 40 runs, but the margin is small; the "
              "busy-host test will check it."],
             ["Why are DMS-BTT and FTMaster so good under A2?", "They were trained on A2 traffic from the same network "
              "and delete attack rules every second. Our DMS-BTT also has an added 60 s blocklist."],
             ["Is the comparison fair?", "Every method is retrained on the same training data and run on the same "
              "testbed and seeds. The numbers are not comparable with those printed in the papers, because each "
              "paper uses its own setup."],
             ["What is new compared with rDefender?", "rDefender limits each port's share but never finds or blocks "
              "the attacker. FEVER identifies the attacking host, by detector or by volume, and removes it."]],
            [0.34, 0.66]),
      table("Glossary.",
            [["Word", "Meaning"],
             ["Flow table / rule", "The switch's list of forwarding instructions, one per connection"],
             ["Idle timeout", "A rule is deleted after this long (10 s) without packets"],
             ["Controller / Packet-In", "The program that installs rules; the switch's request to it for a new rule"],
             ["Evict", "Delete a rule from the table"],
             ["Block", "Drop all packets of a host at its switch port"],
             ["τ (tau)", "The score above which a rule is treated as an attack rule"],
             ["X", "The volume limit: the number of rules above which a host is suspicious"],
             ["TH1 / TH2", "Table fullness at which scoring starts (70 %) and the volume rule acts (90 %)"],
             ["T1A / T1B", "Training part (first 40 %) and test part (last 60 %) of the traffic capture"],
             ["Seed", "A number fixing the random choices of one run, so it can be repeated"],
             ["Recall / F1", "Share of attack rules caught / a balance of recall and precision"]],
            [0.27, 0.73], head="9. Words used")]

SimpleDocTemplate("docs/fever_guide.pdf", pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=18 * mm,
                  bottomMargin=18 * mm, title="FEVER explained", author="asifahmedutsa").build(s)
print("wrote docs/fever_guide.pdf")
