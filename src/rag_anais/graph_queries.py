from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal


ROUTING_VERSION = "query-router-v1.2"
GRAPH_QUERY_VERSION = "knowledge-graph-query-v1.2"

Route = Literal["semantic", "structural", "hybrid"]


@dataclass(frozen=True)
class QueryPlan:
    route: Route
    intent: str
    explanation: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphQueryResult:
    query_identifier: str
    sql_text: str
    rows: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    answer_text: str
    duration_ms: float


def normalize_question(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text).split())


def _edition_number(normalized: str) -> int | None:
    match = re.search(r"\bedic(?:ao|oes)\s+(?:numero\s+)?([1-5])\b", normalized)
    return int(match.group(1)) if match else None


def _name_after(normalized: str, marker: str) -> str | None:
    match = re.search(marker + r"\s+([a-z][a-z ]{2,80})", normalized)
    if not match:
        return None
    value = re.split(
        r"\b(?:que|sobre|na|no|nas|nos|em|entre|por edicao)\b",
        match.group(1),
        maxsplit=1,
    )[0]
    return " ".join(value.split()) or None


def classify_question(question: str) -> QueryPlan:
    normalized = normalize_question(question)
    edition = _edition_number(normalized)
    has_content_cue = any(
        cue in normalized
        for cue in (
            " sobre ", " tema ", " tratam ", " aborda", " investig", " aplicac",
            " contribuic", " metodologia", " problema", " resultado", " biodiversidade",
            " cacau", " saude", " ambiental", " inteligencia artificial",
        )
    )
    has_count_cue = any(
        cue in normalized
        for cue in (
            "quantos", "quantas", "quantidade", "total", "maior numero",
            "mais trabalhos", "mais pdf", "ranking", "distribuicao",
        )
    )

    advisor_name = _name_after(
        normalized,
        r"(?:(?:orientados?|orientadas?)\s+(?:por|pelo|pela)(?:\s+(?:professor|professora|orientador|orientadora))?|(?:do|da)\s+orientador(?:a)?|orientador(?:a)?)",
    )
    author_name = _name_after(
        normalized,
        r"(?:(?:apresentados?|apresentadas?|escritos?|escritas?|produzidos?|produzidas?)\s+(?:por|pelo|pela)(?:\s+(?:aluno|aluna|autor|autora|participante))?|(?:do|da)\s+autor(?:a)?(?:\s+principal)?|autor(?:a)?(?:\s+principal)?|participante\s+principal)",
    )
    course_name = _name_after(normalized, r"\bcurso(?:\s+de)?")

    if "orientador" in normalized and any(
        cue in normalized for cue in ("mais trabalhos", "mais pdf", "maior numero", "ranking")
    ):
        if has_content_cue:
            return QueryPlan(
                "hybrid",
                "semantic_with_structural_context",
                "A pergunta combina um tema textual com uma agregação por orientador.",
                {"edition": edition} if edition else {},
            )
        return QueryPlan(
            "structural",
            "top_advisors",
            "A pergunta solicita um ranking ou máximo calculado sobre relações de orientação.",
            {"limit": 10},
        )

    if advisor_name:
        if has_content_cue:
            return QueryPlan(
                "hybrid",
                "semantic_by_advisor",
                "A pergunta exige filtrar pelo orientador e depois recuperar conteúdo textual.",
                {"advisor_name": advisor_name, **({"edition": edition} if edition else {})},
            )
        return QueryPlan(
            "structural",
            "works_by_advisor",
            "A pergunta solicita trabalhos ligados explicitamente a um orientador.",
            {"advisor_name": advisor_name},
        )

    if author_name:
        if has_content_cue:
            return QueryPlan(
                "hybrid",
                "semantic_by_author",
                "A pergunta exige filtrar pelo autor principal e recuperar conteúdo textual.",
                {"author_name": author_name, **({"edition": edition} if edition else {})},
            )
        return QueryPlan(
            "structural",
            "works_by_author",
            "A pergunta solicita os trabalhos ligados explicitamente ao autor principal.",
            {"author_name": author_name},
        )

    if "curso" in normalized and any(
        cue in normalized for cue in ("mais trabalhos", "maior numero", "ranking")
    ):
        return QueryPlan(
            "structural",
            "top_courses",
            "A pergunta solicita um ranking de cursos por quantidade de trabalhos.",
            {"limit": 10},
        )

    if edition is None and has_count_cue and any(
        term in normalized for term in ("edicao", "edicoes")
    ):
        return QueryPlan(
            "structural",
            "works_per_edition",
            "A pergunta solicita uma distribuição ou comparação integral entre as edições.",
        )

    if edition is not None and has_count_cue:
        return QueryPlan(
            "structural",
            "works_by_edition",
            "A pergunta solicita uma contagem exata de trabalhos de uma edição.",
            {"edition": edition},
        )

    if edition is not None and has_content_cue:
        return QueryPlan(
            "hybrid",
            "semantic_by_edition",
            "A pergunta restringe a busca semântica a uma edição do grafo.",
            {"edition": edition},
        )

    if course_name:
        if has_content_cue:
            return QueryPlan(
                "hybrid",
                "semantic_by_course",
                "A pergunta exige filtrar pelo curso e recuperar conteúdo textual.",
                {"course_name": course_name, **({"edition": edition} if edition else {})},
            )
        return QueryPlan(
            "structural",
            "works_by_course",
            "A pergunta solicita trabalhos vinculados explicitamente a um curso.",
            {"course_name": course_name},
        )

    if has_count_cue and any(term in normalized for term in ("anais", "corpus", "base")):
        return QueryPlan(
            "structural",
            "corpus_summary",
            "A pergunta solicita estatísticas globais armazenadas no banco.",
        )

    return QueryPlan(
        "semantic",
        "semantic_content",
        "A pergunta solicita evidências presentes no conteúdo textual dos trabalhos.",
    )


