"""Builds docs/fever_figures.pdf: every FEVER figure and result table in one document, one figure
per caption, in the order of a paper (system design, attack behaviour, results, tables). Campaign
figures are the published-methods versions (results/paper_figs/v5pub, testbed/paper_figs.py --v5 --pub).

    ~/.venvs/loft/bin/python docs/build_figures_pdf.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
TITLE = ParagraphStyle("t", fontName="LS-B", fontSize=15, leading=19, spaceAfter=10)
SEC = ParagraphStyle("s", fontName="LS-B", fontSize=12, leading=15, spaceBefore=6, spaceAfter=8)
CAP = ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, alignment=1, spaceBefore=4, spaceAfter=16)
W, H = A4[0] - 40 * mm, A4[1] - 50 * mm
V, P = "results/paper_figs/v5", "results/paper_figs/v5pub"

SECTIONS = [
    ("System design", [
        ("docs/fever_architecture.png", "Architecture of FEVER."),
        ("docs/fever_flowchart.png", "Framework of FEVER."),
        ("docs/fever_working.png", "Working of FEVER."),
        ("docs/fever_federated_training.png", "Federated training of FEVER's detector: (1) local training, (2) model "
         "upload, (3) aggregation, (4) download of the shared detector."),
        ("docs/fever_federated_topology.png", "Experiment topology: three SDN domains and the test domain."),
        ("docs/fever_testbed_topology.png", "Network topology for evaluation."),
    ]),
    ("Flow table under attack without defense", [
        (f"{V}/fig17_states_A2.png", "Distribution of FN and of the entries held per host before and after the A2 attack."),
        (f"{V}/fig17_states_A4.png", "Distribution of FN and of the entries held per host before and after the A4 attack."),
        (f"{V}/fig18_apit_no_defense.png", "APIT before and after the attacks."),
    ]),
    ("Mitigation results on the testbed", [
        (f"{P}/fig03_comparison.png", "Comparison of the defenses under A2, A4 and E9P (five runs each; bar: mean, "
         "whisker: range)."),
        (f"{P}/fig15_per_attack_per_seed.png", "Benign flows harmed and attack share under each attack (bar: mean of "
         "five runs; dot: one run)."),
        (f"{P}/fig01_rules_over_time_A2.png", "Benign and attack rules in the flow table over time under A2."),
        (f"{P}/fig01_rules_over_time_A4.png", "Benign and attack rules in the flow table over time under A4."),
        (f"{P}/fig01_rules_over_time_E9P.png", "Benign and attack rules in the flow table over time under E9P."),
        (f"{P}/fig02_attack_share_over_time.png", "Attack-rule share of the flow table over time."),
        (f"{V}/fig20_malicious_share_A2.png", "Percentage of malicious flows in the flow table with FEVER under A2."),
        (f"{P}/fig16_a2_block_expiry.png", "Flow-table entries over time under A2."),
        (f"{P}/fig10_table_composition.png", "Composition of the flow table 150 s into the A4 attack."),
        (f"{V}/fig19_messages_A2.png", "The quantity of Packet-In and Table-Full messages under A2."),
        (f"{V}/fig19_messages_A4.png", "The quantity of Packet-In and Table-Full messages under A4."),
        (f"{V}/fig19_messages_E9P.png", "The quantity of Packet-In and Table-Full messages under E9P."),
        (f"{P}/fig04_packet_in_over_time.png", "Packet-In messages per second at the controller under A4."),
        (f"{P}/fig05_packet_in_loss.png", "Benign first packets lost at the controller and benign flows harmed."),
        (f"{P}/fig06_new_flow_service.png", "New connections that succeed and their connection time."),
    ]),
    ("Overhead", [
        (f"{P}/fig07_decision_time.png", "Decision time per poll under attack."),
        (f"{P}/fig08_cpu_memory.png", "Controller CPU and memory under attack."),
        (f"{V}/fig21_cpu_A2.png", "CPU usage of the controller under A2."),
        (f"{V}/fig22_overhead_A2.png", "System overhead of deploying FEVER."),
    ]),
    ("Ablation", [
        (f"{V}/fig23_ablation.png", "Ablation of FEVER: benign flows harmed and attack share under each attack."),
    ]),
    ("Tables", [
        ("docs/fever_table_overall.png", None),
        ("docs/fever_table_per_attack.png", None),
        ("docs/fever_table_detection.png", None),
        ("docs/fever_table_ablation.png", None),
        ("docs/fever_overhead_table1.png", None),
    ]),
]


def image(path, maxw=W, maxh=H * 0.78):
    iw, ih = ImageReader(path).getSize()
    sc = min(maxw / iw, maxh / ih)
    return Image(path, width=iw * sc, height=ih * sc)


story = [Paragraph("FEVER: figures", TITLE)]
n = 0
for sec, items in SECTIONS:
    story.append(Paragraph(sec, SEC))
    for path, cap in items:
        if cap is None:                      # tables carry their own caption
            story.append(KeepTogether([image(path, maxh=H * 0.45), Spacer(1, 14)]))
            continue
        n += 1
        story.append(KeepTogether([image(path), Paragraph(f"<b>Fig. {n}.</b> {cap}", CAP)]))
    if sec != SECTIONS[-1][0]:
        story.append(PageBreak())
SimpleDocTemplate("docs/fever_figures.pdf", pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm,
                  bottomMargin=20 * mm, title="FEVER figures", author="asifahmedutsa").build(story)
print("wrote docs/fever_figures.pdf with", n, "figures")
