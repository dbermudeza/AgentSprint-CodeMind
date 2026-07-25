"""Configuracion centralizada del proyecto.

Unico punto de verdad para credenciales y parametros del LLM. El resto del
codigo nunca llama a os.getenv directamente.

Decision de stack (CLAUDE.md:120): se usa OpenAI. `.env.example` ya trae
OPENAI_API_KEY y las dependencias estan pineadas a langchain-openai; migrar a
Gemini cuesta tiempo de hackathon y no aporta nada a la demo. Cambiar de
proveedor = reescribir `crear_llm()` y nada mas.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    # Modelo de bajo costo y baja latencia, como pide CLAUDE.md para la demo.
    modelo_llm: str = Field(default="gpt-4o-mini", alias="MODELO_LLM")
    # 0.0: las respuestas tecnicas deben ser reproducibles entre ejecuciones.
    temperatura: float = Field(default=0.0, alias="TEMPERATURA_LLM")

    @property
    def hay_llm(self) -> bool:
        """Si no hay clave, el sistema cae a modo deterministico (sin LLM)."""
        return bool(self.openai_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def crear_llm():
    """Factory del LLM. Cambiar de proveedor es cambiar solo esta funcion.

    Devuelve None si no hay API key configurada, para que el agente pueda
    operar en modo deterministico y la demo siga siendo ejecutable sin
    credenciales.
    """
    settings = get_settings()
    if not settings.hay_llm:
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.modelo_llm,
        temperature=settings.temperatura,
        api_key=settings.openai_api_key,
    )
