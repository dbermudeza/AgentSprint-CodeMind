"""Herramienta de agente: buscar en la documentacion oficial de Pfannenberg.

Envuelve `src.rag.retriever.buscar` para que el orquestador la use sin conocer
el indice. La funcion devuelve los `Fragmento` del contrato (no texto plano):
quien construye la respuesta necesita `fuente` y `pagina` para citar, y perder
esa metadata aqui haria imposible cumplir la regla de citar la fuente exacta.

`formatear_contexto` es el helper para armar el prompt: antepone la cita a cada
fragmento, de modo que el LLM vea de que pagina viene cada dato y pueda
atribuirlo en su respuesta.
"""
from __future__ import annotations

from src.contracts import Fragmento
from src.rag.retriever import buscar as _buscar

# Tope defensivo: pedir 50 fragmentos no mejora la respuesta, solo diluye el
# prompt y encarece el turno.
MAX_FRAGMENTOS = 12


def buscar_documentacion(
    consulta: str, k: int = 6, solo_tablas: bool = False
) -> list[Fragmento]:
    """Recupera fragmentos citables del corpus oficial.

    Args:
        consulta: pregunta o terminos en lenguaje natural. Incluir el codigo de
            modelo si se conoce ("capacidad DTS 3061"): BM25 lo trata como el
            token discriminante y es lo que evita confundir modelos vecinos.
        k: cuantos fragmentos devolver (tope `MAX_FRAGMENTOS`).
        solo_tablas: restringe a tablas, donde viven las especificaciones. Usar
            True para specs por modelo; False para argumentar aplicacion.

    Returns:
        Lista de `Fragmento` ordenada por relevancia. Vacia si nada puntua, lo
        que significa "el corpus no lo respalda": hay que decirlo, no rellenar.
    """
    return _buscar(consulta, k=min(k, MAX_FRAGMENTOS), solo_tablas=solo_tablas)


def formatear_contexto(fragmentos: list[Fragmento]) -> str:
    """Serializa fragmentos para inyectarlos en un prompt, con su cita delante."""
    if not fragmentos:
        return "(sin resultados en la documentacion oficial)"
    return "\n\n".join(f"[{f.cita()}]\n{f.texto}" for f in fragmentos)
