"""Punto de entrada del backend (CONTRATO 3). Lo consume la UI.

Dos modos, con la misma firma y la misma forma de salida:

  - Con OPENAI_API_KEY: agente ReAct. El LLM razona, decide que herramienta
    usar y redacta. Puede responder preguntas abiertas sobre la documentacion,
    no solo el flujo de dimensionamiento.
  - Sin API key: grafo deterministico. Cubre la ruta de dimensionamiento y no
    necesita credenciales, asi que la demo nunca se queda sin nada que enseñar.

En ambos modos los campos estructurados del panel (recomendacion, alternativa,
supuestos, fuentes) se calculan en Python. El texto del agente va a `mensaje`,
pero ninguna cifra del panel depende de que el modelo no alucine.

Devuelve `dict`, no la dataclass, para que el mock de la UI y este backend real
sean intercambiables cambiando un unico import en app.py.
"""
from __future__ import annotations

from typing import Any

from src.agents.explicador import (
    construir_recomendacion,
    elegir_alternativa,
    holgura_de,
)
from src.agents.extractor import extraer_parametros
from src.contracts import Respuesta
from src.graph import GRAFO
from src.state import estado_inicial, faltantes
from src.tools.catalogo import cargar_catalogo, filtrar_candidatos
from src.tools.dimensionar import dimensionar

# Se crea una sola vez: montar el agente en cada turno anadiria latencia inutil.
_AGENTE = None
_AGENTE_RESUELTO = False


def _agente():
    global _AGENTE, _AGENTE_RESUELTO
    if not _AGENTE_RESUELTO:
        from src.agents.agente import crear_agente

        _AGENTE = crear_agente()
        _AGENTE_RESUELTO = True
    return _AGENTE


def _panel_estructurado(caso: dict[str, Any]) -> dict[str, Any]:
    """Calcula recomendacion, alternativa, supuestos y fuentes desde Python.

    Devuelve dict vacio si el caso aun no tiene los parametros necesarios.
    """
    if faltantes(caso):
        return {}

    dim = dimensionar(
        disipacion_w=caso["disipacion_w"],
        t_ambiente_c=caso["t_ambiente_c"],
        t_interior_objetivo_c=caso["t_interior_objetivo_c"],
        alto_mm=caso["alto_mm"],
        ancho_mm=caso.get("ancho_mm", caso["alto_mm"]),
        fondo_mm=caso.get("fondo_mm", caso["alto_mm"]),
    )
    productos, _ = cargar_catalogo()
    candidatos, _descartes = filtrar_candidatos(
        productos,
        tecnologia=dim.tecnologia,
        carga_min_w=dim.rango_min_w,
        carga_max_w=dim.rango_max_w,
        delta_t_k=dim.delta_t_k,
    )

    principal = alternativa = None
    fuentes: list[dict[str, Any]] = []
    if candidatos:
        principal = construir_recomendacion(candidatos[0], dim, True)
        fuentes.extend(principal.fuentes)
        if alt := elegir_alternativa(candidatos, candidatos[0]):
            alternativa = construir_recomendacion(
                alt, dim, False, holgura_principal=holgura_de(candidatos[0], dim)
            )
            fuentes.extend(alternativa.fuentes)

    return {
        "recomendacion": principal,
        "alternativa": alternativa,
        "supuestos": dim.supuestos,
        "fuentes": fuentes,
        "trazas": dim.trazas,
    }


def _correr_agente(mensaje: str, sesion: dict[str, Any]) -> tuple[str, list[str]]:
    """Ejecuta el agente ReAct. Devuelve (texto, trazas de herramientas)."""
    agente = _agente()
    historial = sesion.setdefault("mensajes", [])
    historial.append({"role": "user", "content": mensaje})

    resultado = agente.invoke({"messages": historial})
    mensajes = resultado["messages"]

    trazas: list[str] = []
    for m in mensajes:
        for llamada in getattr(m, "tool_calls", None) or []:
            args = ", ".join(f"{k}={v!r}" for k, v in list(llamada["args"].items())[:3])
            trazas.append(f"herramienta: {llamada['name']}({args})")

    texto = mensajes[-1].content if mensajes else ""
    if isinstance(texto, list):  # algunos modelos devuelven bloques
        texto = " ".join(str(b.get("text", b)) for b in texto)

    sesion["mensajes"] = [
        {"role": getattr(m, "type", "assistant"), "content": str(m.content)}
        for m in mensajes
        if getattr(m, "content", None)
    ][-12:]  # ventana corta: memoria de sesion, no historia larga

    return texto, trazas


def responder(mensaje: str, sesion: dict[str, Any]) -> dict[str, Any]:
    """Procesa un turno de conversacion.

    `sesion` es la memoria del caso actual: pasala de vuelta en cada llamada
    para que el agente no vuelva a preguntar lo que ya sabe.
    """
    caso, trazas_extraccion = extraer_parametros(mensaje, sesion.get("caso", {}))
    sesion["caso"] = caso

    if _agente() is not None:
        texto, trazas_agente = _correr_agente(mensaje, sesion)
        panel = _panel_estructurado(caso)
        respuesta = Respuesta(
            mensaje=texto,
            preguntas_pendientes=[],  # el agente pregunta dentro del propio texto
            recomendacion=panel.get("recomendacion"),
            alternativa=panel.get("alternativa"),
            supuestos=panel.get("supuestos", []),
            fuentes=panel.get("fuentes", []),
            trazas=["modo: agente ReAct con LLM"]
            + trazas_extraccion
            + trazas_agente
            + panel.get("trazas", []),
            caso=caso,
        )
    else:
        estado = estado_inicial(mensaje, sesion)
        final = GRAFO.invoke(estado)
        respuesta = Respuesta(
            mensaje=final.get("respuesta", ""),
            preguntas_pendientes=final.get("preguntas_pendientes", []),
            recomendacion=final.get("recomendacion"),
            alternativa=final.get("alternativa"),
            supuestos=final.get("supuestos", []),
            fuentes=final.get("fuentes", []),
            trazas=["modo: determinístico (sin API key)"] + final.get("trazas", []),
            caso=final.get("caso", {}),
        )
        sesion["caso"] = final.get("caso", {})

    sesion.setdefault("historial", []).append(
        {"usuario": mensaje, "agente": respuesta.mensaje}
    )
    return respuesta.to_dict()
