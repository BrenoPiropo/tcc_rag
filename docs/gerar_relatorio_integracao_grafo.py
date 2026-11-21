from __future__ import annotations

import html
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "artifacts" / "knowledge_graph" / "query_integration_validation.json"
DER_IMAGE = ROOT / "artifacts" / "knowledge_graph" / "knowledge_graph_der.png"
OUTPUT = ROOT / "output" / "pdf" / "relatorio_integracao_grafo_rag.pdf"

NAVY = colors.HexColor("#173B57")
TEAL = colors.HexColor("#16837B")
INK = colors.HexColor("#20252B")
MUTED = colors.HexColor("#59636E")
LIGHT = colors.HexColor("#EEF4F3")
LINE = colors.HexColor("#C9D3D6")


def register_fonts() -> None:
    fonts = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("TimesNewRoman", fonts / "times.ttf"))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", fonts / "timesbd.ttf"))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", fonts / "timesi.ttf"))
    pdfmetrics.registerFont(TTFont("Consolas", fonts / "consola.ttf"))
    pdfmetrics.registerFontFamily(
        "TimesNewRoman",
        normal="TimesNewRoman",
        bold="TimesNewRoman-Bold",
        italic="TimesNewRoman-Italic",
    )


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=11.5,
            leading=17.2,
            alignment=TA_JUSTIFY,
            firstLineIndent=1.25 * cm,
            spaceAfter=7,
            textColor=INK,
        ),
        "body_no_indent": ParagraphStyle(
            "BodyNoIndent",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=11.5,
            leading=17.2,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
            textColor=INK,
        ),
        "abstract": ParagraphStyle(
            "Abstract",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=10.5,
            leading=15.5,
            alignment=TA_JUSTIFY,
            spaceAfter=7,
            textColor=INK,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="TimesNewRoman-Bold",
            fontSize=15,
            leading=19,
            textColor=NAVY,
            spaceBefore=15,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="TimesNewRoman-Bold",
            fontSize=12.5,
            leading=16,
            textColor=TEAL,
            spaceBefore=11,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=11,
            leading=16,
            leftIndent=0.65 * cm,
            firstLineIndent=-0.35 * cm,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=9.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=MUTED,
            spaceBefore=5,
            spaceAfter=8,
        ),
        "table": ParagraphStyle(
            "TableText",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=9.2,
            leading=12.3,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName="TimesNewRoman-Bold",
            fontSize=9.2,
            leading=12,
            textColor=colors.white,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName="Consolas",
            fontSize=7.8,
            leading=10.5,
            leftIndent=0.25 * cm,
            rightIndent=0.25 * cm,
            borderColor=LINE,
            borderWidth=0.5,
            borderPadding=7,
            backColor=colors.HexColor("#F4F6F7"),
            spaceBefore=5,
            spaceAfter=8,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="TimesNewRoman",
            fontSize=10.5,
            leading=15.5,
            leftIndent=0.35 * cm,
            rightIndent=0.35 * cm,
            borderColor=TEAL,
            borderWidth=0,
            borderLeftWidth=3,
            borderPadding=8,
            backColor=LIGHT,
            spaceBefore=6,
            spaceAfter=9,
        ),
    }


def markup(text: str) -> str:
    return text


