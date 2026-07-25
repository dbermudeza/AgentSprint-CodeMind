"""Carga y filtrado del catalogo de producto.

Prefiere `data/processed/productos.json` (CONTRATO 2, lo genera la maquina A).
Mientras no exista, cae a un fixture propio con productos reales verificados
contra el corpus, para no bloquear el desarrollo del agente. El fallback avisa
por traza: nunca debe pasar inadvertido en la demo.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.contracts import Producto

RAIZ = Path(__file__).resolve().parent.parent.parent
CATALOGO_REAL = RAIZ / "data" / "processed" / "productos.json"
CATALOGO_FIXTURE = RAIZ / "src" / "fixtures" / "productos_fixture.json"


def cargar_catalogo() -> tuple[list[Producto], str]:
    """Devuelve (productos, origen). `origen` es "real" o "fixture"."""
    ruta, origen = (
        (CATALOGO_REAL, "real") if CATALOGO_REAL.exists() else (CATALOGO_FIXTURE, "fixture")
    )
    with ruta.open(encoding="utf-8") as f:
        crudo = json.load(f)
    productos = [Producto(**item) for item in crudo]
    return productos, origen


def filtrar_candidatos(
    productos: list[Producto],
    tecnologia: str,
    carga_min_w: float,
    carga_max_w: float,
    delta_t_k: float,
) -> tuple[list[Producto], list[str]]:
    """Filtra por tecnologia y capacidad suficiente.

    Devuelve (candidatos ordenados por ajuste, motivos de descarte). Los
    descartes se conservan porque la respuesta debe explicar que se descarto
    y por que, no solo que se recomienda.

    Ordena por capacidad ascendente: el equipo mas pequeno que cubre la carga
    es el de menor consumo y coste, y sobredimensionar tiene su propio coste
    (ciclado del compresor, precio).
    """
    descartes: list[str] = []
    candidatos: list[Producto] = []

    for p in productos:
        if p.tipo != tecnologia:
            continue
        if p.capacidad_valor is None:
            descartes.append(f"{p.modelo}: sin capacidad publicada en la fuente")
            continue

        # Los aire/aire se especifican en W/K: su capacidad util depende del
        # salto termico disponible. Los activos ya vienen en W.
        if p.capacidad_unidad == "W/K":
            if delta_t_k <= 0:
                descartes.append(f"{p.modelo}: sin ΔT favorable, el intercambio no opera")
                continue
            capacidad_util_w = p.capacidad_valor * delta_t_k
        else:
            capacidad_util_w = p.capacidad_valor

        if capacidad_util_w < carga_max_w:
            descartes.append(
                f"{p.modelo}: {capacidad_util_w:.0f} W útiles, insuficiente "
                f"para los {carga_max_w:.0f} W requeridos"
            )
            continue

        candidatos.append(p)

    candidatos.sort(key=lambda p: p.capacidad_valor or 0)
    return candidatos, descartes


def capacidad_legible(p: Producto, delta_t_k: float) -> str:
    """Capacidad para mostrar, explicitando la conversion en los aire/aire."""
    if p.capacidad_unidad == "W/K" and delta_t_k > 0:
        util = (p.capacidad_valor or 0) * delta_t_k
        return f"{p.capacidad_valor:.0f} W/K (≈{util:.0f} W con ΔT de {delta_t_k:.0f} K)"
    return f"{p.capacidad_valor:.0f} {p.capacidad_unidad}"
