# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project — Pfannenberg Copilot

AgentSprint-CodeMind ("Agente Pfanneberg") is an early-stage Python agent project built for the
AgentSprint Medellín 2026 hackathon. There is no application source code yet — only a dependency
manifest (`requirements.txt`) and environment scaffolding (`.venv`, `.env`, `.gitignore`).

### Objetivo

Construir un asistente técnico-comercial interno para el equipo de ventas/soporte de Pfannenberg que:

1. Responda preguntas técnicas con grounding en documentación pública oficial.
2. Dimensione y recomiende productos según datos del caso.
3. Muestre siempre por qué la recomendación encaja, con fuentes trazables.

### Alcance del MVP

- Chat interno tipo dashboard.
- Respuesta técnica con RAG sobre manuales, fichas técnicas, repuestos y documentación pública.
- Calculadora o flujo de dimensionamiento térmico para recomendar el equipo adecuado.
- Panel de resultados con producto sugerido, argumentos técnicos y enlaces/fuentes.

### Reglas del proyecto

- Usar solo fuentes públicas oficiales de Pfannenberg.
- No inventar especificaciones, compatibilidades ni fórmulas.
- Cada respuesta técnica debe citar fuente exacta cuando exista.
- Si falta un dato, pedirlo antes de recomendar.
- Priorizar una solución que funcione end to end sobre una solución más grande pero incompleta.

### Arquitectura objetivo

- Agente orquestador: interpreta la solicitud del usuario.
- Herramienta RAG: busca en PDFs, manuales, fichas técnicas y catálogos públicos.
- Herramienta de cálculo: calcula o valida el dimensionamiento térmico.
- Memoria de sesión: guarda parámetros del caso actual y recomendaciones previas dentro de la
  conversación.

### Criterios de éxito

- La demo debe resolver al menos un caso real de selección de producto.
- El agente debe justificar la recomendación con datos técnicos y fuente.
- La interfaz debe permitir preguntar en lenguaje natural y ver el resultado en una sola pantalla.
- El flujo debe ser presentable en menos de 3 minutos.

### Flujo de trabajo

1. Leer primero las notas del hackathon y este archivo.
2. Identificar la pregunta concreta del usuario o el siguiente entregable.
3. Mantener el alcance pequeño: una ruta principal bien resuelta.
4. Implementar primero el flujo crítico, luego la UI y luego mejoras.
5. Validar cada paso con algo ejecutable.

### Primeras tareas sugeridas

1. Definir el caso principal: dimensionamiento térmico de gabinete.
2. Elegir la estructura del proyecto.
3. Recolectar fuentes públicas oficiales de Pfannenberg.
4. Construir el esqueleto del agente y la interfaz.

## Stack

Stack recomendado para el MVP: frontend Streamlit, backend Python, LLM Gemini (o el modelo
disponible con mejor costo/rapidez), RAG sobre PDFs oficiales con un índice simple, y trazas
claras de herramientas/decisiones para observabilidad.

`requirements.txt` actualmente pinea un stack basado en LangChain/OpenAI en vez de Gemini —
revisar y ajustar antes de escribir código:

- `langchain` / `langchain-community` / `langchain-openai` — LLM orchestration
- `langgraph` — agent/graph orchestration on top of LangChain
- `pydantic` — data validation/schemas
- `python-dotenv` — loads config from `.env`
- `ddgs` — DuckDuckGo search (likely used as an agent tool)

## Environment setup

```bash
python -m venv .venv
.venv\Scripts\activate        # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Secrets/config (e.g. `OPENAI_API_KEY`) belong in `.env`, loaded via `python-dotenv`. `.env` and
`.venv` are gitignored and must never be committed.
