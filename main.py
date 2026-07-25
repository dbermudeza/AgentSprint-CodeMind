from langchain_core.messages import HumanMessage

from src.graph import grafo


def main() -> None:
    """Bucle de conversación por consola con el agente."""
    print("Agente listo. Escribe 'salir' para terminar.\n")
    historial: list = []
    while True:
        entrada = input("Tú: ")
        if entrada.strip().lower() == "salir":
            break
        historial.append(HumanMessage(content=entrada))
        resultado = grafo.invoke({"messages": historial})
        historial = resultado["messages"]
        print(f"Agente: {historial[-1].content}\n")


if __name__ == "__main__":
    main()
