"""Extraccion de parametros del caso a partir del mensaje del usuario.

Deliberadamente deterministico (regex) para los numeros, no LLM. En una demo
en vivo, que "2000x800x600 mm, 1200 W" se lea siempre igual vale mas que la
flexibilidad de un modelo: el parseo numerico es donde un LLM alucina caro y
donde una expresion regular no falla.

El LLM se reserva para redactar la explicacion final, que es donde aporta.
"""
from __future__ import annotations

import re
from typing import Any

# "2000x800x600", "2000 x 800 x 600 mm", "2000X800X600"
_DIMENSIONES = re.compile(
    r"(\d{2,5})\s*[x×]\s*(\d{2,5})\s*[x×]\s*(\d{2,5})", re.IGNORECASE
)

# "1200 W", "1200W", "1.2 kW", "1200 vatios"
_POTENCIA = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kw|w|vatios|watts?)\b", re.IGNORECASE
)

# Temperaturas. Se aceptan los dos ordenes ("ambiente 35 °C" y "35 °C de
# ambiente") con dos patrones separados, probando primero el de palabra clave
# delante, que es el menos ambiguo.
#
# El hueco entre palabra y numero no puede contener coma ni digito: sin esa
# restriccion, "ambiente 35 °C, interior 40 °C" asigna 35 al interior, porque
# el 35 esta pegado a la palabra "interior" al otro lado de la coma.
_HUECO = r"[^,;.\d]{0,20}?"
_UNIDAD_TEMP = r"\s*(?:°|º)?\s*(?:c|grados?)?"

_PALABRAS_AMBIENTE = r"(?:ambiente|exterior|entorno|afuera|fuera)"
_PALABRAS_INTERIOR = r"(?:interior|dentro|interno|objetivo|mantener|no pase de)"

_AMBIENTE_KW = re.compile(rf"{_PALABRAS_AMBIENTE}{_HUECO}\b(-?\d{{1,2}})\b", re.IGNORECASE)
_AMBIENTE_NUM = re.compile(
    rf"\b(-?\d{{1,2}})\b{_UNIDAD_TEMP}{_HUECO}{_PALABRAS_AMBIENTE}", re.IGNORECASE
)
_INTERIOR_KW = re.compile(rf"{_PALABRAS_INTERIOR}{_HUECO}\b(-?\d{{1,2}})\b", re.IGNORECASE)
_INTERIOR_NUM = re.compile(
    rf"\b(-?\d{{1,2}})\b{_UNIDAD_TEMP}{_HUECO}{_PALABRAS_INTERIOR}", re.IGNORECASE
)


def _temperatura(mensaje: str, patron_kw: re.Pattern, patron_num: re.Pattern) -> float | None:
    """Prueba primero 'palabra clave + numero', que es el orden menos ambiguo."""
    for patron in (patron_kw, patron_num):
        if m := patron.search(mensaje):
            return float(m.group(1))
    return None


def extraer_parametros(mensaje: str, caso: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Actualiza `caso` con lo que aparezca en el mensaje.

    Nunca sobreescribe un valor ya conocido: si el usuario ya dio la
    disipacion, un numero suelto posterior no la pisa. Devuelve el caso
    actualizado y las trazas de lo que se extrajo.
    """
    caso = dict(caso)
    trazas: list[str] = []

    if dim := _DIMENSIONES.search(mensaje):
        if caso.get("alto_mm") is None:
            alto, ancho, fondo = (float(g) for g in dim.groups())
            caso["alto_mm"], caso["ancho_mm"], caso["fondo_mm"] = alto, ancho, fondo
            trazas.append(f"extraido: dimensiones {alto:.0f}x{ancho:.0f}x{fondo:.0f} mm")

    if caso.get("disipacion_w") is None:
        for m in _POTENCIA.finditer(mensaje):
            valor = float(m.group(1).replace(",", "."))
            unidad = m.group(2).lower()
            if unidad == "kw":
                valor *= 1000
            # Ignora capacidades de equipo mencionadas de pasada, no la carga.
            caso["disipacion_w"] = valor
            trazas.append(f"extraido: disipacion {valor:.0f} W")
            break

    if caso.get("t_ambiente_c") is None:
        if (valor := _temperatura(mensaje, _AMBIENTE_KW, _AMBIENTE_NUM)) is not None:
            caso["t_ambiente_c"] = valor
            trazas.append(f"extraido: temperatura ambiente {valor:.0f} °C")

    if caso.get("t_interior_objetivo_c") is None:
        if (valor := _temperatura(mensaje, _INTERIOR_KW, _INTERIOR_NUM)) is not None:
            caso["t_interior_objetivo_c"] = valor
            trazas.append(f"extraido: temperatura interior objetivo {valor:.0f} °C")

    if re.search(r"polvo|sucio|contaminad|aceite|humedad|lavado", mensaje, re.IGNORECASE):
        if caso.get("entorno") is None:
            caso["entorno"] = "industrial con contaminacion ambiental"
            trazas.append("extraido: entorno contaminado (afecta la elección de filtro)")

    return caso, trazas
