from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


QUESTIONS = [
    "Quais contribuições para a cadeia produtiva do cacau são descritas nos trabalhos?",
    "Quais aplicações de inteligência artificial aparecem nos Anais?",
    "Que problemas ambientais do sul da Bahia são investigados?",
    "Quais temas de saúde pública aparecem nos trabalhos?",
    "Como a agricultura familiar é abordada nas pesquisas?",
    "Quais estudos tratam da biodiversidade regional?",
    "Que metodologias de ensino são relatadas nos trabalhos de educação?",
    "Quais soluções de inovação tecnológica foram desenvolvidas na UESC?",
    "Como questões de gênero, raça e inclusão social aparecem nas pesquisas?",
    "Quais relações interdisciplinares podem ser identificadas entre trabalhos de áreas diferentes?",
]


def normalize_text(value: str) -> str:
    return (
        value.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )


def markdown_to_reportlab(value: str) -> str:
    value = normalize_text(value)
    lines: list[str] = []
    for raw_line in value.splitlines():
        escaped = html.escape(raw_line.strip())
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
        if escaped.startswith("## "):
            escaped = f"<b>{escaped[3:]}</b>"
        elif escaped.startswith("# "):
            escaped = f"<b>{escaped[2:]}</b>"
        lines.append(escaped)
    return "<br/>".join(lines)


def split_answer(value: str, maximum_chars: int = 1350) -> list[str]:
    value = normalize_text(value).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", value) if part.strip()]
    blocks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            blocks.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        if len(paragraph) > maximum_chars:
            flush()
            words = paragraph.split()
            chunk = ""
            for word in words:
                candidate = f"{chunk} {word}".strip()
                if len(candidate) > maximum_chars and chunk:
                    blocks.append(chunk)
                    chunk = word
                else:
                    chunk = candidate
            if chunk:
                blocks.append(chunk)
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) > maximum_chars and current:
            flush()
            current = paragraph
        else:
            current = candidate
    flush()
    return blocks or [value]


def post_answer(base_url: str, question: str, top_k: int) -> dict:
    payload = json.dumps({"query": question, "top_k": top_k}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/answer",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


def run_questions(base_url: str, top_k: int, log_path: Path) -> list[dict]:
    results: list[dict] = []
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"INICIO={datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()}\n")
        log.write(f"BASE_URL={base_url}\nTOP_K={top_k}\nTOTAL={len(QUESTIONS)}\n")
        log.flush()
        for number, question in enumerate(QUESTIONS, start=1):
            started = time.perf_counter()
            log.write(f"PERGUNTA_{number:02d}_INICIO={question}\n")
            log.flush()
            last_error: Exception | None = None
            response: dict | None = None
            for attempt in range(1, 3):
                try:
                    response = post_answer(base_url, question, top_k)
                    break
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                    last_error = exc
                    log.write(f"PERGUNTA_{number:02d}_TENTATIVA_{attempt}_ERRO={exc}\n")
                    log.flush()
                    if attempt < 2:
                        time.sleep(3)
            if response is None:
                raise RuntimeError(f"Falha na pergunta {number}: {last_error}")
            elapsed = time.perf_counter() - started
            results.append(response)
            answer = response["answer"]
            log.write(
                f"PERGUNTA_{number:02d}_CONCLUIDA="
                f"run_id={response['run_id']} answer_id={answer['answer_id']} "
                f"fontes={len(answer['sources'])} segundos={elapsed:.3f}\n"
            )
            log.flush()
        log.write(f"FIM={datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()}\n")
    return results


