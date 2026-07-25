"""Construye la base vectorial ChromaDB desde data/processed/chunks.jsonl.

Requiere OPENAI_API_KEY en .env: los embeddings se calculan con la API. Indexar
el corpus completo (~2.100 chunks) cuesta del orden de 0.02 USD con
text-embedding-3-small y tarda un par de minutos.

Solo hay que ejecutarlo una vez, o cuando cambie el corpus:

    python scripts/build_vectorstore.py
"""
from __future__ import annotations

import sys
import time

from src.config import get_settings
from src.rag.vectorstore import CHROMA_DIR, indexar


def main() -> None:
    if not get_settings().hay_llm:
        print(
            "Falta OPENAI_API_KEY en .env.\n"
            "Los embeddings la necesitan. Sin base vectorial el sistema sigue\n"
            "funcionando solo con BM25, pero pierde la búsqueda semántica.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"Indexando en {CHROMA_DIR} ...")
    inicio = time.time()
    total = indexar()
    print(f"\n{total} chunks indexados en {time.time() - inicio:.0f} s")
    print("Listo: la búsqueda híbrida (BM25 + vectorial) ya está activa.")


if __name__ == "__main__":
    main()
