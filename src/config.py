"""Configuracion centralizada del proyecto.

Unico punto de verdad para credenciales y parametros. El resto del codigo nunca
llama a os.getenv directamente.

Decision de stack: **todo gratuito**.

  - LLM: Groq (tier gratuito, sin tarjeta). Sirve modelos Llama con tool
    calling, que es lo que el agente necesita para razonar y decidir que
    herramienta usar. Cambiar de proveedor = reescribir `crear_llm()`.
  - Embeddings: modelo local ONNX empaquetado con chromadb. Cero API key, cero
    coste, cero cuota que se agote en mitad de la demo.

OpenAI queda como alternativa opcional (PROVEEDOR_LLM=openai), pero requiere
credito: una cuenta sin saldo devuelve 429 insufficient_quota aunque la clave
sea valida.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── LLM ────────────────────────────────────────────────────────────────
    # "groq" (gratuito) | "openai" (requiere credito)
    proveedor_llm: str = Field(default="groq", alias="PROVEEDOR_LLM")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    # Llama 3.3 70B: soporta tool calling, necesario para el agente ReAct.
    modelo_groq: str = Field(default="llama-3.3-70b-versatile", alias="MODELO_GROQ")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    modelo_llm: str = Field(default="gpt-4o-mini", alias="MODELO_LLM")

    # 0.0: las respuestas tecnicas deben ser reproducibles entre ejecuciones.
    temperatura: float = Field(default=0.0, alias="TEMPERATURA_LLM")

    # ── Embeddings ─────────────────────────────────────────────────────────
    # "local" (gratis, 384 dim) | "openai" (requiere credito, 1536 dim)
    modo_embeddings: str = Field(default="local", alias="MODO_EMBEDDINGS")
    modelo_embeddings: str = Field(
        default="text-embedding-3-small", alias="MODELO_EMBEDDINGS"
    )

    @property
    def hay_llm(self) -> bool:
        """Si no hay clave del proveedor activo, el sistema cae a modo determinístico."""
        if self.proveedor_llm == "openai":
            return bool(self.openai_api_key.strip())
        return bool(self.groq_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def crear_llm():
    """Factory del LLM. Cambiar de proveedor es cambiar solo esta funcion.

    Devuelve None si no hay API key, para que el agente pueda operar en modo
    deterministico y la demo siga siendo ejecutable sin credenciales.
    """
    settings = get_settings()
    if not settings.hay_llm:
        return None

    if settings.proveedor_llm == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.modelo_llm,
            temperature=settings.temperatura,
            api_key=settings.openai_api_key,
        )

    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.modelo_groq,
        temperature=settings.temperatura,
        api_key=settings.groq_api_key,
    )


def describir_llm() -> str:
    settings = get_settings()
    if not settings.hay_llm:
        return "sin LLM (modo determinístico)"
    if settings.proveedor_llm == "openai":
        return f"OpenAI {settings.modelo_llm}"
    return f"Groq {settings.modelo_groq} (gratuito)"
