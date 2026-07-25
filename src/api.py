"""Punto de entrada del backend (CONTRATO 3). Lo consume la UI.

Devuelve `dict`, no la dataclass, a proposito: asi el mock de la capa de
presentacion y este backend real son intercambiables cambiando un unico
import en app.py.
"""
from __future__ import annotations

from typing import Any

from src.contracts import Respuesta
from src.graph import GRAFO
from src.state import estado_inicial


def responder(mensaje: str, sesion: dict[str, Any]) -> dict[str, Any]:
    """Procesa un turno de conversacion.

    `sesion` es la memoria del caso actual: pasala de vuelta en cada llamada
    para que el agente no vuelva a preguntar lo que ya sabe. Se actualiza
    in-place con el caso y el historial.
    """
    estado = estado_inicial(mensaje, sesion)
    final = GRAFO.invoke(estado)

    respuesta = Respuesta(
        mensaje=final.get("respuesta", ""),
        preguntas_pendientes=final.get("preguntas_pendientes", []),
        recomendacion=final.get("recomendacion"),
        alternativa=final.get("alternativa"),
        supuestos=final.get("supuestos", []),
        fuentes=final.get("fuentes", []),
        trazas=final.get("trazas", []),
        caso=final.get("caso", {}),
    )

    # Memoria de sesion (no persistente entre ejecuciones).
    sesion["caso"] = final.get("caso", {})
    sesion.setdefault("historial", []).append(
        {"usuario": mensaje, "agente": respuesta.mensaje}
    )

    return respuesta.to_dict()
