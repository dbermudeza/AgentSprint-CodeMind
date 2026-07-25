from __future__ import annotations

from copy import deepcopy

import streamlit as st

from src.api import responder
from src.config import describir_llm
from src.contracts import CASO_DORADO
from src.rag.embeddings import describir_motor
from src.rag.vectorstore import existe_indice


st.set_page_config(
    page_title="Pfannenberg Copilot",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Todo color de texto se declara explicitamente. La version anterior fijaba un
# fondo claro pero dejaba que el color de letra lo heredara del tema del
# sistema: en modo oscuro salia texto blanco sobre fondo claro, ilegible.
st.markdown(
    """
<style>
    :root {
        --tinta: #16233A;
        --tinta-suave: #4A5872;
        --azul: #0B5FA5;
        --borde: #DCE3ED;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, rgba(11, 95, 165, 0.07), transparent 30%),
            radial-gradient(circle at top right, rgba(255, 184, 0, 0.08), transparent 26%),
            linear-gradient(180deg, #F7F9FC 0%, #EDF2F8 100%);
    }
    .block-container { padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1400px; }

    /* Contraste explícito en todo lo que pinta texto. */
    [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"],
    .stMarkdown, p, li, span, label, h1, h2, h3, h4 { color: var(--tinta); }

    h1 { font-weight: 700; letter-spacing: -0.02em; }
    h3 { color: var(--azul) !important; font-weight: 650; }

    [data-testid="stCaptionContainer"], .muted {
        color: var(--tinta-suave) !important;
        font-size: 0.92rem;
    }

    /* Tarjetas: st.container(border=True) en vez de <div> sueltos, que
       Streamlit no aplicaba porque cada widget va en su propio contenedor. */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF;
        border: 1px solid var(--borde);
        border-radius: 16px;
        box-shadow: 0 6px 24px rgba(18, 32, 64, 0.05);
    }

    [data-testid="stMetricValue"] { color: var(--azul); font-weight: 700; }
    [data-testid="stMetricLabel"] { color: var(--tinta-suave); }

    /* Chat: el rol se distingue por color de fondo, con texto siempre oscuro. */
    [data-testid="stChatMessage"] {
        background: #F4F7FB;
        border: 1px solid var(--borde);
        border-radius: 12px;
        color: var(--tinta);
    }

    .stButton > button {
        background: var(--azul); color: #FFFFFF; border: 0;
        border-radius: 10px; font-weight: 600; padding: 0.55rem 1rem;
    }
    .stButton > button:hover { background: #094B84; color: #FFFFFF; }

    /* Avisos: Streamlit los tiñe de amarillo claro; forzamos letra oscura. */
    [data-testid="stAlert"] { border-radius: 12px; }
    [data-testid="stAlert"] * { color: #4A3A08 !important; }
    [data-testid="stAlertContentInfo"] * { color: #0B3C63 !important; }

    .fuente-chip {
        display: inline-block; background: #EEF3FA; color: var(--azul);
        border: 1px solid #D3E0EF; border-radius: 8px;
        padding: 0.2rem 0.55rem; margin: 0.15rem 0.25rem 0.15rem 0;
        font-size: 0.83rem; font-family: ui-monospace, monospace;
    }
    .etiqueta-seccion {
        text-transform: uppercase; letter-spacing: 0.08em;
        font-size: 0.74rem; font-weight: 700;
        color: var(--tinta-suave); margin-bottom: 0.3rem;
    }
    [data-testid="stTable"] td, [data-testid="stTable"] th { color: var(--tinta); }
</style>
""",
    unsafe_allow_html=True,
)


def _ensure_state() -> None:
    if "sesion" not in st.session_state:
        st.session_state.sesion = {}
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "ultima_respuesta" not in st.session_state:
        st.session_state.ultima_respuesta = responder("Hola", st.session_state.sesion)
    if not st.session_state.chat_history:
        st.session_state.chat_history.append(
            {"role": "assistant", "content": st.session_state.ultima_respuesta["mensaje"]}
        )


def _record_turn(user_message: str, response: dict) -> None:
    st.session_state.chat_history.append({"role": "user", "content": user_message})
    st.session_state.chat_history.append({"role": "assistant", "content": response["mensaje"]})
    st.session_state.ultima_respuesta = response
    caso = response.get("caso") or {}
    if caso:
        st.session_state.sesion["caso"] = caso


def _load_example_case() -> None:
    st.session_state.sesion["caso"] = deepcopy(CASO_DORADO)
    response = responder("Cargar caso de ejemplo", st.session_state.sesion)
    _record_turn("Cargar caso de ejemplo", response)


def _source_label(source: dict) -> str:
    fuente = source.get("fuente") or source.get("source") or "Fuente desconocida"
    pagina = source.get("pagina") or source.get("page")
    if pagina is None:
        return str(fuente)
    return f"{fuente}, p.{pagina}"


def _render_case_table(caso: dict) -> None:
    if not caso:
        st.caption("Aún no hay un caso cargado.")
        return
    rows = []
    labels = {
        "alto_mm": "Alto (mm)",
        "ancho_mm": "Ancho (mm)",
        "fondo_mm": "Fondo (mm)",
        "disipacion_w": "Disipación (W)",
        "t_ambiente_c": "Ambiente (°C)",
        "t_interior_objetivo_c": "Objetivo interior (°C)",
        "entorno": "Entorno",
    }
    for key, value in caso.items():
        rows.append({"Parámetro": labels.get(key, key), "Valor": value})
    st.table(rows)


def _render_recommendation_block(title: str, rec: dict | None, subtle: bool = False) -> None:
    if not rec:
        st.caption("Sin recomendación todavía.")
        return
    if title:
        st.markdown(f"**{title}**")
    if subtle:
        st.markdown(f"### {rec['modelo']}")
    else:
        st.metric(label="Modelo", value=rec["modelo"])
    st.caption(f"{rec['capacidad']} · Artículo {rec.get('articulo') or 'N/D'}")
    st.write(rec["porque"])


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        st.caption("Sin fuentes aún.")
        return
    chips = "".join(
        f'<span class="fuente-chip">{_source_label(s)}</span>' for s in sources
    )
    st.markdown(chips, unsafe_allow_html=True)


def _seccion(texto: str) -> None:
    st.markdown(f'<div class="etiqueta-seccion">{texto}</div>', unsafe_allow_html=True)


_ensure_state()

st.title("🧊 Pfannenberg Copilot")
st.caption("Copiloto técnico-comercial para selección térmica de gabinete.")

# Estado visible del sistema: en una demo conviene que se vea de un vistazo si
# el agente esta razonando con LLM o corriendo en modo deterministico.
_c1, _c2, _c3 = st.columns(3)
_c1.caption(f"🧠 **LLM:** {describir_llm()}")
_c2.caption(f"🔤 **Embeddings:** {describir_motor()}")
_c3.caption(
    f"🗂️ **Vectorial:** {'índice activo' if existe_indice() else 'sin índice (solo BM25)'}"
)

left, right = st.columns([3, 2], gap="large")

with left:
    with st.container(border=True):
        _seccion("Conversación")
        st.caption(
            "Un clic carga el caso de ejemplo. Después puedes escribir datos "
            "nuevos o preguntas de seguimiento."
        )
        if st.button("⚡ Cargar caso de ejemplo", use_container_width=True):
            _load_example_case()

        for item in st.session_state.chat_history:
            with st.chat_message(item["role"]):
                st.write(item["content"])

        response = st.session_state.ultima_respuesta
        if response.get("preguntas_pendientes"):
            st.info(
                "\n".join(f"• {pregunta}" for pregunta in response["preguntas_pendientes"])
            )

    prompt = st.chat_input("Escribe el caso o una pregunta de seguimiento")
    if prompt:
        # El spinner importa: el agente encadena varias llamadas y puede tardar
        # bastantes segundos. Sin señal visible parece que la app se colgó.
        with st.spinner("Consultando la documentación…"):
            try:
                answer = responder(prompt, st.session_state.sesion)
            except Exception as exc:
                # Un fallo silencioso aquí es indistinguible de "no responde".
                st.error(f"No se pudo procesar la consulta: {type(exc).__name__}: {exc}")
                st.stop()
        _record_turn(prompt, answer)
        st.rerun()

with right:
    ultima = st.session_state.ultima_respuesta

    with st.container(border=True):
        _seccion("Caso actual")
        _render_case_table(ultima.get("caso") or {})

    with st.container(border=True):
        _seccion("Recomendación")
        _render_recommendation_block("", ultima.get("recomendacion"))
        if ultima.get("alternativa"):
            st.divider()
            _seccion("Alternativa")
            _render_recommendation_block("", ultima.get("alternativa"), subtle=True)

    with st.container(border=True):
        _seccion("Supuestos")
        st.caption("Se muestran siempre: distinguen la estimación propia del dato oficial.")
        st.warning(
            "\n\n".join(
                f"• {s}" for s in (ultima.get("supuestos") or ["Sin supuestos todavía."])
            )
        )

    with st.container(border=True):
        _seccion("Fuentes")
        _render_sources(ultima.get("fuentes") or [])

        with st.expander("Ver trazas del razonamiento", expanded=False):
            trazas = ultima.get("trazas") or []
            if not trazas:
                st.caption("Sin trazas todavía.")
            else:
                for trace in trazas:
                    st.markdown(f"- {trace}")