"""Construye la base vectorial ChromaDB desde data/processed/chunks.jsonl.

Por defecto usa el modelo de embeddings local (all-MiniLM-L6-v2 via ONNX,
empaquetado con chromadb): sin API key, sin coste y sin cuota. La primera
ejecucion descarga ~80 MB de modelo y luego queda en cache.

Solo hay que ejecutarlo una vez, o cuando cambie el corpus:

    python scripts/build_vectorstore.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Permite ejecutar el script directamente (`python scripts/build_vectorstore.py`)
# sin exigir `python -m` ni tener el proyecto instalado.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.embeddings import describir_motor  # noqa: E402
from src.rag.vectorstore import CHROMA_DIR, indexar  # noqa: E402


def main() -> None:
    print(f"Motor de embeddings: {describir_motor()}")
    print(f"Destino: {CHROMA_DIR}\n")

    inicio = time.time()
    total = indexar()

    print(f"\n{total} chunks indexados en {time.time() - inicio:.0f} s")
    print("Búsqueda híbrida (BM25 + vectorial) activa.")


if __name__ == "__main__":
    main()