TOP_ADVISORS_SQL = """SELECT advisor_entity_id AS entity_id,
       advisor_name AS label,
       work_count
FROM knowledge_graph_advisor_work_counts
ORDER BY work_count DESC, advisor_name
LIMIT %(limit)s"""

TOP_COURSES_SQL = """SELECT c.entity_id,
       c.label,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities c ON c.entity_id = r.target_entity_id
WHERE r.relation_type = 'ASSOCIATED_WITH_COURSE'
GROUP BY c.entity_id, c.label
ORDER BY work_count DESC, c.label
LIMIT %(limit)s"""

WORKS_BY_EDITION_SQL = """SELECT e.entity_id,
       e.label,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities e ON e.entity_id = r.target_entity_id
WHERE r.relation_type = 'PRESENTED_IN'
  AND e.canonical_key = %(edition)s
GROUP BY e.entity_id, e.label"""

WORKS_PER_EDITION_SQL = """SELECT e.entity_id,
       e.canonical_key AS edition,
       e.label,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities e ON e.entity_id = r.target_entity_id
WHERE r.relation_type = 'PRESENTED_IN'
GROUP BY e.entity_id, e.canonical_key, e.label
ORDER BY e.canonical_key::integer"""

WORKS_BY_ADVISOR_SQL = """SELECT p.entity_id,
       p.label,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities p ON p.entity_id = r.target_entity_id
WHERE r.relation_type = 'ADVISED_BY'
  AND p.canonical_key LIKE %(advisor_pattern)s
GROUP BY p.entity_id, p.label
ORDER BY work_count DESC, p.label"""

WORKS_BY_AUTHOR_SQL = """SELECT p.entity_id,
       p.label,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities p ON p.entity_id = r.target_entity_id
WHERE r.relation_type = 'AUTHORED_BY'
  AND p.canonical_key LIKE %(author_pattern)s
GROUP BY p.entity_id, p.label
ORDER BY work_count DESC, p.label"""

