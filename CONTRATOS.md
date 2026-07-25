# Contratos e integración

Tres máquinas trabajando en paralelo sobre 2.5 h. Este archivo es el mapa: quién
posee qué archivos y cómo se conectan las capas sin bloquearse.

Las interfaces viven en **[`src/contracts.py`](src/contracts.py)** como código real,
no como convención. Impórtalas, no las redefinas.

## Reparto de archivos

Cada quien edita **solo** sus archivos. Tocar los de otro genera conflictos de merge
que en un hackathon cuestan más que la funcionalidad que aportan.

| | Capa | Archivos propios |
|---|---|---|
| **A** | Datos / RAG | `src/rag/*`, `src/tools/buscar_documentacion.py`, `scripts/build_catalog.py`, `data/processed/productos.json` |
| **B** | Lógica / Agente | `src/config.py`, `src/state.py`, `src/graph.py`, `src/agents/*`, `src/tools/dimensionar.py`, `src/api.py`, `src/tools/__init__.py`, `requirements.txt` |
| **C** | Presentación | `app.py`, `demo/*`, `README.md` |

`src/contracts.py` es de **todos y de nadie**: cambiarlo requiere avisar al equipo.

## Cómo se conectan

```
  A: rag/retriever.buscar()  ──Fragmento──►  B: graph/agents
  A: productos.json          ──Producto───►  B: filtrado de candidatos
                                             │
                                             ▼
                             B: api.responder() ──dict──► C: app.py
```

### Contrato 1 — Retriever (A implementa, B consume)

```python
from src.contracts import Fragmento

def buscar(consulta: str, k: int = 6, solo_tablas: bool = False) -> list[Fragmento]: ...
```

`solo_tablas=True` restringe a `tipo == "table"`, donde viven las specs.

### Contrato 2 — Catálogo (A genera, B consume)

`data/processed/productos.json`: lista de objetos con la forma de `Producto`.

El campo `confianza` es el importante: `"media"` significa que la fila de la tabla
tenía más valores que modelos y la atribución es ambigua. **No afirmar esa spec sin
avisar** — choca con el invariante de no inventar especificaciones.

### Contrato 3 — Backend → UI (B implementa, C consume)

```python
# src/api.py
def responder(mensaje: str, sesion: dict) -> dict:
    ...
    return Respuesta(...).to_dict()
```

Devuelve **dict, no dataclass**, a propósito: así el mock de la UI y el backend real
son intercambiables cambiando un único import. Las claves del dict están definidas
por `Respuesta.to_dict()` en `src/contracts.py`.

## Desbloqueo mutuo

Nadie espera a nadie. Si tu dependencia no ha llegado, mockéala y sigue:

- **B sin el retriever de A** → stub que devuelve dos `Fragmento` a mano.
- **B sin `productos.json`** → fixture con 3 productos reales sacados del catálogo.
- **C sin `src/api.py`** → `demo/mock_backend.py` con la forma del contrato 3.

Cuando la pieza real aterrice, se cambia el import y listo.

## Caso dorado

Las tres capas apuntan al mismo escenario, definido en `CASO_DORADO`
(`src/contracts.py`):

> Gabinete 2000 × 800 × 600 mm, disipación interna 1200 W, ambiente 35 °C,
> objetivo interior 40 °C, entorno industrial con polvo.

Nótese que el objetivo interior (40 °C) está **por encima** del ambiente (35 °C), así
que un intercambiador aire/aire es viable. Si se invierte la relación, la física
obliga a refrigeración activa — ese razonamiento es el que hace la demo convincente.

## Orden de arranque

```bash
git checkout main && git pull      # los tres, primero

git checkout -b feat/rag           # A
git checkout -b feat/agente        # B
git checkout -b feat/ui            # C
```

**Minuto 0:** B añade `streamlit` y `rank_bm25` a `requirements.txt` y pushea a
`main`. A y C hacen `pull` y arrancan. A partir de ahí, los tres son independientes.

**Última media hora — integración.** Reservarla de verdad: merge `feat/rag` →
`feat/agente`, conectar, luego `feat/ui` y C cambia su import. La integración
siempre tarda más de lo previsto.

## Si algo se derrapa

El catálogo estructurado (A) es la tarea con más riesgo, porque depende de parsear
tablas sucias. Si a la hora no hay `productos.json` usable, B sigue con su fixture de
3 productos reales y se demuestra con eso. **La demo vale más que la cobertura.**
