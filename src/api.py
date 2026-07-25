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

import re
from typing import Any

from src.agents.explicador import (
    construir_recomendacion,
    elegir_alternativa,
    holgura_de,
)
from src.agents.extractor import extraer_parametros
from src.contracts import Respuesta
from src.graph import GRAFO
from src.state import CAMPOS_CRITICOS, estado_inicial, faltantes
from src.tools.catalogo import cargar_catalogo, filtrar_candidatos
from src.tools.dimensionar import dimensionar

# Se crea una sola vez: montar el agente en cada turno anadiria latencia inutil.
_AGENTE = None
_AGENTE_RESUELTO = False

# Marcas de consulta a la documentacion, frente a la entrega de datos del caso.
_INTERROGATIVA = re.compile(
    r"\?|\b(qu[eé]|cu[aá]l|cu[aá]les|c[oó]mo|d[oó]nde|por qu[eé]|existe|hay|"
    r"tienen|sirve|recomienda[sn]?|diferencia|compara|explica|dime)\b",
    re.IGNORECASE,
)


def _agente():
    global _AGENTE, _AGENTE_RESUELTO
    if not _AGENTE_RESUELTO:
        from src.agents.agente import crear_agente

        _AGENTE = crear_agente()
        _AGENTE_RESUELTO = True
    return _AGENTE


def _es_limite_de_cuota(exc: Exception) -> bool:
    """Distingue un agotamiento de cuota de un fallo real del codigo.

    Solo la cuota justifica degradar en silencio; cualquier otro error debe
    propagarse para que no quede oculto.
    """
    detalle = str(exc).lower()
    return "rate limit" in detalle or "429" in detalle or "quota" in detalle


def _es_pregunta_abierta(mensaje: str, caso: dict[str, Any]) -> bool:
    """¿Es una consulta que solo el LLM podria responder?

    Se considera abierta si no aporta ningun parametro del gabinete y no hay
    caso previo en marcha. Un "necesito enfriar un armario" sin datos sigue
    siendo intake valido, porque no interroga a la documentacion; una pregunta
    sobre productos o aplicaciones, en cambio, exige buscar y razonar.
    """
    if any(caso.get(c) is not None for c in CAMPOS_CRITICOS):
        return False  # hay un caso en marcha: el flujo de intake aplica
    return bool(_INTERROGATIVA.search(mensaje))


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

    # Se guarda solo la conversacion: turnos del usuario y respuestas finales
    # del agente. Las llamadas a herramienta y sus resultados se descartan.
    #
    # No es por ahorrar espacio: un mensaje `tool` necesita su `tool_call_id`
    # y el mensaje `ai` que lo invoco, y al serializar a dict se perdian. El
    # turno siguiente reenviaba un historial invalido y el proveedor fallaba
    # con KeyError: 'tool_call_id'. El razonamiento intermedio no aporta
    # contexto al turno siguiente; la conversacion si.
    conversacion: list[dict[str, str]] = []
    for m in mensajes:
        tipo = getattr(m, "type", None)
        if tipo not in ("human", "ai"):
            continue
        if getattr(m, "tool_calls", None):  # paso intermedio, no respuesta
            continue
        contenido = str(m.content or "").strip()
        if contenido:
            conversacion.append(
                {"role": "user" if tipo == "human" else "assistant", "content": contenido}
            )

    sesion["mensajes"] = conversacion[-10:]  # ventana corta de memoria de sesion

    return texto, trazas


def responder(mensaje: str, sesion: dict[str, Any]) -> dict[str, Any]:
    """Procesa un turno de conversacion.

    `sesion` es la memoria del caso actual: pasala de vuelta en cada llamada
    para que el agente no vuelva a preguntar lo que ya sabe.
    """
    caso, trazas_extraccion = extraer_parametros(mensaje, sesion.get("caso", {}))
    sesion["caso"] = caso

    texto = trazas_agente = None
    if _agente() is not None:
        try:
            texto, trazas_agente = _correr_agente(mensaje, sesion)
        except Exception as exc:
            # La cuota gratuita de Groq se agota por tokens/dia. Antes que dejar
            # la demo sin respuesta, se cae al modo deterministico: cubre el
            # dimensionamiento y cumple los invariantes sin depender del LLM.
            if not _es_limite_de_cuota(exc):
                raise
            texto = None
            sesion.pop("mensajes", None)  # historial a medias, mejor descartarlo

    if texto is not None:
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
            + (trazas_agente or [])
            + panel.get("trazas", []),
            caso=caso,
        )
    else:
        degradado = _agente() is not None  # habia LLM pero se agoto la cuota

        # Sin LLM solo se cubre la ruta de dimensionamiento. Ante una pregunta
        # abierta, el grafo pediria las medidas del gabinete: una no-respuesta
        # disfrazada de respuesta. Es preferible decir que no se puede.
        if _es_pregunta_abierta(mensaje, caso):
            return Respuesta(
                mensaje=(
                    "No puedo responder esa pregunta ahora mismo.\n\n"
                    + (
                        "**Por qué:** la cuota diaria del modelo de lenguaje se ha "
                        "agotado, y sin él no puedo buscar en la documentación ni "
                        "razonar sobre preguntas abiertas.\n\n"
                        if degradado
                        else "**Por qué:** no hay modelo de lenguaje configurado, así "
                        "que no puedo buscar en la documentación ni razonar sobre "
                        "preguntas abiertas.\n\n"
                    )
                    + "**Qué sí puedo hacer:** dimensionar un gabinete. Dame la "
                    "disipación en W, las temperaturas ambiente y objetivo, y las "
                    "medidas, y te doy la recomendación con sus fuentes.\n\n"
                    + (
                        "**Para preguntas abiertas:** espera al reinicio diario de la "
                        "cuota o consulta la documentación oficial de Pfannenberg."
                        if degradado
                        else "**Para preguntas abiertas:** configura `GROQ_API_KEY` "
                        "(gratuita en console.groq.com/keys)."
                    )
                ),
                trazas=["modo: determinístico — pregunta fuera de alcance sin LLM"],
                caso=caso,
            ).to_dict()

        estado = estado_inicial(mensaje, sesion)
        final = GRAFO.invoke(estado)
        aviso = (
            "⚠️ Cuota del LLM agotada: respondiendo en modo determinístico.\n\n"
            if degradado
            else ""
        )
        respuesta = Respuesta(
            mensaje=aviso + final.get("respuesta", ""),
            preguntas_pendientes=final.get("preguntas_pendientes", []),
            recomendacion=final.get("recomendacion"),
            alternativa=final.get("alternativa"),
            supuestos=final.get("supuestos", []),
            fuentes=final.get("fuentes", []),
            trazas=[
                "modo: determinístico"
                + (" (cuota del LLM agotada)" if degradado else " (sin API key)")
            ]
            + final.get("trazas", []),
            caso=final.get("caso", {}),
        )
        sesion["caso"] = final.get("caso", {})

    sesion.setdefault("historial", []).append(
        {"usuario": mensaje, "agente": respuesta.mensaje}
    )
    return respuesta.to_dict()
