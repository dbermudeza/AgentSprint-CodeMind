from __future__ import annotations

from copy import deepcopy

import streamlit as st

from src.api import responder
from src.contracts import CASO_DORADO


st.set_page_config(
    page_title="Pfannenberg Copilot",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, rgba(0, 92, 185, 0.10), transparent 28%),
            radial-gradient(circle at top right, rgba(255, 184, 0, 0.10), transparent 24%),
            linear-gradient(180deg, #f6f8fb 0%, #eef3f8 100%);
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    .panel-card {
        background: rgba(255, 255, 255, 0.90);
        border: 1px solid rgba(23, 34, 56, 0.08);
        border-radius: 18px;
        padding: 1rem 1.05rem;
        box-shadow: 0 8px 30px rgba(18, 32, 64, 0.06);
    }
    .muted {
        color: rgba(49, 60, 77, 0.72);
        font-size: 0.95rem;
    }
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
    for source in sources:
        st.markdown(f"- {_source_label(source)}")


_ensure_state()

st.title("Pfannenberg Copilot")
st.caption("Copiloto técnico-comercial para selección térmica de gabinete.")

left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader("Chat")
    st.markdown(
        """
        <div class="muted">
        Un solo clic carga el caso dorado. Después puedes escribir datos o preguntas para simular la conversación.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Cargar caso de ejemplo", use_container_width=True):
        _load_example_case()

    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]):
            st.write(item["content"])

    response = st.session_state.ultima_respuesta
    if response.get("preguntas_pendientes"):
        st.info("\n".join(f"• {pregunta}" for pregunta in response["preguntas_pendientes"]))

    prompt = st.chat_input("Escribe el caso o una pregunta de seguimiento")
    if prompt:
        answer = responder(prompt, st.session_state.sesion)
        _record_turn(prompt, answer)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader("Resultados")

    st.markdown("**Caso actual**")
    _render_case_table(st.session_state.ultima_respuesta.get("caso") or {})

    st.markdown("---")
    _render_recommendation_block("Recomendación", st.session_state.ultima_respuesta.get("recomendacion"))

    st.markdown("---")
    _render_recommendation_block(
        "Alternativa",
        st.session_state.ultima_respuesta.get("alternativa"),
        subtle=True,
    )

    st.markdown("---")
    st.warning("\n".join(st.session_state.ultima_respuesta.get("supuestos") or ["Sin supuestos cargados todavía."]))

    st.markdown("**Fuentes**")
    _render_sources(st.session_state.ultima_respuesta.get("fuentes") or [])

    with st.expander("Ver trazas", expanded=False):
        trazas = st.session_state.ultima_respuesta.get("trazas") or []
        if not trazas:
            st.caption("Sin trazas todavía.")
        else:
            for trace in trazas:
                st.markdown(f"- {trace}")
    st.markdown("</div>", unsafe_allow_html=True)