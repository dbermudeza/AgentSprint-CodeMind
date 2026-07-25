# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project — Pfannenberg Copilot

AgentSprint-CodeMind ("Agente Pfannenberg") es un proyecto de agente en Python en etapa temprana,
construido para el hackathon AgentSprint Medellín 2026. Todavía no hay código de aplicación, pero
el corpus documental ya está listo: 60 PDFs oficiales en `data/`, procesados a chunks con
`scripts/process_pdfs.py` (ver "Corpus de datos").

La demo debe optimizarse para **una sola historia de valor**: ayudar a ventas/soporte a resolver un
caso real de selección térmica de gabinete en minutos, con preguntas mínimas, recomendación
justificada y fuentes trazables.

## Objetivo y alcance del MVP

Construir un copiloto técnico-comercial interno para ventas/soporte de Pfannenberg que, en una sola
ruta de demo (dimensionamiento térmico de gabinete):

1. Haga intake guiado del caso (3–5 preguntas máximo si faltan datos).
2. Recupere contexto desde documentación pública oficial de Pfannenberg (RAG focalizado, no
   generalista).
3. Estime el rango de capacidad térmica requerida y filtre opciones candidatas contra las
   especificaciones reales del catálogo. ⚠️ Ver "Restricción sobre el cálculo térmico": el corpus
   no publica la fórmula de dimensionamiento, así que el cálculo se presenta como estimación con
   supuestos explícitos, no como resultado certificado.
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

## Corpus de datos

60 PDFs oficiales de Pfannenberg en `data/` (catálogos, brochures, flyers sectoriales, case
studies, whitepapers). Se procesan con:

```bash
python scripts/process_pdfs.py    # data/*.pdf -> data/processed/chunks.jsonl
```

El script extrae **tablas y prosa por separado**: las tablas se serializan a Markdown conservando
la fila de cabecera, porque un extractor plano aplasta las columnas y deja valores sin dueño
(`Power consumption 50 | 56 310 | 420 W` para tres modelos distintos). Cada chunk lleva `source`,
`page` y `type` (`table` | `text`) — `source` + `page` es lo que permite cumplir la regla de citar
la fuente exacta. Los chunks duplicados se descartan por hash.

Al añadir PDFs nuevos a `data/`, volver a correr el script (reescribe el `.jsonl` completo).

### Qué respalda el corpus

- Especificaciones por modelo en tablas resumen: `PAS 6043 | 20 W/K | 230 V | 618 x 380 x 212 mm`.
- Números de artículo para cerrar hacia una referencia comprable (`12981111055`).
- Familias: DTS/DTI/DTT (refrigeración), PAS (aire/aire), PWS (aire/agua), chillers, señalización.

### Restricción sobre el cálculo térmico

**El corpus no contiene la fórmula de dimensionamiento térmico.** No hay k-factor, superficie
efectiva de gabinete ni W/m²K. Los documentos delegan el cálculo al **Pfannenberg Sizing Software
(PSS)** — hay ~230 menciones; textual de `Thermal_Management_EN_V4.pdf` p52: *"Pfannenberg Sizing
Software determines your cooling requirements, calculates the necessary cooling capacity"*.

Consecuencia para el agente, dado el invariante "no inventar fórmulas":

- Puede recoger los parámetros del caso, estimar un rango de capacidad y **filtrar productos reales
  por sus specs citadas** — ahí es donde está el valor demostrable.
- Debe marcar la estimación como supuesto propio y **derivar al PSS** para el dimensionamiento
  certificado. No presentar el cálculo como respaldado por la documentación oficial.

### Zonas de baja confianza

- **Fichas multi-columna**: algunas filas tienen más valores que modelos (variantes 50/60 Hz,
  celdas combinadas). Si la alineación es ambigua, preguntar o citar el rango — no adivinar.
- **`Pfannenberg_Cut-out_compatibility_list...pdf`**: matriz de compatibilidad que se extrae como
  ruido ilegible, además de ser versión 1.3 de 2017. **No usar para afirmar compatibilidades**
  (choca directo con el invariante correspondiente).
- **Case studies y flyers** (~28% del corpus) son material de marketing: sirven para argumentar
  aplicación, no para specs.
- No hay manuales de operación ni listas de repuestos reales, pese a que el alcance los menciona.

## Arquitectura objetivo

Componentes del pipeline (mapean 1:1 con el flujo intake → cálculo → comparación → explicación
descrito arriba):

- **Orquestador**: clasifica el caso, detecta datos faltantes y decide si preguntar, calcular o
  buscar.
- **Intake guiado**: recopila los parámetros mínimos del gabinete y del ambiente.
- **RAG focalizado**: busca solo en una base pequeña de PDFs/documentos oficiales relevantes.
- **Motor de cálculo**: estima la necesidad térmica y compara contra opciones candidatas. La
  fórmula usada debe estar declarada en código como supuesto propio, nunca atribuida a Pfannenberg.
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
- `pdfplumber` — extracción de PDFs preservando tablas (usado por `scripts/process_pdfs.py`)
- `pypdf` — dependencia de lectura de PDF

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