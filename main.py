"""Chat por consola contra el copiloto. Util para probar sin levantar la UI.

    python main.py

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


if __name__ == "__main__":
    main()
