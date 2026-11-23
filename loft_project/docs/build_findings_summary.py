"""Builds docs/fever_findings_summary.pdf: the findings of the testbed experiments in plain words, a
few sentences each. Numbers from results/testbed_prereg_final (report.md, tests.csv, paper/*.tex),
results/tbfl, results/testbed_flash2, results/testbed_crowdseeds, results/testbed_scale and
results/testbed_sens.

    ~/.venvs/loft/bin/python docs/build_findings_summary.py
"""
import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

OUT = "docs/fever_findings_summary.pdf"
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")

S = {
    "title": ParagraphStyle("title", fontName="LS-B", fontSize=14, leading=18, alignment=1, spaceAfter=12),
    "h": ParagraphStyle("h", fontName="LS-I", fontSize=11, leading=14, spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="LS", fontSize=11, leading=15, spaceAfter=5, alignment=4),
}


def P(t, s="p"):
    # Keep a number on the same line as its unit.
    return Paragraph(re.sub(r"(\d) (%|s\b|ms\b|GB\b|MB\b)", r"\1&nbsp;\2", t), S[s])


FINDINGS = [
    ("Normal traffic is protected best",
     "FEVER harmed only 0.011 % of benign flows. The six other defenses harmed between 1.0 % and 5.2 %. "
     "FEVER also kept 84 % of new connections working during the attacks, while the others kept only 21 % "
     "to 46 %. Under G2, Spoof, Pulse and Mimic almost every new connection went through (97 % to 99 %). In "
     "the runs without any attack, FEVER did not harm a single benign flow. Both results were confirmed by "
     "the statistical tests against every one of the six defenses."),
    ("The attackers get the smallest part of the flow table",
     "On average the attackers held 6.8 % of the flow table under FEVER, and between 24 % and 36 % under "
     "the other defenses. FTODefender is the one exception: it kept G2, Pulse and EVX lower than FEVER, at "
     "about 0.2 %. However, it did this by deleting many entries, and it harmed 3.4 % of benign flows and "
     "let only 46 % of new connections through."),
    ("The biggest gain is against attacks that look like normal traffic",
     "Mimic and Aware use many source addresses and normal packet sizes, so they are hard to tell apart "
     "from benign flows. Under these two attacks FEVER held the attackers to 4.9 % and 14.1 % of the table, "
     "while the other defenses left them 33 % to 49 %. FEVER stayed ahead even when the other defenses "
     "were trained on the data of all three controllers together (9.5 % against 21 % to 39 %), and on the "
     "UHt traffic that no controller had trained on (7.7 % against 37 % to 41 %)."),
    ("Federated training lets a controller recognise attacks it has never seen",
     "Each controller trained on its own traffic and its own two attacks. When it trained alone, controller "
     "C3 detected only 0.2 % of the Mimic flows. With federated training it detected 61 %, and on all "
     "attacks seen only by another controller its recall rose from 75.8 % to 90.5 %. No traffic records or "
     "labels were shared; the controllers exchanged only summed statistics. On the testbed this blocked "
     "the Mimic attackers 64 s earlier, lowered their share of the table from 15.7 % to 4.9 %, and raised "
     "new-connection success from 63 % to 98 %. Other federated methods (FedAvg, FedProx and federated "
     "tree bagging) gave no such gain. Our lossless federated XGBoost did as well as training on all data "
     "in one place, and needed 2.6 GB of exchanged data and 38 s of training."),
    ("Blocking at the access port matters most",
     "We removed each part of FEVER in turn. Without blocking the attacker at its access port, the attackers "
     "kept 23 % to 35 % of the table, because the entries FEVER evicted were simply installed again. "
     "Without the volume rule, the attackers' share under Aware rose from 14 % to 43 %. Without the "
     "detector, the attackers were blocked 35 s to 55 s later. Without federated training, the share under "
     "Mimic rose from 4.9 % to 15.7 %. So every part is needed for at least one attack."),
    ("A flash crowd from a single host can be mistaken for an attack",
     "A sudden rise in normal traffic should not be mistaken for an attack. We added three short bursts "
     "of new benign flows to each run, with no attacker present, in a table small enough for the bursts "
     "to fill it. When the crowd was spread over the four normal hosts, no defense blocked a normal host, "
     "and FEVER harmed only 0.02 % of benign flows. When one host sent the whole crowd, FEVER blocked "
     "that host in two of the three runs, and its harm rose to 4.9 %. In ten more runs with one host sending "
     "the crowd, FEVER blocked it in nine, mostly during the first crowd, so that host was cut off for most "
     "of the run and FEVER's harm was 20.8 %, against 0.06 % without a defense. No other defense blocked a host, "
     "although FTOP and DMS-BTT deleted about 140 to 250 benign entries per minute."),
    ("FEVER still works with more attackers",
     "We repeated G2 and EVX with four and eight attackers instead of two. FEVER blocked every G2 attacker "
     "and kept the attackers' share below that of FTMaster and DMS-BTT in every paired run. EVX attackers "
     "can hide below FEVER's volume limit when there are only two of them, but with four or more they fill "
     "the table and FEVER caught 32 of the 36. With eight attackers the controller was close to its limit, "
     "so blocks came later, but FEVER still harmed only 0.9 % (G2) and 2.0 % (EVX) of benign flows, against "
     "16.3 % and 12.1 % without any defense."),
    ("FEVER does not depend on fine tuning",
     "FEVER has three fixed settings: how full the table must be before it starts evicting, how far above "
     "the other hosts a host's evictions must be before it is blocked, and the volume limit. We made each "
     "one lower and higher, one at a time, in 90 more runs. In 17 of 18 cases the attackers' share of the "
     "table and the harm to benign flows stayed close to FEVER's, and no setting blocked a normal host when "
     "there was no attack. The one exception was starting eviction later (at 80 % instead of 70 %): under "
     "Mimic the attackers were blocked 27 s later and held 15 % of the table instead of 5 %. No setting "
     "stopped FEVER from blocking a host that sent a whole flash crowd; every setting blocked it in all three "
     "runs."),
    ("FEVER is light on the controller",
     "FEVER needed 20.8 ms per decision, almost the same as running without a defense (19.4 ms) and less "
     "than every other defense (35 ms to 103 ms). It also used the least controller CPU, 62 % against "
     "70 % to 78 %. Its memory use was the highest, 253 MB against 191 MB to 233 MB, because it keeps a "
     "300-tree model in memory."),
    ("Two attacks are not stopped",
     "No method could stop the Slow attack, which uses spoofed addresses and a very slow refresh: every "
     "method, FEVER included, left about 20 % of the table to the attackers. With only two attackers, EVX "
     "stayed below FEVER's volume limit and kept 17.7 % of the table, while FTODefender, DMS-BTT and FloRa "
     "held it between 0.2 % and 14.3 %."),
]

story = [
    P("FEVER: summary of findings", "title"),
    P("FEVER protects SDN switches against low-rate flow table overflow attacks. Three controllers train "
      "one shared detector without sharing their traffic, and each controller uses it to evict attack "
      "entries and to block attacking hosts at their access port. We compared FEVER with six published "
      "defenses (FTMaster, FTOP, FTODefender, FloRa, DMS-BTT and rDefender) on a Mininet testbed with real "
      "traffic and seven attacks, in 532 runs whose tests were fixed in advance. We then ran three more "
      "studies: benign flash crowds, four or eight attackers instead of two, and FEVER with its settings "
      "changed. The findings are below."),
]
for i, (head, text) in enumerate(FINDINGS, 1):
    story += [P(f"{i}. {head}", "h"), P(text)]

SimpleDocTemplate(OUT, pagesize=A4, leftMargin=24 * mm, rightMargin=24 * mm, topMargin=22 * mm,
                  bottomMargin=22 * mm, title="FEVER: summary of findings").build(story)
print("written", os.path.abspath(OUT))
