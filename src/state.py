"""Estado del grafo: el contrato de datos que viaja entre nodos.

`caso` es la memoria de sesion: acumula los parametros que el usuario ha ido
dando a lo largo de la conversacion. Es lo que permite cumplir el invariante
de no volver a preguntar un dato ya entregado.

No persiste entre ejecuciones, por diseno (CLAUDE.md: solo memoria de sesion).
"""
from __future__ import annotations

from typing import Any, TypedDict

# Unico dato que no se puede suponer: la carga interna es lo que define el
# problema y varia por ordenes de magnitud entre gabinetes. Todo lo demas tiene
# un valor tipico de industria razonable, y exigirlo antes de responder solo
# anade fricción a la conversacion.
CAMPOS_CRITICOS: dict[str, str] = {
    "disipacion_w": "¿Cuánta potencia disipan los componentes dentro del gabinete, en vatios?",
}

# Valores por defecto de industria. Se aplican solo si el usuario no los dio, y
# SIEMPRE se declaran como supuesto en la respuesta: rellenar un hueco en
# silencio seria asumir un dato, que es justo lo que el proyecto prohibe.
VALORES_TIPICOS: dict[str, tuple[float, str]] = {
    "t_ambiente_c": (35.0, "temperatura ambiente de 35 °C (entorno industrial típico)"),
    # 40 °C y no 35: con ambos a 35 el ΔT sale 0 y el balance concluye siempre
    # "refrigeracion activa" por definicion, sin informar de nada. 40 °C dentro
    # con 35 fuera es ademas el emparejamiento habitual en electronica de
    # control, y deja que el calculo distinga tecnologias de verdad.
    "t_interior_objetivo_c": (
        40.0,
        "temperatura interior objetivo de 40 °C (límite habitual para electrónica de control)",
    ),
    "alto_mm": (2000.0, "gabinete estándar de 2000 × 800 × 600 mm"),
    "ancho_mm": (800.0, ""),
    "fondo_mm": (600.0, ""),
}


def aplicar_valores_tipicos(caso: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Rellena lo que falte con valores tipicos y devuelve los supuestos usados."""
    caso = dict(caso)
    supuestos: list[str] = []
    for campo, (valor, descripcion) in VALORES_TIPICOS.items():
        if caso.get(campo) is None:
            caso[campo] = valor
            if descripcion:
                supuestos.append(f"Se asumió {descripcion}; corrígelo si tu caso difiere.")
    return caso, supuestos

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