def code_path(value: str) -> str:
    escaped = html.escape(value)
    for separator in ("/", "_", "\\"):
        escaped = escaped.replace(separator, separator + "&#8203;")
    return f'<font name="Consolas" size="8.6">{escaped}</font>'


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("TimesNewRoman", 8.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(3 * cm, A4[1] - 1.25 * cm, "Integração do grafo ao RAG - Anais da SIC/UESC")
        canvas.drawRightString(A4[0] - 2 * cm, 1.15 * cm, str(doc.page))
        canvas.setStrokeColor(LINE)
        canvas.line(3 * cm, A4[1] - 1.42 * cm, A4[0] - 2 * cm, A4[1] - 1.42 * cm)
    canvas.restoreState()


def add_cover(story) -> None:
    story.append(Spacer(1, 4.1 * cm))
    story.append(
        Paragraph(
            "UNIVERSIDADE ESTADUAL DE SANTA CRUZ - UESC",
            ParagraphStyle(
                "Institution",
                fontName="TimesNewRoman-Bold",
                fontSize=13,
                leading=18,
                alignment=TA_CENTER,
                textColor=NAVY,
            ),
        )
    )
    story.append(Spacer(1, 2.5 * cm))
    story.append(
        Paragraph(
            "IMPLEMENTAÇÃO DA CAMADA DE CONSULTAS EM GRAFO E SUA INTEGRAÇÃO AO RAG",
            ParagraphStyle(
                "CoverTitle",
                fontName="TimesNewRoman-Bold",
                fontSize=17,
                leading=24,
                alignment=TA_CENTER,
                textColor=INK,
            ),
        )
    )
    story.append(Spacer(1, 1.4 * cm))
    story.append(
        Paragraph(
            "Relatório técnico-científico para incorporação posterior ao Trabalho de Conclusão de Curso",
            ParagraphStyle(
                "Subtitle",
                fontName="TimesNewRoman-Italic",
                fontSize=12,
                leading=18,
                alignment=TA_CENTER,
            ),
        )
    )
    story.append(Spacer(1, 3.5 * cm))
    story.append(
        Paragraph(
            "Versões: query-router-v1.2 e knowledge-graph-query-v1.2<br/>"
            "Estado: implementação validada em ambiente local",
            ParagraphStyle(
                "Version",
                fontName="TimesNewRoman",
                fontSize=11,
                leading=17,
                alignment=TA_CENTER,
            ),
        )
    )
    story.append(Spacer(1, 2.3 * cm))
    story.append(
        Paragraph(
            "Ilhéus - BA<br/>21 de novembro de 2026",
            ParagraphStyle(
                "Place",
                fontName="TimesNewRoman",
                fontSize=12,
                leading=18,
                alignment=TA_CENTER,
            ),
        )
    )
    story.append(PageBreak())


def add_paragraph(story, styles, text: str, style: str = "body") -> None:
    story.append(Paragraph(markup(text), styles[style]))


def add_bullet(story, styles, text: str) -> None:
    story.append(Paragraph("• " + markup(text), styles["bullet"]))


def make_table(rows, widths, styles, repeat_rows=1) -> LongTable:
    converted = []
    for row_index, row in enumerate(rows):
        style = styles["table_head"] if row_index == 0 else styles["table"]
        converted.append([Paragraph(str(cell), style) for cell in row])
    table = LongTable(converted, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F8F8")]),
            ]
        )
    )
    return table


