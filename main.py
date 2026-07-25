"""Chat por consola contra el copiloto. Util para probar sin levantar la UI.

    python main.py                 chat normal
    python main.py --trazas        muestra que herramientas llamo y con que
                                   argumentos, para auditar la respuesta

Comandos dentro del chat:

    /fuente <consulta>   busca en el corpus y muestra el texto crudo con su
                         pagina, para contrastar una cita a mano
    /trazas              alterna la vista de trazas
    salir                terminar

Usa el mismo backend que la interfaz (src/api.responder), asi que lo que se ve
aqui es exactamente lo que vera la demo.
"""
from __future__ import annotations

import sys

from src.config import describir_llm, get_settings
from src.rag.embeddings import describir_motor
from src.rag.vectorstore import existe_indice

BIENVENIDA = """\
Copiloto Pfannenberg — chat de consola
LLM:         {llm}
Embeddings:  {emb}
Vectorial:   {vec}

Escribe tu consulta, o 'salir' para terminar.
Ejemplo: gabinete 2000x800x600 mm, 1200 W, ambiente 35 grados, objetivo 40 dentro
"""


def _mostrar_fuente(consulta: str) -> None:
    """Texto crudo del corpus para contrastar una cita a mano."""
    from src.rag.hibrido import buscar

    fragmentos = buscar(consulta, k=4)
    if not fragmentos:
        print("  sin resultados")
        return
    for f in fragmentos:
        print(f"\n  ── {f.cita()}  [{f.tipo}]")
        for linea in f.texto[:600].splitlines():
            print(f"     {linea}")


def main() -> None:
    from src.api import responder

    print(
        BIENVENIDA.format(
            llm=describir_llm(),
            emb=describir_motor(),
            vec="índice listo" if existe_indice() else "sin índice (solo BM25)",
        )
    )
    if not get_settings().hay_llm:
        print(
            "⚠️  Sin API key: modo determinístico. Responde el flujo de "
            "dimensionamiento, pero no razona ni acepta preguntas abiertas.\n"
            "   Consigue una clave gratuita en https://console.groq.com/keys\n"
        )

    ver_trazas = "--trazas" in sys.argv
    print(f"Trazas: {'activadas' if ver_trazas else 'desactivadas (--trazas o /trazas)'}")
    print("Comando: /fuente <consulta> para ver el texto crudo del corpus\n")

    sesion: dict = {}
    while True:
        try:
            mensaje = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not mensaje:
            continue
        if mensaje.lower() in {"salir", "exit", "quit"}:
            return
        if mensaje.lower() == "/trazas":
            ver_trazas = not ver_trazas
            print(f"  trazas {'activadas' if ver_trazas else 'desactivadas'}")
            continue
        if mensaje.lower().startswith("/fuente"):
            _mostrar_fuente(mensaje[7:].strip())
            continue

        try:
            r = responder(mensaje, sesion)
        except Exception as exc:  # la demo no debe morir por un fallo de red
            print(f"\n[error] {type(exc).__name__}: {exc}", file=sys.stderr)
            continue

        print(f"\n{r['mensaje']}")
        for p in r["preguntas_pendientes"]:
            print(f"  · {p}")
        if r["supuestos"]:
            print("\nSupuestos:")
            for s in r["supuestos"]:
                print(f"  - {s}")
        if r["fuentes"]:
            citas = ", ".join(f.get("cita", "") for f in r["fuentes"])
            print(f"\nFuentes: {citas}")
        if ver_trazas and r["trazas"]:
            print("\nTrazas (qué hizo el agente):")
            for t in r["trazas"]:
                print(f"  · {t}")


if __name__ == "__main__":
    main()
