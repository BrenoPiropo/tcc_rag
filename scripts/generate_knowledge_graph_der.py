from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_OUTPUT = ROOT / "artifacts" / "knowledge_graph" / "knowledge_graph_der.png"
TCC_OUTPUT = ROOT.parent / "Relatorio_Parcial_LaTeX_UESC_Anais" / "figuras" / "der_grafo_conhecimento.png"

WIDTH = 2400
HEIGHT = 1600
NAVY = "#173B57"
INK = "#17212B"
MUTED = "#5E6B75"
LINE = "#7C8992"
PAPER = "#FFFFFF"
PK_FILL = "#FFF2C9"
FK_FILL = "#DFF1ED"
ROW_FILL = "#F6F8F9"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size=size)


REGULAR = font("arial.ttf", 31)
SMALL = font("arial.ttf", 26)
BOLD = font("arialbd.ttf", 32)
TITLE = font("arialbd.ttf", 52)


def draw_table(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    size: tuple[int, int],
    title: str,
    rows: list[tuple[str, str]],
) -> dict[str, int]:
    x, y = xy
    width, height = size
    header_height = 76
    row_height = (height - header_height) // len(rows)
    draw.rounded_rectangle(
        (x, y, x + width, y + height), radius=12, fill=PAPER, outline=NAVY, width=4
    )
    draw.rounded_rectangle(
        (x, y, x + width, y + header_height), radius=12, fill=NAVY
    )
    draw.rectangle((x, y + header_height - 12, x + width, y + header_height), fill=NAVY)
    draw.text((x + 24, y + 19), title, font=BOLD, fill=PAPER)
    row_centers: dict[str, int] = {}
    for index, (marker, label) in enumerate(rows):
        top = y + header_height + index * row_height
        bottom = y + header_height + (index + 1) * row_height
        fill = PK_FILL if marker == "PK" else FK_FILL if marker == "FK" else ROW_FILL if index % 2 else PAPER
        draw.rectangle((x + 2, top, x + width - 2, bottom), fill=fill)
        draw.line((x, bottom, x + width, bottom), fill="#CBD2D7", width=2)
        if marker:
            draw.text((x + 22, top + 12), marker, font=SMALL, fill=NAVY)
        draw.text((x + 105, top + 12), label, font=SMALL, fill=INK)
        row_centers[label.split()[0]] = (top + bottom) // 2
    return row_centers


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    label: str,
    label_offset: tuple[int, int] = (0, -42),
) -> None:
    x1, y1 = start
    x2, y2 = end
    mid_x = (x1 + x2) // 2
    draw.line((x1, y1, mid_x, y1, mid_x, y2, x2, y2), fill=LINE, width=5)
    draw.polygon([(x2, y2), (x2 - 20, y2 - 12), (x2 - 20, y2 + 12)], fill=LINE)
    bbox = draw.textbbox((0, 0), label, font=SMALL)
    label_width = bbox[2] - bbox[0]
    lx = mid_x - label_width // 2 + label_offset[0]
    ly = min(y1, y2) + abs(y2 - y1) // 2 + label_offset[1]
    draw.rectangle((lx - 8, ly - 4, lx + label_width + 8, ly + 34), fill=PAPER)
    draw.text((lx, ly), label, font=SMALL, fill=MUTED)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((100, 64), "DER da projeção do grafo de conhecimento", font=TITLE, fill=INK)
    draw.text(
        (102, 132),
        "Anais da SIC/UESC - nós, relações e proveniência documental",
        font=REGULAR,
        fill=MUTED,
    )

    entity_rows = [
        ("PK", "entity_id  char(64)"),
        ("", "entity_type  text"),
        ("", "canonical_key  text"),
        ("", "label  text"),
        ("", "properties  jsonb"),
        ("", "extraction_version  text"),
        ("", "created_at  timestamptz"),
        ("UQ", "entity_type + canonical_key"),
    ]
    document_rows = [
        ("PK", "sha256  char(64)"),
        ("", "edition  smallint"),
        ("", "site_user_id  bigint"),
        ("", "participant_name  text"),
        ("", "source_path  text"),
        ("", "page_count  integer"),
    ]
    relation_rows = [
        ("PK", "relation_id  char(64)"),
        ("FK", "source_entity_id  char(64)"),
        ("", "relation_type  text"),
        ("FK", "target_entity_id  char(64)"),
        ("FK", "source_document_sha256  char(64)"),
        ("", "source_page_number  integer"),
        ("", "properties  jsonb"),
        ("", "extraction_version  text"),
        ("", "created_at  timestamptz"),
        ("UQ", "origem + tipo + destino + documento + página"),
    ]

    entity_xy = (100, 245)
    entity_size = (980, 610)
    document_xy = (100, 990)
    document_size = (980, 455)
    relation_xy = (1310, 320)
    relation_size = (990, 880)
    entity_centers = draw_table(
        draw, entity_xy, entity_size, "knowledge_graph_entities", entity_rows
    )
    document_centers = draw_table(
        draw, document_xy, document_size, "documents", document_rows
    )
    relation_centers = draw_table(
        draw, relation_xy, relation_size, "knowledge_graph_relations", relation_rows
    )

    entity_right = entity_xy[0] + entity_size[0]
    relation_left = relation_xy[0]
    arrow(
        draw,
        (entity_right, entity_centers["entity_id"]),
        (relation_left, relation_centers["source_entity_id"]),
        "1:N - nó de origem",
        (0, -52),
    )
    arrow(
        draw,
        (entity_right, entity_centers["entity_id"] + 34),
        (relation_left, relation_centers["target_entity_id"]),
        "1:N - nó de destino",
        (0, 12),
    )
    arrow(
        draw,
        (document_xy[0] + document_size[0], document_centers["sha256"]),
        (relation_left, relation_centers["source_document_sha256"]),
        "1:N - proveniência",
        (0, -46),
    )

    draw.text((1320, 1255), "Tipos de nó", font=BOLD, fill=NAVY)
    draw.text((1320, 1305), "work · person · edition · course", font=REGULAR, fill=INK)
    draw.text((1320, 1370), "Tipos de relação", font=BOLD, fill=NAVY)
    draw.text(
        (1320, 1420),
        "AUTHORED_BY · ADVISED_BY · PRESENTED_IN · ASSOCIATED_WITH_COURSE",
        font=SMALL,
        fill=INK,
    )
    draw.text((100, 1530), "Fonte: elaboração própria (2026).", font=SMALL, fill=MUTED)

    ARTIFACT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TCC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(ARTIFACT_OUTPUT, format="PNG", optimize=True)
    image.save(TCC_OUTPUT, format="PNG", optimize=True)
    print(ARTIFACT_OUTPUT)
    print(TCC_OUTPUT)


if __name__ == "__main__":
    main()

