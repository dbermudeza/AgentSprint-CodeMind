"""Grafo del agente: intake -> calculo -> filtrado -> explicacion.

Una sola ruta, como pide CLAUDE.md. La unica bifurcacion es si falta algun
dato critico: en ese caso se pregunta y se corta el turno, sin calcular nada
a medias (invariante: "si falta un dato critico, preguntar antes de
recomendar; nunca asumirlo silenciosamente").
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.explicador import (
    construir_recomendacion,
    elegir_alternativa,
    holgura_de,
    redactar_mensaje,
)
from src.agents.extractor import extraer_parametros
from src.state import CAMPOS_CRITICOS, AgentState, faltantes
from src.tools.catalogo import cargar_catalogo, filtrar_candidatos
from src.tools.dimensionar import dimensionar

try:  # CONTRATO 1 — lo entrega la maquina A.
    from src.rag.retriever import buscar
except ImportError:  # Stub para no bloquearse mientras A trabaja.

    def buscar(consulta: str, k: int = 6, solo_tablas: bool = False) -> list:
        return []


# --------------------------------------------------------------------------
# Nodos
# --------------------------------------------------------------------------


def nodo_extraer(state: AgentState) -> AgentState:
    caso, trazas = extraer_parametros(state["mensaje"], state.get("caso", {}))
    state["caso"] = caso
    state["trazas"] = state.get("trazas", []) + trazas
    return state


def nodo_intake(state: AgentState) -> AgentState:
    """Pregunta solo por lo que falta, maximo 3 preguntas por turno."""
    pendientes = faltantes(state["caso"])
    preguntas = [CAMPOS_CRITICOS[c] for c in pendientes][:3]

    state["preguntas_pendientes"] = preguntas
    state["trazas"] = state.get("trazas", []) + [
        f"intake: faltan {len(pendientes)} datos criticos ({', '.join(pendientes)})"
    ]

    conocidos = [k for k in CAMPOS_CRITICOS if state["caso"].get(k) is not None]
    if conocidos:
        state["respuesta"] = (
            "Ya tengo parte de los datos. Para poder dimensionar necesito además:"
        )
    else:
        state["respuesta"] = (
            "Puedo ayudarte a seleccionar la solución térmica. Necesito estos datos:"
        )
    return state


def nodo_calcular(state: AgentState) -> AgentState:
    caso = state["caso"]
    dim = dimensionar(
        disipacion_w=caso["disipacion_w"],
        t_ambiente_c=caso["t_ambiente_c"],
        t_interior_objetivo_c=caso["t_interior_objetivo_c"],
        alto_mm=caso["alto_mm"],
        ancho_mm=caso.get("ancho_mm", caso["alto_mm"]),
        fondo_mm=caso.get("fondo_mm", caso["alto_mm"]),
    )
    state["dimensionamiento"] = dim
    state["supuestos"] = dim.supuestos
    state["trazas"] = state.get("trazas", []) + dim.trazas
    return state


def nodo_filtrar(state: AgentState) -> AgentState:
    dim = state["dimensionamiento"]
    productos, origen = cargar_catalogo()
    state["origen_catalogo"] = origen

    if origen == "fixture":
        state["trazas"] = state.get("trazas", []) + [
            "⚠️ catalogo: usando fixture local, aun no hay data/processed/productos.json"
        ]

    candidatos, descartes = filtrar_candidatos(
        productos,
        tecnologia=dim.tecnologia,
        carga_min_w=dim.rango_min_w,
        carga_max_w=dim.rango_max_w,
        delta_t_k=dim.delta_t_k,
    )
    state["candidatos"] = candidatos
    state["descartes"] = descartes
    state["trazas"] = state.get("trazas", []) + [
        f"filtrado: {len(candidatos)} candidatos de tipo '{dim.tecnologia}', "
        f"{len(descartes)} descartados"
    ]
    return state


def nodo_explicar(state: AgentState) -> AgentState:
    dim = state["dimensionamiento"]
    candidatos = state["candidatos"]

    principal = alternativa = None
    if candidatos:
        principal = construir_recomendacion(candidatos[0], dim, True)
        if alt := elegir_alternativa(candidatos, candidatos[0]):
            alternativa = construir_recomendacion(
                alt, dim, False, holgura_principal=holgura_de(candidatos[0], dim)
            )

    state["recomendacion"] = principal
    state["alternativa"] = alternativa
    state["respuesta"] = redactar_mensaje(
        dim, principal, alternativa, state["descartes"], state["caso"]
    )

    fuentes: list[dict] = []
    for rec in (principal, alternativa):
        if rec:
            fuentes.extend(rec.fuentes)

    # Grounding documental adicional (CONTRATO 1). Vacio mientras A no entregue.
    for frag in buscar(f"{dim.tecnologia} capacidad de refrigeracion", k=3, solo_tablas=True):
        fuentes.append({"fuente": frag.fuente, "pagina": frag.pagina, "cita": frag.cita()})

    vistos, unicas = set(), []
    for f in fuentes:
        clave = (f["fuente"], f["pagina"])
        if clave not in vistos:
            vistos.add(clave)
            unicas.append(f)
    state["fuentes"] = unicas
    return state


# --------------------------------------------------------------------------
# Ensamblado
# --------------------------------------------------------------------------


def _decidir(state: AgentState) -> str:
    return "intake" if faltantes(state["caso"]) else "calcular"


def construir_grafo():
    g = StateGraph(AgentState)

    g.add_node("extraer", nodo_extraer)
    g.add_node("intake", nodo_intake)
    g.add_node("calcular", nodo_calcular)
    g.add_node("filtrar", nodo_filtrar)
    g.add_node("explicar", nodo_explicar)

    g.set_entry_point("extraer")
    g.add_conditional_edges(
        "extraer", _decidir, {"intake": "intake", "calcular": "calcular"}
    )
    g.add_edge("intake", END)
    g.add_edge("calcular", "filtrar")
    g.add_edge("filtrar", "explicar")
    g.add_edge("explicar", END)

    return g.compile()


GRAFO = construir_grafo()
