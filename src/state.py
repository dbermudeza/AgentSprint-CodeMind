"""Estado del grafo: el contrato de datos que viaja entre nodos.

`caso` es la memoria de sesion: acumula los parametros que el usuario ha ido
dando a lo largo de la conversacion. Es lo que permite cumplir el invariante
de no volver a preguntar un dato ya entregado.

No persiste entre ejecuciones, por diseno (CLAUDE.md: solo memoria de sesion).
"""
from __future__ import annotations

from typing import Any, TypedDict

# Parametros sin los cuales no se puede estimar nada. El intake solo pregunta
# por los que falten de esta lista.
CAMPOS_CRITICOS: dict[str, str] = {
    "disipacion_w": "¿Cuánta potencia disipan los componentes dentro del gabinete, en vatios?",
    "t_ambiente_c": "¿Cuál es la temperatura ambiente máxima del lugar donde está el gabinete, en °C?",
    "t_interior_objetivo_c": "¿Qué temperatura máxima quieres mantener dentro del gabinete, en °C?",
    "alto_mm": "¿Cuáles son las dimensiones del gabinete (alto x ancho x fondo, en mm)?",
}

# Se derivan de la misma respuesta que alto_mm, asi que no se preguntan aparte.
CAMPOS_DIMENSION = ("alto_mm", "ancho_mm", "fondo_mm")


class AgentState(TypedDict, total=False):
    mensaje: str
    caso: dict[str, Any]
    historial: list[dict[str, str]]

    dimensionamiento: Any | None
    candidatos: list[Any]
    descartes: list[str]
    origen_catalogo: str

    preguntas_pendientes: list[str]
    respuesta: str
    recomendacion: Any | None
    alternativa: Any | None
    supuestos: list[str]
    fuentes: list[dict[str, Any]]
    trazas: list[str]


def faltantes(caso: dict[str, Any]) -> list[str]:
    """Campos criticos que el usuario todavia no ha dado."""
    return [campo for campo in CAMPOS_CRITICOS if caso.get(campo) is None]


def estado_inicial(mensaje: str, sesion: dict[str, Any] | None = None) -> AgentState:
    sesion = sesion or {}
    return AgentState(
        mensaje=mensaje,
        caso=dict(sesion.get("caso", {})),
        historial=list(sesion.get("historial", [])),
        preguntas_pendientes=[],
        supuestos=[],
        fuentes=[],
        trazas=[],
        candidatos=[],
        descartes=[],
        dimensionamiento=None,
        recomendacion=None,
        alternativa=None,
    )
