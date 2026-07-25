# AgentSprint-CodeMind
Copiloto técnico-comercial para Pfannenberg.

## Qué corre hoy

La demo actual es una app de Streamlit de una sola pantalla. La UI vive en [app.py](app.py) y usa un backend mock en [demo/mock_backend.py](demo/mock_backend.py) hasta que el equipo entregue `src/api.py`.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

Si quieres abrir la demo localmente en una sesión headless, usa el puerto 8501 que levanta Streamlit por defecto.

## Guion de demo de 3 minutos

1. Abre la app y señala que la pantalla está dividida en chat a la izquierda y resultados a la derecha.
2. Haz clic en **Cargar caso de ejemplo** para precargar el gabinete de 2000 × 800 × 600 mm, 1200 W, ambiente 35 °C y objetivo 40 °C.
3. En el panel derecho muestra **Caso actual**, luego **Recomendación** y destaca el artículo 12982411055 como referencia comprable.
4. Señala **Supuestos** para dejar claro que la estimación es propia y que el cálculo certificado va al Pfannenberg Sizing Software.
5. Abre **Ver trazas** y termina mostrando las fuentes citadas en formato simple: Thermal_Management_EN_V4.pdf, p.45.

## Nota de integración

Cuando `src/api.py` esté listo, cambia solo la línea de import en [app.py](app.py):

```python
from demo.mock_backend import responder  # TODO: -> from src.api import responder
```

El contrato del dict viene de [src/contracts.py](src/contracts.py) y la UI ya está alineada con esa forma.