WORKS_BY_COURSE_SQL = """SELECT c.entity_id,
       c.label,
       count(DISTINCT r.source_document_sha256) AS work_count
FROM knowledge_graph_relations r
JOIN knowledge_graph_entities c ON c.entity_id = r.target_entity_id
WHERE r.relation_type = 'ASSOCIATED_WITH_COURSE'
  AND c.canonical_key LIKE %(course_pattern)s
GROUP BY c.entity_id, c.label
ORDER BY work_count DESC, c.label"""

CORPUS_SUMMARY_SQL = """SELECT
    (SELECT count(*) FROM documents) AS documents,
    (SELECT count(*) FROM knowledge_graph_entities) AS entities,
    (SELECT count(*) FROM knowledge_graph_relations) AS relations,
    (SELECT count(*) FROM knowledge_graph_entities WHERE entity_type = 'person') AS people,
    (SELECT count(*) FROM knowledge_graph_entities WHERE entity_type = 'course') AS courses"""

ENTITY_SOURCES_SQL = """SELECT DISTINCT
       d.sha256 AS document_sha256,
       d.edition,
       d.participant_name,
       w.label AS document_title
FROM knowledge_graph_relations r
JOIN documents d ON d.sha256 = r.source_document_sha256
JOIN knowledge_graph_entities w ON w.entity_id = r.source_entity_id
WHERE r.relation_type = %(relation_type)s
  AND r.target_entity_id = %(entity_id)s
ORDER BY d.edition, d.participant_name, d.sha256
LIMIT %(source_limit)s"""

EDITION_SOURCES_SQL = """SELECT DISTINCT
       d.sha256 AS document_sha256,
       d.edition,
       d.participant_name,
       w.label AS document_title
FROM knowledge_graph_relations r
JOIN documents d ON d.sha256 = r.source_document_sha256
JOIN knowledge_graph_entities w ON w.entity_id = r.source_entity_id
WHERE r.relation_type = 'PRESENTED_IN'
  AND r.target_entity_id = %(entity_id)s
ORDER BY d.participant_name, d.sha256
LIMIT %(source_limit)s"""


def _canonical_pattern(value: str) -> str:
    return "%" + normalize_question(value) + "%"


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items()} for row in rows]


def _sources_for_entity(conn: Any, entity_id: str, relation_type: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        ENTITY_SOURCES_SQL,
        {"entity_id": entity_id, "relation_type": relation_type, "source_limit": 10},
    ).fetchall()
    return _serialize_rows(rows)


