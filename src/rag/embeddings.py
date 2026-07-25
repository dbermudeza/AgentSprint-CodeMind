"""Embeddings para la base vectorial, con motor local por defecto.

Por que local y no OpenAI por defecto: los embeddings son la unica pieza que
necesitaria credito de API solo para *construir el indice*, algo que se hace
una vez y no aporta razonamiento. Usar el modelo local (all-MiniLM-L6-v2 via
ONNX, empaquetado con chromadb) deja la busqueda semantica funcionando sin
cuenta, sin coste y sin cuota que se agote a mitad de una demo.

El LLM si necesita credito: ahi el modelo aporta razonamiento real y no hay
sustituto local practico en este contexto.

Se puede forzar OpenAI con MODO_EMBEDDINGS=openai en .env, util si mas adelante
se quiere mas calidad de recuperacion semantica.

⚠️ Cambiar de motor cambia la dimension del vector (384 local vs 1536 OpenAI):
hay que reconstruir el indice entero, no vale mezclar.
"""
from __future__ import annotations

from typing import Any

from src.config import get_settings


class EmbeddingsLocales:
    """Adaptador del embedder ONNX de chromadb a la interfaz de LangChain.

    LangChain espera `embed_documents` / `embed_query`; chromadb expone un
    callable. Este puente permite usar el modelo local con `langchain_chroma`
    sin cambiar el resto del codigo.
    """

    def __init__(self) -> None:
        from chromadb.utils import embedding_functions as ef

        self._fn = ef.DefaultEmbeddingFunction()

    @staticmethod
    def _a_floats(vector: Any) -> list[float]:
        """Convierte a float nativo de Python.

        El embedder devuelve numpy: `list(array)` deja escalares np.float32 y
        chromadb los rechaza al insertar. `tolist()` si convierte de verdad.
        """
        return vector.tolist() if hasattr(vector, "tolist") else [float(x) for x in vector]

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        return [self._a_floats(v) for v in self._fn(textos)]

    def embed_query(self, texto: str) -> list[float]:
        return self._a_floats(self._fn([texto])[0])


def crear_embeddings() -> Any:
    """Motor de embeddings activo. Local salvo que se pida OpenAI en .env."""
    settings = get_settings()

    if settings.modo_embeddings == "openai":
        if not settings.hay_llm:
            raise RuntimeError(
                "MODO_EMBEDDINGS=openai requiere OPENAI_API_KEY en .env."
            )
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.modelo_embeddings, api_key=settings.openai_api_key
        )

    return EmbeddingsLocales()


def describir_motor() -> str:
    settings = get_settings()
    if settings.modo_embeddings == "openai":
        return f"OpenAI {settings.modelo_embeddings} (1536 dim, requiere crédito)"
    return "local all-MiniLM-L6-v2 vía ONNX (384 dim, sin API key)"
