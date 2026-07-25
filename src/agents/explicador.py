"""Construccion de la respuesta final: recomendacion, alternativa y por que.

La estructura se arma de forma deterministica a partir de datos verificables
(catalogo + estimacion), y el LLM solo redacta el parrafo de cierre si hay
API key. Asi ninguna cifra ni referencia depende de que el modelo no alucine:
lo que el LLM aporta es tono, no contenido tecnico.

Cada afirmacion tecnica arrastra su fuente (archivo + pagina), que es el
invariante de trazabilidad de CLAUDE.md.
"""
from __future__ import annotations

from typing import Any

from src.contracts import Producto, Recomendacion
from src.tools.catalogo import capacidad_legible
from src.tools.dimensionar import Dimensionamiento


def _fuente_de(p: Producto) -> list[dict[str, Any]]:
    return [{"fuente": p.fuente, "pagina": p.pagina, "cita": p.cita()}]


def construir_recomendacion(
    p: Producto, dim: Dimensionamiento, es_principal: bool
) -> Recomendacion:
    capacidad = capacidad_legible(p, dim.delta_t_k)
    margen = (p.capacidad_valor or 0) * (dim.delta_t_k if p.capacidad_unidad == "W/K" else 1)
    holgura = margen - dim.rango_max_w

    if es_principal:
        porque = (
            f"Cubre los {dim.rango_max_w:.0f} W requeridos con {holgura:.0f} W de holgura, "
            f"que es el ajuste más ceñido del catálogo para esta carga. "
            "Sobredimensionar encarece el equipo y hace ciclar el compresor sin necesidad."
        )
    else:
        porque = (
            f"Alternativa con más margen ({holgura:.0f} W de holgura). "
            "Conviene si se prevé ampliar la carga del gabinete o si la temperatura "
            "ambiente puede superar la indicada."
        )

    if p.confianza != "alta":
        porque += (
            " ⚠️ La atribución de esta especificación en la tabla de origen es ambigua; "
            "verifíquela contra la ficha técnica antes de cotizar."
        )

    return Recomendacion(
        modelo=p.modelo,
        capacidad=capacidad,
        porque=porque,
        articulo=p.articulo,
        fuentes=_fuente_de(p),
    )


def redactar_mensaje(
    dim: Dimensionamiento,
    principal: Recomendacion | None,
    alternativa: Recomendacion | None,
    descartes: list[str],
    caso: dict[str, Any],
) -> str:
    """Narrativa de la respuesta. Deterministica: sin cifras inventadas."""
    partes: list[str] = []

    partes.append(
        f"Para un gabinete de {caso['alto_mm']:.0f}×{caso['ancho_mm']:.0f}×{caso['fondo_mm']:.0f} mm "
        f"que disipa {caso['disipacion_w']:.0f} W, con {caso['t_ambiente_c']:.0f} °C de ambiente y "
        f"un objetivo de {caso['t_interior_objetivo_c']:.0f} °C en el interior:"
    )

    partes.append(
        f"**Carga a extraer: {dim.rango_legible}.** "
        f"El gabinete disipa por sus paredes {dim.disipacion_pasiva_w:+.0f} W "
        f"(superficie efectiva {dim.superficie_efectiva_m2:.2f} m², ΔT de {dim.delta_t_k:+.0f} K), "
        f"así que la carga neta parte de {dim.carga_neta_w:.0f} W."
    )

    partes.append(f"**Tecnología: {dim.tecnologia}.** {dim.motivo}")

    if principal:
        partes.append(
            f"**Recomendación: {principal.modelo}** ({principal.capacidad}). {principal.porque} "
            f"Fuente: {principal.fuentes[0]['cita']}."
        )
    else:
        partes.append(
            "⚠️ Ningún equipo del catálogo disponible cubre esta carga con un solo módulo. "
            "Habría que evaluar varias unidades en paralelo o un chiller, y confirmarlo con "
            "el Pfannenberg Sizing Software."
        )

    if alternativa:
        partes.append(
            f"**Alternativa: {alternativa.modelo}** ({alternativa.capacidad}). {alternativa.porque}"
        )

    if descartes:
        partes.append("**Descartados:** " + "; ".join(descartes[:4]) + ".")

    if caso.get("entorno"):
        partes.append(
            "Como el entorno tiene contaminación ambiental, conviene revisar el tipo de filtro "
            "y el grado de protección IP en la ficha del equipo antes de cerrar la selección."
        )

    return "\n\n".join(partes)