def architecture_flow(styles) -> Table:
    labels = [
        ("PERGUNTA", "Texto recebido pela API"),
        ("CLASSIFICADOR", "Regras determinísticas versionadas"),
        ("SEMÂNTICA", "BGE-M3 + pgvector + Llama 3"),
        ("ESTRUTURAL", "SQL sobre nós e relações"),
        ("HÍBRIDA", "Filtro do grafo + recuperação vetorial"),
    ]
    cells = []
    for title, subtitle in labels:
        cells.append(
            Paragraph(
                f'<b>{title}</b><br/><font size="8">{subtitle}</font>',
                ParagraphStyle(
                    f"Flow{title}",
                    parent=styles["table"],
                    alignment=TA_CENTER,
                    textColor=colors.white,
                    leading=11,
                ),
            )
        )
    table = Table([cells], colWidths=[3.2 * cm] * 5, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), NAVY),
                ("BACKGROUND", (2, 0), (4, 0), TEAL),
                ("GRID", (0, 0), (-1, -1), 0.8, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def build_story(data: dict, styles: dict[str, ParagraphStyle]):
    story = []
    add_cover(story)

    story.append(Paragraph("Resumo", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "Este relatório registra a implementação da camada de consultas estruturais e sua integração "
        "ao sistema RAG construído sobre os Anais da Semana de Iniciação Científica da UESC. O objetivo "
        "foi separar perguntas que dependem do conteúdo textual dos trabalhos daquelas que exigem "
        "contagens, rankings ou travessias de relações explícitas. A solução utiliza um roteador "
        "determinístico, consultas SQL sobre a projeção do grafo de conhecimento e um fluxo híbrido "
        "que restringe a busca vetorial a subconjuntos definidos pelo grafo.",
        "abstract",
    )
    add_paragraph(
        story,
        styles,
        "A implementação preserva a proveniência documental, registra cada decisão de roteamento no "
        "PostgreSQL e apresenta na interface o método utilizado. A validação confirmou 3.969 documentos, "
        "7.628 entidades, 15.717 relações e ausência de arestas órfãs. Após a inclusão da consulta "
        "agregada por edição e das consultas por autor, orientador e curso, vinte testes unitários estão aprovados. "
        "A consulta de referência identificou Wolney Gomes Almeida com 47 trabalhos; a "
        "pergunta híbrida sobre cacau na edição 3 restringiu a recuperação a 733 documentos antes da "
        "busca semântica.",
        "abstract",
    )
    add_paragraph(
        story,
        styles,
        "<b>Palavras-chave:</b> Retrieval-Augmented Generation; grafo de conhecimento; roteamento de "
        "consultas; recuperação semântica; proveniência; PostgreSQL.",
        "abstract",
    )

    story.append(Paragraph("1 Objetivo e delimitação", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "A recuperação vetorial é adequada para perguntas como “quais aplicações de inteligência "
        "artificial aparecem nos Anais?”, pois a resposta depende da similaridade entre a pergunta e "
        "passagens textuais. Entretanto, ela não garante a inspeção de todo o corpus e, por isso, não "
        "deve ser usada isoladamente para responder “qual orientador possui mais trabalhos?”. A segunda "
        "pergunta exige uma agregação completa sobre relações explícitas. A camada implementada atende "
        "essa diferença metodológica sem substituir o RAG existente.",
    )
    story.append(
        Paragraph(
            "Decisão central: valores quantitativos e rankings são produzidos pelo banco de dados; a "
            "LLM não calcula nem estima essas respostas. Ela permanece responsável apenas pela síntese "
            "textual quando há evidências recuperadas.",
            styles["callout"],
        )
    )
    add_bullet(story, styles, "Rota semântica: recuperação BGE-M3/pgvector seguida de geração local pelo Llama 3.")
    add_bullet(story, styles, "Rota estrutural: consulta SQL determinística sobre entidades e relações.")
    add_bullet(story, styles, "Rota híbrida: o grafo define o conjunto elegível e o recuperador ordena evidências dentro dele.")

    story.append(Paragraph("2 Arquitetura implementada", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "A pergunta é normalizada e classificada antes de qualquer chamada ao modelo de embeddings ou "
        "à LLM. O classificador retorna a rota, a intenção, os parâmetros extraídos e uma justificativa. "
        "Esse plano é armazenado e passa a controlar o restante da execução.",
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(architecture_flow(styles))
    story.append(Paragraph("Figura 1 - Fluxo lógico do roteamento implementado.", styles["caption"]))

    if DER_IMAGE.exists():
        story.append(Spacer(1, 0.15 * cm))
        image = Image(str(DER_IMAGE), width=16 * cm, height=10.67 * cm)
        story.append(image)
        story.append(
            Paragraph(
                "Figura 2 - DER da projeção do grafo: entidades, relações e proveniência documental. "
                "Fonte: elaboração própria (2026).",
                styles["caption"],
            )
        )

    story.append(PageBreak())
    story.append(Paragraph("3 Etapa 1 - Classificação determinística", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "O módulo de roteamento foi implementado em " + code_path("src/rag_anais/graph_queries.py") + ". "
        "A normalização converte a pergunta para caixa uniforme, remove acentos para comparação e reduz "
        "espaços. Em seguida, expressões explícitas reconhecem contagens, rankings, edições, cursos e "
        "orientadores e autores. A regra é versionada como <font name=\"Consolas\">query-router-v1.2</font>.",
    )
    routing_rows = [["Pergunta de validação", "Rota", "Intenção"]]
    for case in data["classification_cases"]:
        routing_rows.append([html.escape(case["question"]), case["route"], case["intent"]])
    story.append(make_table(routing_rows, [8.5 * cm, 2.6 * cm, 5.0 * cm], styles))
    story.append(Paragraph("Tabela 1 - Casos controlados utilizados para validar o roteador.", styles["caption"]))
    add_paragraph(
        story,
        styles,
        "O roteador não emprega uma LLM para decidir o caminho da pergunta. Isso reduz variabilidade, "
        "permite reproduzir a decisão e torna cada erro de classificação diretamente auditável. Como "
        "contrapartida, a versão inicial reconhece somente padrões previamente definidos; sua cobertura "
        "deverá ser avaliada com um conjunto maior de perguntas naturais.",
    )

    story.append(Paragraph("4 Etapa 2 - Consultas estruturais", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "As consultas estruturais usam parâmetros preparados e relacionam cada resultado ao documento "
        "que originou a aresta. As contagens utilizam documentos distintos para impedir que múltiplas "
        "linhas de uma mesma evidência aumentem artificialmente o valor.",
    )
    query_rows = [
        ["Identificador", "Finalidade", "Estrutura principal"],
        ["graph.top_advisors.v1", "Ranking de orientadores", "ADVISED_BY + COUNT(DISTINCT documento)"],
        ["graph.works_by_advisor.v1", "Trabalhos de um orientador", "Nome canônico + ADVISED_BY"],
        ["graph.works_by_author.v1", "Trabalhos de um autor principal", "Nome canônico + AUTHORED_BY"],
        ["graph.works_by_edition.v1", "Contagem por edição", "PRESENTED_IN"],
        ["graph.works_per_edition.v1", "Distribuição entre edições", "PRESENTED_IN + agrupamento"],
        ["graph.top_courses.v1", "Ranking de cursos", "ASSOCIATED_WITH_COURSE"],
        ["graph.works_by_course.v1", "Contagem de um curso", "Curso canônico + relação"],
        ["graph.corpus_summary.v1", "Resumo global", "Contagens integrais do banco"],
    ]
    story.append(make_table(query_rows, [4.2 * cm, 5.1 * cm, 6.8 * cm], styles))
    story.append(Paragraph("Tabela 2 - Catálogo inicial de consultas estruturais.", styles["caption"]))
    story.append(Paragraph("Consulta de referência para o ranking de orientadores", styles["h2"]))
    story.append(
        Preformatted(
            """SELECT advisor_entity_id, advisor_name, work_count
FROM knowledge_graph_advisor_work_counts
ORDER BY work_count DESC, advisor_name
LIMIT 10;""",
            styles["code"],
        )
    )
    add_paragraph(
        story,
        styles,
        "A resposta exibe até dez documentos de evidência do primeiro resultado. Esses documentos não "
        "representam a totalidade usada na contagem; funcionam como amostra verificável. O valor 47 foi "
        "calculado sobre todos os documentos distintos ligados ao orientador pela relação "
        "<font name=\"Consolas\">ADVISED_BY</font>.",
    )

    story.append(Paragraph("5 Etapa 3 - Persistência e auditoria", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "Foi criada a tabela " + code_path("query_route_runs") + " por meio do arquivo "
        + code_path("sql/016_query_routing_schema.sql") + ". Cada pergunta recebe um identificador de "
        "auditoria antes da execução. Ao final, são registrados a rota, a intenção, a versão do roteador, "
        "os parâmetros extraídos, o identificador da consulta, o SQL estrutural quando aplicável, a "
        "quantidade de resultados, a duração, o vínculo com a execução vetorial e o estado final.",
    )
    audit_rows = [
        ["Campo", "Função científica"],
        ["route / intent", "Reconstruir por que um mecanismo foi escolhido."],
        ["routing_version", "Distinguir mudanças nas regras de classificação."],
        ["parameters", "Preservar edição, nome ou curso extraído da pergunta."],
        ["query_identifier / executed_sql", "Identificar exatamente a consulta estrutural usada."],
        ["retrieval_run_id", "Vincular o roteamento à busca vetorial existente."],
        ["duration_ms / result_count", "Medir custo e volume do processamento."],
        ["status / error_text", "Diferenciar conclusão e falha reproduzível."],
    ]
    story.append(make_table(audit_rows, [5.2 * cm, 10.9 * cm], styles))
    story.append(Paragraph("Tabela 3 - Campos de auditoria e finalidade.", styles["caption"]))

    story.append(PageBreak())
    story.append(Paragraph("6 Etapa 4 - Integração à API e à interface", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "O endpoint " + code_path("POST /api/answer") + " passou a classificar a pergunta antes da "
        "recuperação. Na rota estrutural, nenhuma codificação vetorial e nenhuma chamada ao Ollama são "
        "realizadas. Na rota semântica, o comportamento da linha de base foi preservado. Na rota híbrida, "
        "o grafo primeiro resolve o conjunto de documentos e esse conjunto é aplicado como restrição à "
        "consulta do pgvector.",
    )
    add_paragraph(
        story,
        styles,
        "A página passou a apresentar a quantidade de nós e relações, o tipo da resposta, o método "
        "utilizado, os PDFs de evidência e uma área expansível denominada “Como esta pergunta foi "
        "processada”. Nessa área são exibidos o motivo do roteamento, o identificador da consulta, o "
        "número do registro de auditoria e, nas consultas estruturais, o SQL executado.",
    )
    integration_rows = [
        ["Arquivo", "Alteração realizada"],
        [code_path("src/rag_anais/graph_queries.py"), "Classificação, consultas e resolução do escopo híbrido."],
        [code_path("src/rag_anais/web_app.py"), "Roteamento, auditoria, resposta estrutural e filtro vetorial."],
        [code_path("web/static/index.html"), "Indicadores do grafo e painel de explicação."],
        [code_path("web/static/app.js"), "Renderização específica de cada rota."],
        [code_path("web/static/styles.css"), "Layout dos indicadores e detalhes da consulta."],
        [code_path("sql/016_query_routing_schema.sql"), "Persistência dos experimentos de roteamento."],
        [code_path("tests/test_graph_queries.py"), "Casos unitários de decisão e extração de parâmetros."],
        [code_path("scripts/validate_graph_query_integration.py"), "Validação integral e artefato JSON."],
    ]
    story.append(make_table(integration_rows, [6.1 * cm, 10.0 * cm], styles))
    story.append(Paragraph("Tabela 4 - Arquivos envolvidos na integração.", styles["caption"]))

    story.append(Paragraph("7 Etapa 5 - Validação", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "A validação combinou testes unitários, consultas diretas ao banco, execução pela API e inspeção "
        "visual da interface. Os testes unitários cobrem extração dos metadados do grafo, normalização, "
        "identificadores determinísticos, classificação das três rotas, preservação de preposições em "
        "nomes, cursos, edições e estatísticas globais.",
    )
    results = data["structural_results"]
    validation_rows = [
        ["Verificação", "Resultado"],
        ["Testes unitários", "20 aprovados; nenhuma falha."],
        ["Documentos", f"{data['counts']['documents']:,}".replace(",", ".")],
        ["Nós do grafo", f"{data['counts']['entities']:,}".replace(",", ".")],
        ["Relações", f"{data['counts']['relations']:,}".replace(",", ".")],
        ["Maior quantidade por orientador", "Wolney Gomes Almeida - 47 trabalhos."],
        ["Trabalhos de Breno Gonçalves Piropo", "2 trabalhos, nas edições 4 e 5."],
        ["Edição 2", "973 trabalhos."],
        ["Distribuição das edições 1 a 5", "680; 973; 733; 754; 829 trabalhos."],
        ["Ciência da Computação", f"{results['works_by_course']['rows'][0]['work_count']} trabalhos."],
        ["Escopo híbrido da edição 3", f"{results['semantic_by_edition']['scope_documents']} documentos."],
        ["Teste híbrido completo", "3 resultados recuperados; resposta gerada pelo Llama 3; 39,45 s."],
        ["Integridade", "Zero arestas órfãs; um trabalho por documento."],
    ]
    story.append(make_table(validation_rows, [7.4 * cm, 8.7 * cm], styles))
    story.append(Paragraph("Tabela 5 - Evidências da validação realizada em 21/11/2026.", styles["caption"]))
    add_paragraph(
        story,
        styles,
        "O tempo de 39,45 s observado no teste híbrido inclui carregamento/uso do modelo de embeddings, "
        "recuperação e geração local. Ele não deve ser interpretado como uma comparação definitiva de "
        "desempenho. A consulta estrutural isolada foi concluída em aproximadamente 20 ms nas execuções "
        "pela interface, evidenciando a diferença entre uma agregação SQL e a geração por LLM.",
    )

    story.append(Paragraph("8 Procedimento de reprodução", styles["h1"]))
    add_paragraph(story, styles, "A reprodução deve respeitar a seguinte ordem:", "body_no_indent")
    reproduction = [
        "Iniciar o PostgreSQL/pgvector com <font name=\"Consolas\">docker compose up -d postgres</font>.",
        "Aplicar o esquema do grafo e confirmar a carga das 7.628 entidades e 15.717 relações.",
        "Executar <font name=\"Consolas\">scripts/apply_query_routing_schema.py</font> para criar a auditoria.",
        "Executar os testes com <font name=\"Consolas\">python -m unittest tests.test_graph_metadata tests.test_graph_queries -v</font>.",
        "Iniciar a interface com <font name=\"Consolas\">scripts/start_web.ps1</font>.",
        "Executar <font name=\"Consolas\">scripts/validate_graph_query_integration.py</font>.",
        "Conferir o JSON em <font name=\"Consolas\">artifacts/knowledge_graph/query_integration_validation.json</font> e o log correspondente.",
    ]
    for index, item in enumerate(reproduction, start=1):
        add_bullet(story, styles, f"{index}. {item}")
    story.append(
        Paragraph(
            "Para preservar a comparabilidade, devem ser mantidas as versões query-router-v1.2, "
            "knowledge-graph-query-v1.2, BGE-M3 na revisão registrada e o mesmo congelamento dos 3.969 PDFs.",
            styles["callout"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("9 Limitações e riscos de validade", styles["h1"]))
    add_bullet(story, styles, "O roteador inicial é baseado em regras e ainda não foi avaliado com um conjunto amplo de paráfrases.")
    add_bullet(story, styles, "Pessoas são consolidadas pelo nome normalizado; homônimos podem ser reunidos incorretamente.")
    add_bullet(story, styles, "Variações muito diferentes de um mesmo nome podem permanecer como entidades separadas.")
    add_bullet(story, styles, "Os dez PDFs mostrados numa resposta estrutural são exemplos; a contagem usa todo o conjunto relacionado.")
    add_bullet(story, styles, "O filtro híbrido garante o recorte relacional, mas a relevância final ainda depende do recuperador e da LLM.")
    add_bullet(story, styles, "Rankings devem ser apresentados como resultados do corpus atual, não como características permanentes da instituição.")

    story.append(Paragraph("10 Próxima avaliação recomendada", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "A implementação está funcional, mas ainda requer avaliação humana específica. Recomenda-se um "
        "conjunto balanceado com perguntas semânticas, estruturais e híbridas. Para o roteador, devem ser "
        "medidas acurácia da rota e acurácia da intenção. Para consultas estruturais, deve-se conferir a "
        "correção do valor e da proveniência. Para perguntas híbridas, devem ser preservadas as métricas "
        "de recuperação e os critérios de fidelidade já adotados no RAG.",
    )
    proposed_questions = [
        "Qual orientador possui mais trabalhos?",
        "Quantos trabalhos existem em cada edição?",
        "Quais cursos apresentam mais trabalhos?",
        "Quantos trabalhos estão vinculados ao curso de Ciência da Computação?",
        "Quais trabalhos foram orientados por Wolney Gomes Almeida?",
        "Quais trabalhos sobre cacau aparecem na edição 3?",
        "Quais pesquisas de saúde da edição 2 foram orientadas por determinado orientador?",
        "Quais aplicações de inteligência artificial aparecem nos Anais?",
        "Que problemas ambientais do sul da Bahia são investigados?",
        "Qual edição reúne mais trabalhos relacionados à biodiversidade?",
    ]
    for index, question in enumerate(proposed_questions, start=1):
        add_bullet(story, styles, f"{index}. {question}")

    story.append(Paragraph("11 Síntese para incorporação futura ao TCC", styles["h1"]))
    add_paragraph(
        story,
        styles,
        "Foi implementada uma camada de roteamento para distinguir perguntas semânticas, estruturais e "
        "híbridas. Perguntas sobre o conteúdo dos trabalhos permanecem no pipeline RAG composto por "
        "BGE-M3, pgvector e Llama 3. Perguntas que exigem contagens, rankings ou relações explícitas são "
        "respondidas por consultas determinísticas sobre a projeção do grafo de conhecimento. Nas "
        "perguntas híbridas, o grafo restringe o conjunto de documentos antes da ordenação vetorial. "
        "Essa separação evita atribuir à LLM operações agregadas que exigem cobertura integral do corpus.",
    )
    add_paragraph(
        story,
        styles,
        "Cada execução passou a registrar a versão do roteador, a rota selecionada, a intenção, os "
        "parâmetros extraídos, o identificador da consulta, a duração, a quantidade de resultados e o "
        "vínculo com a recuperação vetorial. A validação confirmou a consistência do grafo e demonstrou "
        "a consulta estrutural sobre orientadores, cujo maior valor no corpus atual foi de 47 trabalhos. "
        "Também foi validado um fluxo híbrido que restringiu uma pergunta temática aos 733 documentos "
        "da edição 3 antes da recuperação semântica.",
    )
    add_paragraph(
        story,
        styles,
        "Os resultados desta etapa demonstram viabilidade técnica e reprodutibilidade, mas não "
        "constituem ainda a avaliação final do sistema. A próxima etapa deve medir a acurácia do roteador, "
        "a correção das respostas estruturais e a qualidade das respostas híbridas mediante julgamento "
        "humano e perguntas previamente definidas.",
    )

    story.append(Paragraph("Apêndice A - Evidências e artefatos", styles["h1"]))
    artifacts = [
        ["Artefato", "Conteúdo"],
        [code_path("artifacts/knowledge_graph/query_integration_validation.json"), "Resultado consolidado da validação."],
        [code_path("logs/knowledge_graph_query_integration.log"), "Registro temporal da validação."],
        [code_path("artifacts/knowledge_graph/knowledge_graph_validation.json"), "Integridade e contagens do grafo."],
        [code_path("artifacts/knowledge_graph/knowledge_graph_der.png"), "DER utilizado na documentação."],
        [code_path("logs/web_interface.log"), "Buscas, respostas, tempos e avaliações da aplicação."],
    ]
    story.append(make_table(artifacts, [8.0 * cm, 8.1 * cm], styles))
    story.append(Paragraph("Tabela 6 - Artefatos de auditoria produzidos ou reutilizados.", styles["caption"]))
    return story


def main() -> None:
    register_fonts()
    data = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if data.get("status") != "valid":
        raise RuntimeError("A validação da integração não está marcada como válida")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=3 * cm,
        rightMargin=2 * cm,
        topMargin=2.8 * cm,
        bottomMargin=2 * cm,
        title="Implementação da camada de consultas em grafo e integração ao RAG",
        author="Projeto de TCC - UESC",
        subject="Relatório técnico-científico reproduzível",
    )
    document.build(
        build_story(data, make_styles()),
        onFirstPage=header_footer,
        onLaterPages=header_footer,
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
