from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


EXTRACTION_VERSION = "graph-metadata-v1"


@dataclass(frozen=True)
class GraphDocumentMetadata:
    title: str | None
    author: str
    advisors: tuple[str, ...]
    course: str | None
    warnings: tuple[str, ...]


def canonical_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", without_marks.casefold()).split())


def deterministic_entity_id(entity_type: str, canonical_value: str) -> str:
    payload = f"{entity_type}:{canonical_value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def deterministic_relation_id(
    source_entity_id: str,
    relation_type: str,
    target_entity_id: str,
    document_sha256: str,
) -> str:
    payload = (
        f"{source_entity_id}:{relation_type}:{target_entity_id}:{document_sha256}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _lines(page_text: str) -> list[str]:
    return [line.strip() for line in page_text.splitlines() if line.strip()]


def _participant_index(lines: list[str], participant_name: str) -> int | None:
    participant_key = canonical_key(participant_name)
    return next(
        (
            index
            for index, line in enumerate(lines)
            if participant_key and participant_key in canonical_key(line)
        ),
        None,
    )


def extract_document_title(page_text: str, participant_name: str) -> str | None:
    lines = _lines(page_text)
    author_index = _participant_index(lines, participant_name)
    if author_index is None:
        return None
    header_start = 0
    for index, line in enumerate(lines[:author_index]):
        if line.upper().startswith("CÓDIGO:"):
            header_start = index + 1
    title_lines = [
        line
        for line in lines[header_start:author_index]
        if not line.upper().startswith(("CURSO:", "CÓDIGO:", "ISSN:"))
    ]
    title = " ".join(title_lines).strip()
    return title or None


def extract_course(page_text: str) -> str | None:
    for line in _lines(page_text)[:15]:
        match = re.match(r"^CURSO\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            course = " ".join(match.group(1).split()).strip(" .;,:")
            return course or None
    return None


def extract_advisor_names(page_text: str, participant_name: str) -> tuple[str, ...]:
    lines = _lines(page_text)
    author_index = _participant_index(lines, participant_name)
    if author_index is None:
        return ()

    affiliation_index = next(
        (
            index
            for index in range(author_index + 1, len(lines))
            if re.match(r"^1\s+", lines[index])
        ),
        None,
    )
    if affiliation_index is None:
        return ()

    author_block = " ".join(lines[author_index:affiliation_index])
    authors_by_number: dict[str, str] = {}
    for match in re.finditer(r"([^,]+?)\s+(\d+)\s*(?:,|$)", author_block):
        name = " ".join(match.group(1).split()).strip(" ,")
        if name:
            authors_by_number[match.group(2)] = name

    affiliation_lines: list[str] = []
    for line in lines[affiliation_index:]:
        if re.match(r"^(Introdução|INTRODUÇÃO)\s*:", line):
            break
        affiliation_lines.append(line)
    affiliation_block = " ".join(affiliation_lines)

    advisor_numbers: list[str] = []
    for marker in re.finditer(r"Orientador\s*\(a\)", affiliation_block, flags=re.IGNORECASE):
        starts = list(re.finditer(r"(?:^|,\s+)(\d+)\s+", affiliation_block[: marker.start()]))
        if starts:
            advisor_numbers.append(starts[-1].group(1))

    advisors: list[str] = []
    seen: set[str] = set()
    for number in advisor_numbers:
        name = authors_by_number.get(number)
        key = canonical_key(name or "")
        if name and key not in seen:
            advisors.append(name)
            seen.add(key)
    return tuple(advisors)


def extract_graph_metadata(page_text: str, participant_name: str) -> GraphDocumentMetadata:
    title = extract_document_title(page_text, participant_name)
    course = extract_course(page_text)
    advisors = extract_advisor_names(page_text, participant_name)
    warnings = []
    if title is None:
        warnings.append("title_not_found")
    if course is None:
        warnings.append("course_not_found")
    if not advisors:
        warnings.append("advisor_not_found")
    return GraphDocumentMetadata(
        title=title,
        author=" ".join(participant_name.split()),
        advisors=advisors,
        course=course,
        warnings=tuple(warnings),
    )

