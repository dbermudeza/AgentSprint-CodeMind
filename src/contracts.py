"""Contratos compartidos entre las tres capas del proyecto.

Este archivo es la unica fuente de verdad de las interfaces. Se trabaja en
paralelo (datos / logica / UI), asi que cambiar una firma de aqui rompe a
alguien mas: avisar al equipo antes de tocarlo.

Reparto:
  - `Fragmento`   la produce la capa RAG (src/rag/retriever.py), la consume el agente.
  - `Recomendacion` / `Respuesta` las construye el agente (src/api.py).
  - La UI (app.py) NO importa este archivo: consume el dict que devuelve
    `Respuesta.to_dict()`, para que el mock de la UI y el backend real sean
    intercambiables cambiando un solo import.

Solo stdlib a proposito: la UI y los scripts deben poder importarlo sin
arrastrar dependencias.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# CONTRATO 1 — Capa RAG.  Implementa: maquina A.  Consume: maquina B.
# ---------------------------------------------------------------------------


@dataclass
class Fragmento:
    """Un chunk recuperado del corpus, con lo necesario para citarlo."""

    texto: str
    fuente: str  # "Thermal_Management_EN_V4.pdf"
    pagina: int  # 47
    tipo: str  # "table" | "text"
    score: float = 0.0

    def cita(self) -> str:
        """Cita legible para el usuario final."""
        return f"{self.fuente}, p.{self.pagina}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "texto": self.texto,
            "fuente": self.fuente,
            "pagina": self.pagina,
            "tipo": self.tipo,
            "cita": self.cita(),
        }


# Firma que debe exponer src/rag/retriever.py:
#
#     def buscar(consulta: str, k: int = 6, solo_tablas: bool = False) -> list[Fragmento]
#
# `solo_tablas=True` restringe a tipo == "table", donde viven las specs.


# ---------------------------------------------------------------------------
# CONTRATO 2 — Catalogo de producto.
# Genera: maquina A (scripts/build_catalog.py -> data/processed/productos.json).
# Consume: maquina B.
# ---------------------------------------------------------------------------


@dataclass
class Producto:
    modelo: str  # "PAS 6043"
    familia: str  # "PAS"
    tipo: str  # "aire/aire" | "aire/agua" | "refrigeracion activa" | "chiller"
    capacidad_valor: float | None  # 20
    capacidad_unidad: str | None  # "W/K" | "W"
    fuente: str
    pagina: int
    tension: str | None = None
    dimensiones_mm: str | None = None
    articulo: str | None = None
    # "alta"  = atribucion modelo->spec inequivoca.
    # "media" = la fila de la tabla tenia mas valores que modelos (variantes
    #           50/60 Hz, celdas combinadas). No afirmar la spec sin avisar.
    confianza: str = "alta"

    def cita(self) -> str:
        return f"{self.fuente}, p.{self.pagina}"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# CONTRATO 3 — Backend -> UI.  Implementa: maquina B.  Consume: maquina C.
# ---------------------------------------------------------------------------


@dataclass
class Recomendacion:
    modelo: str
    capacidad: str  # "65 W/K" (ya formateado para mostrar)
    porque: str  # justificacion tecnica en lenguaje natural
    articulo: str | None = None
    fuentes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "modelo": self.modelo,
            "capacidad": self.capacidad,
            "porque": self.porque,
            "articulo": self.articulo,
            "fuentes": self.fuentes,
        }


@dataclass
class Respuesta:
    """Lo que el agente devuelve tras cada turno de conversacion."""

    mensaje: str
    preguntas_pendientes: list[str] = field(default_factory=list)
    recomendacion: Recomendacion | None = None
    alternativa: Recomendacion | None = None
    # Obligatorio cuando hubo estimacion termica: CLAUDE.md prohibe presentar
    # el calculo como respaldado por documentacion oficial de Pfannenberg.
    supuestos: list[str] = field(default_factory=list)
    fuentes: list[dict[str, Any]] = field(default_factory=list)
    trazas: list[str] = field(default_factory=list)
    caso: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mensaje": self.mensaje,
            "preguntas_pendientes": self.preguntas_pendientes,
            "recomendacion": self.recomendacion.to_dict() if self.recomendacion else None,
            "alternativa": self.alternativa.to_dict() if self.alternativa else None,
            "supuestos": self.supuestos,
            "fuentes": self.fuentes,
            "trazas": self.trazas,
            "caso": self.caso,
        }


# Firma que debe exponer src/api.py.  Devuelve dict (no dataclass) a proposito:
# asi el mock de la UI y el backend real son intercambiables cambiando un import.
#
#     def responder(mensaje: str, sesion: dict) -> dict:
#         ...
#         return Respuesta(...).to_dict()


# ---------------------------------------------------------------------------
# Caso dorado de la demo. Las tres capas apuntan a este mismo escenario.
# ---------------------------------------------------------------------------

CASO_DORADO: dict[str, Any] = {
    "alto_mm": 2000,
    "ancho_mm": 800,
    "fondo_mm": 600,
    "disipacion_w": 1200,
    "t_ambiente_c": 35,
    "t_interior_objetivo_c": 40,
    "entorno": "industrial con polvo",
}
