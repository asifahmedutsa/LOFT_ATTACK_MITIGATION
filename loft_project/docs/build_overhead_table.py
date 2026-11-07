"""Builds docs/fever_overhead_table.pdf: CPU and memory overhead of FEVER against the published
methods. Table 1 is measured on our testbed (results/paper_figs/v5/testbed_runs.csv, v5 campaign);
Table 2 lists the overhead each paper reports on its own setup (Other Paper/experiments_summary.md).

    ~/.venvs/loft/bin/python docs/build_overhead_table.py
"""
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = "docs/fever_overhead_table.pdf"
FD = "/usr/share/fonts/truetype/liberation/"
for n, f in (("LS", "LiberationSerif-Regular.ttf"), ("LS-B", "LiberationSerif-Bold.ttf"),
             ("LS-I", "LiberationSerif-Italic.ttf"), ("LS-BI", "LiberationSerif-BoldItalic.ttf")):
    pdfmetrics.registerFont(TTFont(n, FD + f))
pdfmetrics.registerFontFamily("LS", normal="LS", bold="LS-B", italic="LS-I", boldItalic="LS-BI")
S = dict(cap=ParagraphStyle("c", fontName="LS", fontSize=9.5, leading=12, spaceBefore=12, spaceAfter=4),
         cell=ParagraphStyle("x", fontName="LS", fontSize=9, leading=11),
         note=ParagraphStyle("n", fontName="LS", fontSize=8.8, leading=11.5, textColor=colors.HexColor("#333333"),
                             spaceBefore=4))
W = A4[0] - 44 * mm


def table(caption, head, rows, widths, note=None):
    data = [[Paragraph(f"<b>{h}</b>", S["cell"]) for h in head]]
    data += [[Paragraph(str(c), S["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    parts = [Paragraph(caption, S["cap"]), t]
    if note:
        parts.append(Paragraph(note, S["note"]))
    return KeepTogether(parts + [Spacer(1, 10)])


r = pd.read_csv("results/paper_figs/v5/testbed_runs.csv")
att, ben = r[r.variant != "benign"], r[r.variant == "benign"]
NAME = [("none", "None"), ("ftmaster", "FTMaster"), ("dms-btt", "DMS-BTT"), ("ensguard-v5", "FEVER")]
base_mem = att[att.defense == "none"].mem_mb.mean()
base_idle = ben[ben.defense == "none"].cpu_pct.mean()
rows = []
for k, name in NAME:
    a, b = att[att.defense == k], ben[ben.defense == k]
    rows.append([name, f"{b.cpu_pct.mean():.1f}", f"{b.cpu_pct.mean() - base_idle:+.1f}" if k != "none" else "-",
                 f"{a.cpu_pct.mean():.1f}",
                 f"{a.mem_mb.mean():.0f}", f"{a.mem_mb.mean() - base_mem:+.0f}" if k != "none" else "-",
                 f"{a.decision_ms_median.mean():.0f}"])
c = lambda t: Paragraph(f"<b>{t}</b>", ParagraphStyle("h", parent=S["cell"], alignment=1))  # noqa: E731
v = lambda t: Paragraph(str(t), ParagraphStyle("v", parent=S["cell"], alignment=1))  # noqa: E731
data = [[c("Method"), c("CPU usage (%)"), "", "", c("Memory (MB)"), "", c("Time per decision (ms)")],
        ["", c("No attack"), c("Increase over no defense"), c("Under attack"), c("Peak"),
         c("Increase over no defense"), ""]]
data += [[Paragraph(r[0], S["cell"])] + [v(x) for x in r[1:]] for r in rows]
t1 = Table(data, colWidths=[w * W for w in (0.14, 0.12, 0.16, 0.13, 0.11, 0.16, 0.18)])
t1.setStyle(TableStyle([("SPAN", (1, 0), (3, 0)), ("SPAN", (4, 0), (5, 0)), ("SPAN", (0, 0), (0, 1)),
                        ("SPAN", (6, 0), (6, 1)),
                        ("LINEABOVE", (0, 0), (-1, 0), 0.9, colors.black),
                        ("LINEBELOW", (1, 0), (3, 0), 0.4, colors.black), ("LINEBELOW", (4, 0), (5, 0), 0.4, colors.black),
                        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.black),
                        ("LINEBELOW", (0, -1), (-1, -1), 0.9, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
s = [KeepTogether([Paragraph("<b>Table 1</b><br/>System overhead of each method.", S["cap"]), t1, Spacer(1, 10)])]

pub = [["SFTO-Guard", "+1.64 %", "-", "Mininet + Ryu"],
       ["FTMaster", "+2.38 %", "230", "Mininet + Ryu"],
       ["FTODefender", "about +4 %", "175", "Mininet + Ryu"],
       ["FTOP", "about +18 %", "129", "Mininet + Ryu"],
       ["FloRa", "1.86 %", "217", "Mininet + Raspberry Pi"],
       ["ALFO-Guard", "+5.19 %", "+206", "Mininet + Ryu"],
       ["DMS-BTT", "+10 to 15 %", "-", "Mininet + Ryu"],
       ["FEVER", f"{ben[ben.defense == 'ensguard-v5'].cpu_pct.mean() - base_idle:+.1f} %",
        f"{att[att.defense == 'ensguard-v5'].mem_mb.mean():.0f} ({att[att.defense == 'ensguard-v5'].mem_mb.mean() - base_mem:+.0f})",
        "Mininet + Ryu"]]
s.append(table("<b>Table 2</b><br/>System overhead reported by each method.",
               ["Method", "CPU", "Memory (MB)", "Platform"], pub, [0.25, 0.22, 0.25, 0.28],
               "Values as reported in each paper on its own setup; - : not reported. FEVER: CPU added with no attack and "
               "peak memory (added memory) from Table 1."))

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm,
                        bottomMargin=20 * mm, title="FEVER overhead", author="asifahmedutsa")
doc.build(s)
print("wrote", OUT)
