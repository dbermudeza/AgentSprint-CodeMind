# AgentSprint-CodeMind
Agente Pfanneberg

## Estructura del proyecto

```

├── main.py                  # Punto de entrada: bucle de conversación por consola
├── requirements.txt         # Dependencias del proyecto
├── .env                     # Variables de entorno reales (NO se sube al repo)
├── .env.example             # Plantilla de variables de entorno
├── .gitignore
└── src/
    ├── config.py             # Configuración centralizada (lee variables de entorno)
    ├── state.py               # Definición del estado del grafo (AgentState)
    ├── graph.py                # Ensamblado del grafo de LangGraph (nodos y bordes)
    ├── agents/
    │   ├── __init__.py
    └── tools/
        ├── __init__.py         # Registro 
```

### Por qué esta separación

- **`config.py`**: un único punto de verdad para credenciales/configuración; evita
  leer `os.getenv` esparcido por el código.
- **`state.py`**: el estado (`AgentState`) es el "contrato" de datos que viaja
  entre nodos del grafo. Aislarlo facilita añadir campos (memoria, contexto de
  otros agentes, etc.) sin tocar la lógica.
- **`tools/`**: cada herramienta vive en su propio archivo y se expone en
  `all_tools`. Añadir una herramienta nueva no requiere tocar el agente.
- **`agents/`**: la lógica del nodo (qué LLM, qué prompt, qué herramientas)
  está aislada. En un sistema multi-agente, cada agente tendría su propio
  archivo aquí.
- **`graph.py`**: define cómo se conectan los nodos (agente ⇄ herramientas).
  Es el único lugar que conoce la topología del flujo.

## Librerías utilizadas

| Librería | Uso en el proyecto |
|---|---|
| [`langchain`](https://python.langchain.com/) | Framework base: mensajes, herramientas (`@tool`), abstracciones comunes |
| [`langchain-openai`](https://python.langchain.com/docs/integrations/platforms/openai/) | Integración con la API de OpenAI (`ChatOpenAI`) |
| [`langchain-community`](https://python.langchain.com/docs/integrations/platforms/) | Herramientas de la comunidad, aquí usada para `DuckDuckGoSearchRun` |
| [`langgraph`](https://langchain-ai.github.io/langgraph/) | Orquestación del agente como grafo de estados (nodos, bordes condicionales, bucles) |
| [`ddgs`](https://pypi.org/project/ddgs/) | Cliente de búsqueda en DuckDuckGo, dependencia de la herramienta `buscar_web` |
| [`pydantic`](https://docs.pydantic.dev/) | Validación y tipado de la configuración (`Settings`) |
| [`python-dotenv`](https://pypi.org/project/python-dotenv/) | Carga de variables de entorno desde `.env` |

Todas se instalan a partir de `requirements.txt`; el resto de paquetes que
aparecen si haces `pip freeze` son dependencias transitivas resueltas por pip.