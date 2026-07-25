"""Procesa los PDFs de data/ en chunks de texto y tablas para el sistema RAG.

A diferencia de una extraccion plana, aqui las tablas se detectan y se
serializan como Markdown antes de trocear. Eso preserva la relacion
modelo -> especificacion (p. ej. "PAS 6043 | 20 W/K | 230 V"), que es
justo lo que se pierde cuando un extractor aplasta las columnas y deja
valores sin dueno.

Cada chunk sale con la metadata necesaria para citar la fuente exacta
(archivo + pagina) y un campo `type` que distingue tabla de prosa, para
poder filtrar o priorizar en el retrieval.

Uso:
    python scripts/process_pdfs.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "processed" / "chunks.jsonl"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
# Una tabla mas larga que esto se parte por filas, repitiendo la cabecera.
TABLE_MAX_CHARS = 1800
MIN_CHUNK_CHARS = 40


def clean_cell(value: str | None) -> str:
    """Normaliza una celda: sin saltos de linea ni espacios repetidos."""
    if not value:
        return ""
    return " ".join(value.split())


def table_to_markdown_blocks(rows: list[list[str | None]]) -> list[str]:
    """Convierte una tabla en uno o mas bloques Markdown.

    Si la tabla es grande se parte por filas y se repite la cabecera en
    cada bloque, para que ningun fragmento quede sin contexto de columna.
    """
    cleaned = [[clean_cell(cell) for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(row)]
    if len(cleaned) < 2:
        return []

    width = max(len(row) for row in cleaned)
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]

    # Descarta columnas totalmente vacias (artefacto comun de pdfplumber).
    keep = [i for i in range(width) if any(row[i] for row in cleaned)]
    if len(keep) < 2:
        return []
    cleaned = [[row[i] for i in keep] for row in cleaned]

    header, *body = cleaned
    if not body:
        return []

    head_md = "| " + " | ".join(header) + " |\n"
    head_md += "|" + "---|" * len(header) + "\n"

    blocks: list[str] = []
    current = head_md
    for row in body:
        line = "| " + " | ".join(row) + " |\n"
        if len(current) + len(line) > TABLE_MAX_CHARS and current != head_md:
            blocks.append(current.rstrip())
            current = head_md
        current += line
    if current != head_md:
        blocks.append(current.rstrip())
    return blocks


def extract_page(page) -> tuple[str, list[str]]:
    """Devuelve (prosa fuera de tablas, bloques Markdown de las tablas)."""
    tables = page.find_tables()
    bboxes = [t.bbox for t in tables]

    table_blocks: list[str] = []
    for table in tables:
        try:
            rows = table.extract()
        except Exception:
            continue
        table_blocks.extend(table_to_markdown_blocks(rows))

    def outside_tables(obj) -> bool:
        for x0, top, x1, bottom in bboxes:
            if x0 <= obj["x0"] and obj["x1"] <= x1 and top <= obj["top"] and obj["bottom"] <= bottom:
                return False
        return True

    if bboxes:
        prose = page.filter(outside_tables).extract_text() or ""
    else:
        prose = page.extract_text() or ""

    return " ".join(prose.split()), table_blocks


def process_pdf(path: Path, splitter: RecursiveCharacterTextSplitter) -> list[dict]:
    chunks: list[dict] = []
    index = 0
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            try:
                prose, table_blocks = extract_page(page)
            except Exception as exc:
                print(f"    [warn] {path.name} p{page_number}: {exc}", file=sys.stderr)
                continue

            for block in table_blocks:
                chunks.append(
                    {
                        "id": f"{path.stem}-p{page_number}-t{index}",
                        "source": path.name,
                        "page": page_number,
                        "type": "table",
                        "text": block,
                    }
                )
                index += 1

            for piece in splitter.split_text(prose):
                if len(piece) < MIN_CHUNK_CHARS:
                    continue
                chunks.append(
                    {
                        "id": f"{path.stem}-p{page_number}-c{index}",
                        "source": path.name,
                        "page": page_number,
                        "type": "text",
                        "text": piece,
                    }
                )
                index += 1
    return chunks


def main() -> None:
    pdf_paths = sorted(DATA_DIR.glob("*.pdf"))
    if not pdf_paths:
        print(f"No se encontraron PDFs en {DATA_DIR}")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    totals = {"table": 0, "text": 0}
    duplicates = 0
    failed: list[str] = []

    with OUTPUT_PATH.open("w", encoding="utf-8") as out_file:
        for pdf_path in pdf_paths:
            try:
                chunks = process_pdf(pdf_path, splitter)
            except Exception as exc:
                print(f"  [ERROR] {pdf_path.name}: {exc}", file=sys.stderr)
                failed.append(pdf_path.name)
                continue

            kept = {"table": 0, "text": 0}
            for chunk in chunks:
                # Deduplica contenido identico (paginas repetidas, boilerplate).
                digest = hashlib.sha1(chunk["text"].encode("utf-8")).hexdigest()
                if digest in seen:
                    duplicates += 1
                    continue
                seen.add(digest)
                out_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                kept[chunk["type"]] += 1

            totals["table"] += kept["table"]
            totals["text"] += kept["text"]
            print(f"  {pdf_path.name}: {kept['text']} texto + {kept['table']} tablas")

    total = totals["table"] + totals["text"]
    print(f"\nProcesados {len(pdf_paths) - len(failed)}/{len(pdf_paths)} PDFs")
    print(f"  {total} chunks ({totals['text']} texto, {totals['table']} tablas)")
    print(f"  {duplicates} descartados por duplicado")
    print(f"Guardado en: {OUTPUT_PATH}")
    if failed:
        print(f"Fallaron: {', '.join(failed)}", file=sys.stderr)


if __name__ == "__main__":
    main()
