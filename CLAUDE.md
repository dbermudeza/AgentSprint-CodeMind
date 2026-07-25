# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project — Pfannenberg Copilot

AgentSprint-CodeMind ("Agente Pfannenberg") es un proyecto de agente en Python en etapa temprana,
construido para el hackathon AgentSprint Medellín 2026. Todavía no hay código de aplicación — solo
un manifiesto de dependencias (`requirements.txt`) y scaffolding de entorno (`.venv`, `.env`,
`.gitignore`).

La demo debe optimizarse para **una sola historia de valor**: ayudar a ventas/soporte a resolver un
caso real de selección térmica de gabinete en minutos, con preguntas mínimas, recomendación
justificada y fuentes trazables.

## Objetivo y alcance del MVP

Construir un copiloto técnico-comercial interno para ventas/soporte de Pfannenberg que, en una sola
ruta de demo (dimensionamiento térmico de gabinete):

1. Haga intake guiado del caso (3–5 preguntas máximo si faltan datos).
2. Recupere contexto desde documentación pública oficial de Pfannenberg (RAG focalizado, no
   generalista).
3. Calcule/valide la capacidad térmica requerida y filtre opciones candidatas.
4. Entregue una recomendación principal + una alternativa razonable, explicando por qué encaja,
   qué supuestos se usaron, qué opciones se descartaron y por qué, y qué fuente respalda cada
   decisión.
5. Se muestre en una UI simple (panel o Streamlit) enfocada en una conversación y un resultado.

**No intentar en esta demo:**

- Cobertura de múltiples líneas de producto.
- RAG generalista para toda la documentación.
- Memoria larga entre sesiones (solo memoria de la sesión/caso actual).
- Automatización completa de cotización o CRM.

**Criterio de éxito (además de lo anterior):** el flujo completo debe poder mostrarse en menos de 3
minutos y debe sentirse "útil para ventas/soporte", no solo "correcto técnicamente".

## Reglas del proyecto (invariantes — no negociables)

- Usar solo fuentes públicas oficiales de Pfannenberg.
- No inventar especificaciones, compatibilidades ni fórmulas.
- Cada respuesta técnica debe citar la fuente exacta cuando exista.
- Si falta un dato crítico, preguntar antes de recomendar; nunca asumirlo silenciosamente.
- Si no hay evidencia suficiente, responder con incertidumbre explícita y los datos que faltan.
- Priorizar una solución end-to-end simple sobre una arquitectura ambiciosa pero incompleta.

## Arquitectura objetivo

Componentes del pipeline (mapean 1:1 con el flujo intake → cálculo → comparación → explicación
descrito arriba):

- **Orquestador**: clasifica el caso, detecta datos faltantes y decide si preguntar, calcular o
  buscar.
- **Intake guiado**: recopila los parámetros mínimos del gabinete y del ambiente.
- **RAG focalizado**: busca solo en una base pequeña de PDFs/documentos oficiales relevantes.
- **Motor de cálculo**: estima la necesidad térmica y compara contra opciones candidatas.
- **Explicador**: arma la respuesta final con recomendación, alternativa, fuentes y supuestos.
- **Memoria de sesión**: guarda los datos del caso actual durante la conversación (no persistente).

## Stack

Stack recomendado para la demo: frontend Streamlit, backend Python, un LLM de bajo costo y baja
latencia, RAG sobre un corpus pequeño de PDFs oficiales, y trazas claras de decisiones para
observabilidad.

⚠️ **Decisión pendiente:** `requirements.txt` actualmente pinea un stack basado en
LangChain/OpenAI, pero el LLM objetivo parece ser Gemini. Resolver esto **antes** de escribir
código de orquestación:

- `langchain` / `langchain-community` / `langchain-openai` — LLM orchestration (revisar si se
  reemplaza por el paquete de Gemini, p. ej. `langchain-google-genai`)
- `langgraph` — agent/graph orchestration sobre LangChain
- `pydantic` — validación de datos/schemas
- `python-dotenv` — carga config desde `.env`
- `ddgs` — búsqueda DuckDuckGo (probablemente como tool del agente)

Para una demo de 2.5 horas, preferir una implementación sencilla sobre una arquitectura "perfecta":
una sola ruta de grafo, una base documental pequeña y una interfaz clara.

## Plan de trabajo

1. Leer este archivo y las notas del hackathon.
2. Confirmar el caso principal de demo con un ejemplo realista de gabinete.
3. Resolver la decisión de stack (LangChain/OpenAI vs Gemini) antes de codear.
4. Elegir una familia de producto y el conjunto mínimo de documentos oficiales para el RAG.
5. Diseñar las preguntas mínimas que desbloquean el cálculo.
6. Construir el flujo crítico: intake → cálculo → comparación → explicación.
7. Levantar la UI mínima (una sola pantalla) para contar la historia.
8. Mejoras cosméticas al final, no antes.
9. Validar cada paso con algo ejecutable.

## Environment setup

```bash
python -m venv .venv
source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

PowerShell (Windows):

```powershell
.venv\Scripts\Activate.ps1
```

Secrets/config (p. ej. `OPENAI_API_KEY` o el equivalente para Gemini) van en `.env`, cargados vía
`python-dotenv`. `.env` y `.venv` están en `.gitignore` y nunca deben commitearse.