def draw_page(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#B7C5D6"))
    canvas.setLineWidth(0.4)
    canvas.line(12 * mm, 10 * mm, landscape(A4)[0] - 12 * mm, 10 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#4B5563"))
    canvas.drawString(12 * mm, 6.5 * mm, "Avaliação do RAG - Versão 1")
    canvas.drawRightString(landscape(A4)[0] - 12 * mm, 6.5 * mm, f"Página {document.page}")
    canvas.restoreState()


def build_pdf(results: list[dict], output_path: Path, generated_at: datetime) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleV1",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=colors.HexColor("#17324D"),
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleV1",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#374151"),
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#17324D"),
    )
    meta_value = ParagraphStyle(
        "MetaValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#111827"),
    )
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.6,
        leading=9,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    question_style = ParagraphStyle(
        "Question",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.4,
        leading=9.2,
        textColor=colors.HexColor("#172033"),
        alignment=TA_LEFT,
    )
    answer_style = ParagraphStyle(
        "Answer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.1,
        textColor=colors.HexColor("#111827"),
        alignment=TA_LEFT,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#374151"),
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title="Avaliação do RAG - Versão 1 - Dez perguntas",
        author="Projeto RAG dos Anais SIC/UESC",
        subject="Respostas integrais da linha de base rag-baseline-v1.4",
    )

    first = results[0]
    first_answer = first["answer"]
    story = [
        Paragraph("Avaliação do RAG - Versão 1", title_style),
        Paragraph(
            "Dez perguntas temáticas executadas sobre o corpus integral dos Anais da SIC/UESC. "
            "As respostas abaixo foram preservadas sem correção manual.",
            subtitle_style,
        ),
    ]

    metadata = [
        [Paragraph("Data da execução", meta_label), Paragraph(generated_at.strftime("%d/%m/%Y %H:%M:%S"), meta_value)],
        [Paragraph("Pipeline", meta_label), Paragraph(html.escape(first_answer["prompt_version"]), meta_value)],
        [Paragraph("Recuperação", meta_label), Paragraph(f"BAAI/bge-m3 - busca exata por cosseno - top_k={first['top_k']}", meta_value)],
        [Paragraph("Geração", meta_label), Paragraph(f"{first_answer['provider']} - {first_answer['model']} - temperatura {first_answer['temperature']} - semente {first_answer['seed']}", meta_value)],
        [Paragraph("Corpus", meta_label), Paragraph("3.969 PDFs - 3.970 páginas - 7.276 fragmentos e embeddings", meta_value)],
    ]
    meta_table = Table(metadata, colWidths=[42 * mm, 220 * mm], hAlign="CENTER")
    meta_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C5D6")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 5 * mm)])

    rows = [
        [
            Paragraph("Nº", header_style),
            Paragraph("Pergunta", header_style),
            Paragraph("Resposta integral da Versão 1", header_style),
        ]
    ]
    question_row_ranges: list[tuple[int, int, int]] = []
    for number, (question, response) in enumerate(zip(QUESTIONS, results), start=1):
        answer_text = response["answer"]["text"]
        blocks = split_answer(answer_text)
        start_row = len(rows)
        for block_index, block in enumerate(blocks):
            rows.append(
                [
                    Paragraph(str(number) if block_index == 0 else "", question_style),
                    Paragraph(html.escape(question) if block_index == 0 else "", question_style),
                    Paragraph(markdown_to_reportlab(block), answer_style),
                ]
            )
        question_row_ranges.append((start_row, len(rows) - 1, number))

    response_table = LongTable(
        rows,
        colWidths=[10 * mm, 65 * mm, 198 * mm],
        repeatRows=1,
        splitByRow=1,
        hAlign="CENTER",
    )
    table_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#98A8BA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for start, end, number in question_row_ranges:
        background = colors.HexColor("#F4F7FA") if number % 2 else colors.white
        table_commands.append(("BACKGROUND", (0, start), (-1, end), background))
        if end > start:
            table_commands.append(("LINEABOVE", (2, start + 1), (2, end), 0.2, colors.HexColor("#D6DEE8")))
    response_table.setStyle(TableStyle(table_commands))
    story.append(response_table)

    story.extend(
        [
            PageBreak(),
            Paragraph("Dados técnicos das execuções", title_style),
            Paragraph(
                "Os identificadores e tempos permitem localizar cada execução no banco e reproduzir a análise posterior.",
                subtitle_style,
            ),
        ]
    )
    metric_rows = [
        [
            Paragraph("Nº", header_style),
            Paragraph("run_id", header_style),
            Paragraph("answer_id", header_style),
            Paragraph("Emb. (ms)", header_style),
            Paragraph("Recup. (ms)", header_style),
            Paragraph("Geração (ms)", header_style),
            Paragraph("Tokens de entrada", header_style),
            Paragraph("Tokens gerados", header_style),
            Paragraph("Fontes", header_style),
        ]
    ]
    for number, response in enumerate(results, start=1):
        answer = response["answer"]
        values = [
            number,
            response["run_id"],
            answer["answer_id"],
            f"{response['embedding_duration_ms']:.2f}",
            f"{response['retrieval_duration_ms']:.2f}",
            f"{answer['generation_duration_ms']:.2f}",
            answer.get("prompt_eval_count") or "-",
            answer.get("eval_count") or "-",
            len(answer["sources"]),
        ]
        metric_rows.append([Paragraph(html.escape(str(value)), meta_value) for value in values])
    metrics = Table(metric_rows, colWidths=[12 * mm, 24 * mm, 24 * mm, 28 * mm, 30 * mm, 34 * mm, 38 * mm, 35 * mm, 22 * mm], repeatRows=1)
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#98A8BA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            metrics,
            Spacer(1, 5 * mm),
            Paragraph(
                "Nota metodológica: este documento registra a saída original da linha de base. "
                "A presença de uma resposta no relatório não implica que ela tenha sido considerada correta. "
                "A relevância das fontes, a fidelidade das afirmações, a completude e a correção das citações "
                "serão avaliadas separadamente por julgamento humano.",
                note_style,
            ),
        ]
    )

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa as dez perguntas e gera o relatório da Versão 1.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_pdf = root / "output" / "pdf" / "avaliacao_rag_versao_1_10_perguntas.pdf"
    output_json = root / "artifacts" / "avaliacao_rag_versao_1_10_perguntas.json"
    log_path = root / "logs" / "avaliacao_rag_versao_1_10_perguntas.log"
    generated_at = datetime.now(ZoneInfo("America/Sao_Paulo"))

    results = run_questions(args.base_url, args.top_k, log_path)
    record = {
        "version": "1",
        "generated_at": generated_at.isoformat(),
        "base_url": args.base_url,
        "top_k": args.top_k,
        "questions": QUESTIONS,
        "responses": results,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    build_pdf(results, output_pdf, generated_at)
    print(json.dumps({"pdf": str(output_pdf), "json": str(output_json), "log": str(log_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