def execute_structural_query(conn: Any, plan: QueryPlan) -> GraphQueryResult:
    if plan.route != "structural":
        raise ValueError("O plano informado não é estrutural")
    started = time.perf_counter()
    sources: list[dict[str, Any]] = []

    if plan.intent == "top_advisors":
        sql_text = TOP_ADVISORS_SQL
        rows = conn.execute(sql_text, {"limit": int(plan.parameters.get("limit", 10))}).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            first = serialized[0]
            sources = _sources_for_entity(conn, first["entity_id"], "ADVISED_BY")
            answer = (
                f"O orientador com maior número de trabalhos no grafo é {first['label']}, "
                f"com {first['work_count']} trabalhos distintos. A contagem foi obtida "
                "diretamente das relações ADVISED_BY, sem geração ou estimativa da LLM."
            )
        else:
            answer = "Não foram encontradas relações de orientação no grafo."
        query_identifier = "graph.top_advisors.v1"

    elif plan.intent == "top_courses":
        sql_text = TOP_COURSES_SQL
        rows = conn.execute(sql_text, {"limit": int(plan.parameters.get("limit", 10))}).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            first = serialized[0]
            sources = _sources_for_entity(conn, first["entity_id"], "ASSOCIATED_WITH_COURSE")
            ranking = "; ".join(
                f"{position}. {row['label']} ({row['work_count']} trabalhos)"
                for position, row in enumerate(serialized, start=1)
            )
            answer = f"Os cursos com mais trabalhos identificados são: {ranking}."
        else:
            answer = "Não foram encontrados cursos associados aos trabalhos."
        query_identifier = "graph.top_courses.v2"

    elif plan.intent == "works_by_edition":
        sql_text = WORKS_BY_EDITION_SQL
        rows = conn.execute(sql_text, {"edition": str(plan.parameters["edition"])}).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            first = serialized[0]
            source_rows = conn.execute(
                EDITION_SOURCES_SQL,
                {"entity_id": first["entity_id"], "source_limit": 10},
            ).fetchall()
            sources = _serialize_rows(source_rows)
            answer = (
                f"A {first['label']} possui {first['work_count']} trabalhos distintos "
                "registrados no grafo."
            )
        else:
            answer = f"Não foram encontrados trabalhos para a edição {plan.parameters['edition']}."
        query_identifier = "graph.works_by_edition.v1"

    elif plan.intent == "works_per_edition":
        sql_text = WORKS_PER_EDITION_SQL
        rows = conn.execute(sql_text).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            total = sum(int(row["work_count"]) for row in serialized)
            largest = max(serialized, key=lambda row: int(row["work_count"]))
            distribution = "; ".join(
                f"{row['label']}: {row['work_count']} trabalhos" for row in serialized
            )
            answer = (
                f"A distribuição integral do corpus é: {distribution}. "
                f"O total é {total} trabalhos, e {largest['label']} apresenta a maior "
                f"quantidade, com {largest['work_count']} trabalhos."
            )
        else:
            answer = "Não foram encontradas relações entre trabalhos e edições no grafo."
        query_identifier = "graph.works_per_edition.v1"

    elif plan.intent == "works_by_advisor":
        sql_text = WORKS_BY_ADVISOR_SQL
        rows = conn.execute(
            sql_text,
            {"advisor_pattern": _canonical_pattern(str(plan.parameters["advisor_name"]))},
        ).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            first = serialized[0]
            sources = _sources_for_entity(conn, first["entity_id"], "ADVISED_BY")
            editions = sorted({int(source["edition"]) for source in sources})
            titles = "; ".join(
                f"{source['document_title']} (Edição {source['edition']})" for source in sources
            )
            answer = (
                f"{first['label']} está associado(a) a {first['work_count']} trabalhos distintos "
                f"pela relação ADVISED_BY, nas edições {', '.join(str(value) for value in editions)}. "
                f"Trabalhos exibidos: {titles}."
            )
        else:
            answer = (
                "Não foi encontrado um orientador correspondente ao nome informado. "
                "A busca utiliza o nome normalizado armazenado no grafo."
            )
        query_identifier = "graph.works_by_advisor.v1"

    elif plan.intent == "works_by_author":
        sql_text = WORKS_BY_AUTHOR_SQL
        rows = conn.execute(
            sql_text,
            {"author_pattern": _canonical_pattern(str(plan.parameters["author_name"]))},
        ).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            first = serialized[0]
            sources = _sources_for_entity(conn, first["entity_id"], "AUTHORED_BY")
            editions = sorted({int(source["edition"]) for source in sources})
            titles = "; ".join(
                f"{source['document_title']} (Edição {source['edition']})" for source in sources
            )
            answer = (
                f"{first['label']} apresentou {first['work_count']} trabalhos no corpus, "
                f"nas edições {', '.join(str(value) for value in editions)}: {titles}."
            )
        else:
            answer = (
                "Não foi encontrado um autor principal correspondente ao nome informado. "
                "A consulta utiliza a relação AUTHORED_BY e o nome normalizado do participante principal."
            )
        query_identifier = "graph.works_by_author.v1"

    elif plan.intent == "works_by_course":
        sql_text = WORKS_BY_COURSE_SQL
        rows = conn.execute(
            sql_text,
            {"course_pattern": _canonical_pattern(str(plan.parameters["course_name"]))},
        ).fetchall()
        serialized = _serialize_rows(rows)
        if serialized:
            first = serialized[0]
            sources = _sources_for_entity(conn, first["entity_id"], "ASSOCIATED_WITH_COURSE")
            answer = (
                f"O curso {first['label']} está associado a {first['work_count']} trabalhos "
                f"distintos no grafo. A interface apresenta {len(sources)} documentos de exemplo "
                "com seus títulos e edições; a contagem considera todos os documentos relacionados."
            )
        else:
            answer = "Não foi encontrado um curso correspondente ao nome informado."
        query_identifier = "graph.works_by_course.v1"

    elif plan.intent == "corpus_summary":
        sql_text = CORPUS_SUMMARY_SQL
        row = conn.execute(sql_text).fetchone()
        serialized = _serialize_rows([row])
        answer = (
            f"O corpus possui {row['documents']} documentos. A projeção contém "
            f"{row['entities']} entidades e {row['relations']} relações, incluindo "
            f"{row['people']} pessoas e {row['courses']} cursos."
        )
        query_identifier = "graph.corpus_summary.v1"

    else:
        raise ValueError(f"Intenção estrutural não suportada: {plan.intent}")

    duration_ms = (time.perf_counter() - started) * 1000
    return GraphQueryResult(
        query_identifier=query_identifier,
        sql_text=sql_text.strip(),
        rows=serialized,
        sources=sources,
        answer_text=answer,
        duration_ms=duration_ms,
    )


