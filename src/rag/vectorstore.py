"""Base vectorial (ChromaDB) sobre el corpus de PDFs oficiales.

Se eligio Chroma y no Pinecone: corre embebido en el proceso, persiste en
disco dentro del repo y no necesita cuenta, red ni API key propia. Para 2.100
chunks no hay ninguna ventaja practica en un servicio gestionado, y si una
dependencia de red que puede caerse en mitad de la demo.

Lo unico que requiere credencial son los embeddings (OPENAI_API_KEY), tanto al
indexar como al consultar, porque la pregunta hay que vectorizarla con el
mismo modelo con el que se indexo.

Devuelve `Fragmento` (CONTRATO 1), igual que el retriever lexico, para que
ambos sean intercambiables y combinables.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.contracts import Fragmento
from src.rag.embeddings import crear_embeddings

RAIZ = Path(__file__).resolve().parents[2]
CHUNKS_PATH = RAIZ / "data" / "processed" / "chunks.jsonl"
CHROMA_DIR = RAIZ / "data" / "processed" / "chroma"
COLECCION = "pfannenberg"

# Misma exclusion que el indice lexico: CLAUDE.md prohibe citar este PDF.
FUENTES_EXCLUIDAS = ("pfannenberg_cut-out_compatibility_list",)


def _excluido(fuente: str) -> bool:
    return any(p in fuente.lower() for p in FUENTES_EXCLUIDAS)


def cargar_chunks() -> list[dict]:
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        return [
            c for c in (json.loads(linea) for linea in f) if not _excluido(c["source"])
        ]


def _abrir(solo_lectura: bool = True):
    """Abre la coleccion Chroma persistida. None si aun no hay indice."""
    if solo_lectura and not existe_indice():
        return None
    embeddings = crear_embeddings()

    from langchain_chroma import Chroma

    return Chroma(
        collection_name=COLECCION,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )


def existe_indice() -> bool:
    return CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())


def indexar(lote: int = 200) -> int:
    """Construye la base vectorial desde chunks.jsonl. Devuelve n de chunks.

    Idempotente por reconstruccion: borra la coleccion previa para que no
    queden vectores huerfanos de una version anterior del corpus.
    """
    import shutil

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    store = _abrir(solo_lectura=False)
    chunks = cargar_chunks()
    for inicio in range(0, len(chunks), lote):
        trozo = chunks[inicio : inicio + lote]
        store.add_texts(
            texts=[c["text"] for c in trozo],
            metadatas=[
                {"fuente": c["source"], "pagina": c["page"], "tipo": c["type"]}
                for c in trozo
            ],
            ids=[c["id"] for c in trozo],
        )
        print(f"  indexados {min(inicio + lote, len(chunks))}/{len(chunks)}")

    return len(chunks)


def buscar_vectorial(
    consulta: str, k: int = 6, solo_tablas: bool = False
) -> list[Fragmento]:
    """Busqueda semantica. Lista vacia si no hay indice o no hay API key.

    Degradar en vacio en vez de reventar es deliberado: el retriever hibrido
    sigue funcionando solo con BM25, y la demo no se cae por una credencial.
    """
    store = _abrir()
    if store is None:
        return []

    filtro = {"tipo": "table"} if solo_tablas else None
    try:
        # `similarity_search` a secas y no la variante con relevance scores:
        # la fusion RRF usa el ORDEN, no la puntuacion, y la normalizacion de
        # Chroma emite avisos y devuelve valores negativos que aqui no aportan.
        documentos = store.similarity_search(consulta, k=k, filter=filtro)
    except Exception:
        return []

    return [
        Fragmento(
            texto=doc.page_content,
            fuente=doc.metadata.get("fuente", "desconocida"),
            pagina=int(doc.metadata.get("pagina", 0)),
            tipo=doc.metadata.get("tipo", "text"),
            # El puesto en la lista es lo que consume RRF; se guarda invertido
            # solo para que ordenar por score aqui siga teniendo sentido.
            score=float(len(documentos) - i),
        )
        for i, doc in enumerate(documentos)
    ]
