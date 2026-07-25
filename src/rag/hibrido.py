"""Recuperacion hibrida: BM25 lexico + Chroma vectorial, fusionados con RRF.

Por que las dos y no solo la vectorial:

- La semantica sola falla con los codigos de modelo. "DTS 3031" y "DTS 3161"
  son casi el mismo vector, pero uno refrigera 694 W y el otro 1235 W. Ese
  error es invisible: devuelve resultados, solo que los del modelo equivocado.
- La lexica sola falla con las preguntas conceptuales. "¿que sirve para una
  planta de alimentos con lavado a presion?" no comparte ningun token con la
  ficha que lo responde.

Fusion por Reciprocal Rank Fusion (RRF): cada fragmento suma 1/(K + puesto) en
cada lista donde aparece. Se combinan puestos, no puntuaciones, porque las
escalas de BM25 y de similitud coseno no son comparables entre si. Lo que
aparece alto en ambas listas gana; lo que solo destaca en una sigue estando.
"""
from __future__ import annotations

from src.contracts import Fragmento
from src.rag.retriever import buscar as buscar_lexico
from src.rag.vectorstore import buscar_vectorial

# Constante estandar de RRF. Amortigua el peso de los primeros puestos para que
# un unico primer lugar no arrase con el consenso del resto.
K_RRF = 60


def _clave(f: Fragmento) -> tuple[str, int, int]:
    return (f.fuente, f.pagina, hash(f.texto[:120]))


def buscar(
    consulta: str, k: int = 6, solo_tablas: bool = False
) -> list[Fragmento]:
    """CONTRATO 1, ahora hibrido. Drop-in del retriever lexico.

    Si no hay base vectorial (falta indice o API key), degrada limpiamente a
    BM25 puro: la demo sigue funcionando sin credenciales.
    """
    # Se piden mas resultados de los necesarios a cada motor: la fusion
    # descarta, y con k justo se pierden los que solo una lista veia.
    amplitud = max(k * 2, 10)
    listas = [
        buscar_lexico(consulta, k=amplitud, solo_tablas=solo_tablas),
        buscar_vectorial(consulta, k=amplitud, solo_tablas=solo_tablas),
    ]

    puntajes: dict[tuple, float] = {}
    fragmentos: dict[tuple, Fragmento] = {}

    for lista in listas:
        for puesto, frag in enumerate(lista):
            clave = _clave(frag)
            puntajes[clave] = puntajes.get(clave, 0.0) + 1.0 / (K_RRF + puesto + 1)
            fragmentos.setdefault(clave, frag)

    ordenadas = sorted(puntajes.items(), key=lambda kv: kv[1], reverse=True)

    salida: list[Fragmento] = []
    for clave, puntaje in ordenadas[:k]:
        frag = fragmentos[clave]
        salida.append(
            Fragmento(
                texto=frag.texto,
                fuente=frag.fuente,
                pagina=frag.pagina,
                tipo=frag.tipo,
                score=puntaje,
            )
        )
    return salida


def diagnostico(consulta: str, k: int = 5) -> str:
    """Compara lo que aporta cada motor. Util para justificar la arquitectura."""
    lex = buscar_lexico(consulta, k=k)
    vec = buscar_vectorial(consulta, k=k)
    hib = buscar(consulta, k=k)

    lineas = [f"consulta: {consulta!r}", ""]
    for nombre, lista in (("BM25", lex), ("vectorial", vec), ("hibrido", hib)):
        lineas.append(f"[{nombre}] {len(lista)} resultados")
        for f in lista:
            lineas.append(f"   {f.cita()} ({f.tipo})")
        lineas.append("")
    return "\n".join(lineas)