def resolve_hybrid_scope(conn: Any, plan: QueryPlan) -> list[str] | None:
    if plan.route != "hybrid":
        return None
    if plan.intent == "semantic_by_edition":
        rows = conn.execute(
            """SELECT DISTINCT r.source_document_sha256 AS document_sha256
               FROM knowledge_graph_relations r
               JOIN knowledge_graph_entities e ON e.entity_id = r.target_entity_id
               WHERE r.relation_type = 'PRESENTED_IN'
                 AND e.canonical_key = %s""",
            (str(plan.parameters["edition"]),),
        ).fetchall()
        return [str(row["document_sha256"]).strip() for row in rows]
    if plan.intent == "semantic_by_advisor":
        rows = conn.execute(
            """SELECT DISTINCT r.source_document_sha256 AS document_sha256
               FROM knowledge_graph_relations r
               JOIN knowledge_graph_entities p ON p.entity_id = r.target_entity_id
               WHERE r.relation_type = 'ADVISED_BY'
                 AND p.canonical_key LIKE %s""",
            (_canonical_pattern(str(plan.parameters["advisor_name"])),),
        ).fetchall()
        return [str(row["document_sha256"]).strip() for row in rows]
    if plan.intent == "semantic_by_author":
        rows = conn.execute(
            """SELECT DISTINCT r.source_document_sha256 AS document_sha256
               FROM knowledge_graph_relations r
               JOIN knowledge_graph_entities p ON p.entity_id = r.target_entity_id
               WHERE r.relation_type = 'AUTHORED_BY'
                 AND p.canonical_key LIKE %s""",
            (_canonical_pattern(str(plan.parameters["author_name"])),),
        ).fetchall()
        return [str(row["document_sha256"]).strip() for row in rows]
    if plan.intent == "semantic_by_course":
        rows = conn.execute(
            """SELECT DISTINCT r.source_document_sha256 AS document_sha256
               FROM knowledge_graph_relations r
               JOIN knowledge_graph_entities c ON c.entity_id = r.target_entity_id
               WHERE r.relation_type = 'ASSOCIATED_WITH_COURSE'
                 AND c.canonical_key LIKE %s""",
            (_canonical_pattern(str(plan.parameters["course_name"])),),
        ).fetchall()
        return [str(row["document_sha256"]).strip() for row in rows]
    return None
