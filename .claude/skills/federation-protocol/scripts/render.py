"""Lay the federation protocol out as PDF: one file per part of the event.

    uv run --with reportlab==4.4.4 python \
        .claude/skills/federation-protocol/scripts/render.py \
        DATA.json EVENT.json OUT_DIR

DATA.json comes from collect.py. EVENT.json carries every word the protocol prints
that the race data does not -- letterhead, titles, labels, judge and secretary,
corrections -- and the parts: one PDF each, with its own title and its groups in the
order they are printed; see event-template.json.

The layout is the federation's own, from its scanned template: per part, the
letterhead, the title and the date line, one table of final places per group, the
judge and the secretary; then the qualification as one table with a grey row per
group, and the signatures again. No signatures or stamps are drawn.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from standings import group_standings

# Times New Roman, as the template; it carries the Kazakh letters the names need
# (U+049A, U+04AF, U+04D9, U+04B1, U+04A3). Liberation Serif is its metric twin on
# Linux.
FONTS = [
    (
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    ),
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf"),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ),
]
GREY = colors.HexColor("#D9D9D9")
# Sized to the widest value of each column at 11 pt, with room to spare in the place
# column (a three-letter mark such as "DNQ" needs 1.05 cm), so no mark, team or date
# breaks onto a second line; only a coach list of three names does, as on the template.
FINAL_COLS = [1.2 * cm, 0.85 * cm, 4.3 * cm, 2.1 * cm, 2.7 * cm, 5.55 * cm]
QUAL_COLS = [1.2 * cm, 0.85 * cm, 4.3 * cm, 2.1 * cm, 1.55 * cm, 6.7 * cm]


def register_fonts() -> None:
    for regular, bold in FONTS:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("Serif", regular))
            pdfmetrics.registerFont(TTFont("Serif-B", bold))
            return
    sys.exit("no Times New Roman (or Liberation Serif) found; add its path to FONTS")


def styles() -> dict[str, ParagraphStyle]:
    bold, plain = "Serif-B", "Serif"
    spec = {
        "letter": (bold, 14, 16.5, TA_CENTER),
        "title": (bold, 15, 18, TA_CENTER),
        "date": (bold, 13, 15, TA_LEFT),
        "city": (bold, 13, 15, TA_RIGHT),
        "cell": (plain, 11, 12.6, TA_LEFT),
        "sign": (bold, 13, 15, TA_LEFT),
        "sign_r": (bold, 13, 15, TA_RIGHT),
    }
    return {
        name: ParagraphStyle(
            name, fontName=font, fontSize=size, leading=lead, alignment=align
        )
        for name, (font, size, lead, align) in spec.items()
    }


def fix(text: str, event: dict[str, Any]) -> str:
    """The corrections the organizer approved, applied to the printed text only."""
    for wrong, right in event.get("corrections", {}).items():
        text = text.replace(wrong, right)
    return text


class Protocol:
    def __init__(self, data: dict[str, Any], event: dict[str, Any]) -> None:
        self.data, self.event, self.st = data, event, styles()

    def p(self, text: str, style: str = "cell") -> Paragraph:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, self.st[style])

    def grid(self, rows: list[list[str]], widths: list[float]) -> Table:
        table = Table(
            [[self.p(c) for c in r] for r in rows], colWidths=widths, hAlign="CENTER"
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                    ("BACKGROUND", (0, 0), (-1, 0), GREY),
                ]
            )
        )
        return table

    def rider(self, bib: str) -> dict[str, str]:
        return self.data["riders"][bib]

    def heading(self, group: str) -> list[str]:
        return [
            "",
            "",
            self.event.get("group_titles", {}).get(group, group),
            "",
            "",
            "",
        ]

    def final_table(self, group: str) -> Table:
        rows = [self.heading(group)]
        for row in group_standings(group, self.data):
            r = self.rider(row["bib"])
            name, team = fix(r["name"], self.event), fix(r["team"], self.event)
            coach = fix(r["coach"], self.event)
            rows.append([row["place"], r["bib"], name, r["birth"], team, coach])
        return self.grid(rows, FINAL_COLS)

    def qualification_table(self, group: str) -> Table:
        rows = [self.heading(group)]
        for bib in self.data["qualification"][group]:
            r = self.rider(bib)
            place = str(r["qual_place"]) if r["qual_place"] else r["qual_status"]
            name, coach = fix(r["name"], self.event), fix(r["coach"], self.event)
            rows.append([place, bib, name, r["birth"], r.get("time", ""), coach])
        return self.grid(rows, QUAL_COLS)

    def signatures(self) -> Table:
        labels = self.event["labels"]
        table = Table(
            [
                [
                    self.p(labels["judge"], "sign"),
                    self.p(self.event["judge"], "sign_r"),
                ],
                [
                    self.p(labels["secretary"], "sign"),
                    self.p(self.event["secretary"], "sign_r"),
                ],
            ],
            colWidths=[8.0 * cm, 7.0 * cm],
            hAlign="CENTER",
        )
        table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 1), (-1, 1), 22),
                ]
            )
        )
        return table

    def header(self, title: str) -> list:
        story: list = [self.p(line, "letter") for line in self.event["letterhead"]]
        story += [Spacer(1, 0.55 * cm), self.p(title, "title"), Spacer(1, 0.45 * cm)]
        dateline = Table(
            [[self.p(self.event["date"], "date"), self.p(self.event["city"], "city")]],
            colWidths=[8.0 * cm, 7.6 * cm],
            hAlign="CENTER",
        )
        dateline.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [*story, dateline, Spacer(1, 0.4 * cm)]

    def build(self, part: dict[str, Any], out: Path) -> None:
        groups = part["groups"]
        story = self.header(part["title"])
        finals = [self.final_table(g) for g in groups]
        for table in finals[:-1]:
            story += [KeepTogether([table]), Spacer(1, 0.75 * cm)]
        # The signatures stay under the last table, never alone on a page.
        story += [KeepTogether([finals[-1], Spacer(1, 0.95 * cm), self.signatures()])]
        story += [
            PageBreak(),
            self.p(self.event["labels"]["qualification"], "title"),
            Spacer(1, 0.45 * cm),
        ]
        quals = [self.qualification_table(g) for g in groups]
        # Stacked with no gap, the group tables read as the template's one table while
        # no group is split across two pages.
        story += [KeepTogether([table]) for table in quals[:-1]]
        story += [KeepTogether([quals[-1], Spacer(1, 1.2 * cm), self.signatures()])]
        doc = SimpleDocTemplate(
            str(out),
            pagesize=A4,
            leftMargin=2.3 * cm,
            rightMargin=2.0 * cm,
            topMargin=1.8 * cm,
            bottomMargin=1.6 * cm,
            title=out.stem,
            author="",
        )
        doc.build(story)


def main(data_path: str, event_path: str, out_dir: str) -> None:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    register_fonts()
    protocol = Protocol(data, event)
    for part in event["parts"]:
        if not part["groups"]:
            sys.exit(f"{part['file']}: a part needs at least one group")
        unknown = [g for g in part["groups"] if g not in data["qualification"]]
        if unknown:
            sys.exit(f"{part['file']}: no such group in the race data: {unknown}")
        out = Path(out_dir) / part["file"]
        protocol.build(part, out)
        print(f"written: {out}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
