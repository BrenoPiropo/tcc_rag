from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "MEMORIAL_CIENTIFICO.md"
OUTPUT = ROOT / "output" / "pdf" / "memorial_desenvolvimento_rag_anais_uesc.pdf"


def register_fonts() -> None:
    fonts = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("TimesNewRoman", fonts / "times.ttf"))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", fonts / "timesbd.ttf"))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", fonts / "timesi.ttf"))
    pdfmetrics.registerFontFamily(
        "TimesNewRoman",
        normal="TimesNewRoman",
        bold="TimesNewRoman-Bold",
        italic="TimesNewRoman-Italic",
    )


def inline_markup(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=12,
            leading=18,
            alignment=TA_JUSTIFY,
            firstLineIndent=1.25 * cm,
            spaceAfter=8,
            textColor=colors.HexColor("#20252B"),
        ),
        "abstract": ParagraphStyle(
            "Abstract",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=11,
            leading=16.5,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base["Heading1"],
            fontName="TimesNewRoman-Bold",
            fontSize=14,
            leading=18,
            alignment=TA_LEFT,
            spaceBefore=14,
            spaceAfter=10,
            keepWithNext=True,
            textColor=colors.HexColor("#17365D"),
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base["Heading2"],
            fontName="TimesNewRoman-Bold",
            fontSize=12,
            leading=16,
            alignment=TA_LEFT,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
            textColor=colors.HexColor("#294E73"),
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=12,
            leading=17,
            leftIndent=0.7 * cm,
            firstLineIndent=-0.35 * cm,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName="Courier",
            fontSize=9.5,
            leading=13,
            leftIndent=0.5 * cm,
            rightIndent=0.5 * cm,
            borderColor=colors.HexColor("#B8C4CE"),
            borderWidth=0.5,
            borderPadding=8,
            backColor=colors.HexColor("#F3F6F8"),
            spaceBefore=6,
            spaceAfter=10,
        ),
    }


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("TimesNewRoman", 9)
        canvas.setFillColor(colors.HexColor("#59636E"))
        canvas.drawString(3 * cm, A4[1] - 1.35 * cm, "Memorial científico - RAG dos Anais da SIC/UESC")
        canvas.drawRightString(A4[0] - 2 * cm, 1.25 * cm, str(doc.page))
        canvas.setStrokeColor(colors.HexColor("#C9D0D6"))
        canvas.line(3 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
    canvas.restoreState()


def cover(story, title: str, version: str, status: str) -> None:
    story.append(Spacer(1, 5.2 * cm))
    story.append(
        Paragraph(
            "UNIVERSIDADE ESTADUAL DE SANTA CRUZ - UESC",
            ParagraphStyle(
                "Institution",
                fontName="TimesNewRoman-Bold",
                fontSize=13,
                leading=18,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#17365D"),
            ),
        )
    )
    story.append(Spacer(1, 3.2 * cm))
    story.append(
        Paragraph(
            html.escape(title.upper()),
            ParagraphStyle(
                "CoverTitle",
                fontName="TimesNewRoman-Bold",
                fontSize=17,
                leading=24,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#162A3A"),
            ),
        )
    )
    story.append(Spacer(1, 2.4 * cm))
    story.append(
        Paragraph(
            "Documento técnico-científico evolutivo do Trabalho de Conclusão de Curso",
            ParagraphStyle(
                "Subtitle",
                fontName="TimesNewRoman-Italic",
                fontSize=12,
                leading=18,
                alignment=TA_CENTER,
            ),
        )
    )
    story.append(Spacer(1, 4.2 * cm))
    story.append(Paragraph(html.escape(version), ParagraphStyle("Version", fontName="TimesNewRoman", fontSize=11, leading=16, alignment=TA_CENTER)))
    story.append(Paragraph(html.escape(status), ParagraphStyle("Status", fontName="TimesNewRoman", fontSize=11, leading=16, alignment=TA_CENTER)))
    story.append(Spacer(1, 1.1 * cm))
    story.append(Paragraph("Ilhéus - BA<br/>2026", ParagraphStyle("Place", fontName="TimesNewRoman", fontSize=12, leading=18, alignment=TA_CENTER)))
    story.append(PageBreak())


def parse_markdown(text: str, style_map: dict[str, ParagraphStyle]):
    lines = text.splitlines()
    title = lines[0].removeprefix("# ").strip()
    version = lines[2].strip()
    status = lines[4].strip()
    story = []
    cover(story, title, version, status)

    paragraph: list[str] = []
    code: list[str] = []
    in_code = False
    in_abstract = False

    def flush_paragraph() -> None:
        if paragraph:
            content = " ".join(item.strip() for item in paragraph)
            story.append(Paragraph(inline_markup(content), style_map["abstract" if in_abstract else "body"]))
            paragraph.clear()

    for line in lines[5:]:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Preformatted("\n".join(code), style_map["code"]))
                code.clear()
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            heading = stripped[3:]
            if heading == "Referências":
                story.append(PageBreak())
            in_abstract = heading == "Resumo"
            story.append(Paragraph(html.escape(heading), style_map["h2"]))
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            in_abstract = False
            story.append(Paragraph(html.escape(stripped[4:]), style_map["h3"]))
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            story.append(Paragraph("- " + inline_markup(stripped[2:]), style_map["bullet"]))
            continue
        if re.match(r"^\d+\. ", stripped):
            flush_paragraph()
            story.append(Paragraph(inline_markup(stripped), style_map["bullet"]))
            continue
        paragraph.append(stripped)

    flush_paragraph()
    return story


def main() -> None:
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=3 * cm,
        rightMargin=2 * cm,
        topMargin=3 * cm,
        bottomMargin=2 * cm,
        title="Memorial científico do desenvolvimento do RAG dos Anais da SIC/UESC",
        author="Projeto de TCC - UESC",
        subject="Registro científico e reproduzível do desenvolvimento do RAG",
    )
    story = parse_markdown(SOURCE.read_text(encoding="utf-8"), styles())
    document.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()

