"""Recuperacion lexica (BM25) sobre el corpus de PDFs oficiales.

Por que BM25 y no embeddings: el corpus esta dominado por codigos de modelo
(DTS 3061, PAS 6133) y numeros de articulo. La busqueda semantica confunde
modelos de la misma familia -- "DTS 3061" y "DTS 3161" son casi identicos como
vector, pero uno refrigera 694 W y el otro 1235 W. Confundirlos es exactamente
el error que este proyecto no puede permitirse. BM25 trata el codigo como el
token discriminante que es. Ventaja adicional: cero API keys, todo local.

Contrato 1 (ver CONTRATOS.md y src/contracts.py):

    def buscar(consulta: str, k: int = 6, solo_tablas: bool = False) -> list[Fragmento]

Uso directo para inspeccionar el indice:

    python -m src.rag.retriever "capacidad de refrigeracion DTS 3061" --tablas
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.contracts import Fragmento

CHUNKS_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "chunks.jsonl"

# CLAUDE.md ("Zonas de baja confianza") prohibe usar este PDF: su matriz se
# extrae como ruido ilegible y ademas es la version 1.3 de 2017. Se excluye del
# indice entero, no solo del ranking, para que no pueda colarse en una cita.
FUENTES_EXCLUIDAS = ("pfannenberg_cut-out_compatibility_list",)

_PALABRA = re.compile(r"[a-z0-9]+")
_LETRAS_O_DIGITOS = re.compile(r"[a-z]+|\d+")
# Un prefijo de familia ("DTS", "PAS", "PWS") no pasa de 4 letras. Limitar el
# largo evita fabricar tokens absurdos como "capacity20".
MAX_PREFIJO = 4


def tokenizar(texto: str) -> list[str]:
    """Tokeniza preservando codigos alfanumericos escritos de cualquier forma.

    "PAS6043", "PAS 6043", "pas-6043" producen los mismos tokens, porque cada
    variante emite a la vez las piezas sueltas y la forma pegada:

        {"pas", "6043", "pas6043"}

    Sin esto, buscar "PAS 6043" no encontraria la tabla que escribe "PAS6043"
    -- y ese fallo es invisible: devuelve resultados, solo que los equivocados.
    """
    crudos = _PALABRA.findall(texto.lower())

    tokens: list[str] = []
    for token in crudos:
        tokens.append(token)
        partes = _LETRAS_O_DIGITOS.findall(token)
        if len(partes) > 1:  # "pas6043" -> "pas", "6043"
            tokens.extend(partes)

    for actual, siguiente in zip(crudos, crudos[1:]):  # "pas", "6043" -> "pas6043"
        if actual.isalpha() and len(actual) <= MAX_PREFIJO and siguiente.isdigit():
            tokens.append(actual + siguiente)

    return tokens


@dataclass
class _Indice:
    bm25: BM25Okapi
    chunks: list[dict]


_cache: dict[bool, _Indice] = {}
_corpus: list[dict] | None = None


def _cargar_corpus() -> list[dict]:
    """Lee chunks.jsonl una sola vez, ya filtrado de fuentes prohibidas."""
    global _corpus
    if _corpus is not None:
        return _corpus

    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"No existe {CHUNKS_PATH}. Genera el corpus con: python scripts/process_pdfs.py"
        )

    chunks: list[dict] = []
    with CHUNKS_PATH.open(encoding="utf-8") as archivo:
        for linea in archivo:
            chunk = json.loads(linea)
            fuente = chunk.get("source", "").lower()
            if fuente.startswith(FUENTES_EXCLUIDAS):
                continue
            chunks.append(chunk)

    _corpus = chunks
    return _corpus


def _obtener_indice(solo_tablas: bool) -> _Indice:
    """Indice BM25 perezoso, uno por subconjunto.

    Se indexa el subconjunto en vez de filtrar los resultados despues, para que
    `k` signifique siempre "k fragmentos utiles": filtrar a posteriori devuelve
    menos de k cuando las tablas no entran en el top-k global.
    """
    if solo_tablas in _cache:
        return _cache[solo_tablas]

    chunks = _cargar_corpus()
    if solo_tablas:
        chunks = [c for c in chunks if c.get("type") == "table"]

    _cache[solo_tablas] = _Indice(
        bm25=BM25Okapi([tokenizar(c["text"]) for c in chunks]),
        chunks=chunks,
    )
    return _cache[solo_tablas]


def buscar(consulta: str, k: int = 6, solo_tablas: bool = False) -> list[Fragmento]:
    """Recupera los `k` fragmentos mas relevantes del corpus oficial.

    `solo_tablas=True` restringe a chunks de tipo "table", donde viven las
    especificaciones por modelo. La prosa sirve para argumentar aplicacion, no
    para afirmar specs.

    Devuelve lista vacia si nada puntua: preferimos no citar a citar de mas,
    porque el invariante del proyecto es no afirmar sin fuente.
    """
    tokens = tokenizar(consulta)
    if not tokens:
        return []

    indice = _obtener_indice(solo_tablas)
    if not indice.chunks:
        return []

    puntajes = indice.bm25.get_scores(tokens)
    mejores = sorted(range(len(puntajes)), key=puntajes.__getitem__, reverse=True)[:k]

    return [
        Fragmento(
            texto=indice.chunks[i]["text"],
            fuente=indice.chunks[i]["source"],
            pagina=indice.chunks[i]["page"],
            tipo=indice.chunks[i]["type"],
            score=round(float(puntajes[i]), 3),
        )
        for i in mejores
        if puntajes[i] > 0
    ]


if __name__ == "__main__":
    import sys

    argumentos = [a for a in sys.argv[1:] if a != "--tablas"]
    consulta = " ".join(argumentos) or "capacidad de refrigeracion DTS 3061"

    for fragmento in buscar(consulta, solo_tablas="--tablas" in sys.argv):
        print(f"\n[{fragmento.score}] {fragmento.cita()}  ({fragmento.tipo})")
        print(fragmento.texto[:400])
