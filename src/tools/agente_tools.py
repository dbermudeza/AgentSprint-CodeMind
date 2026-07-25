"""Herramientas del agente.

Cada herramienta devuelve texto ya citado (archivo + pagina). Esto es
deliberado: si el modelo recibe los datos sin procedencia, no puede cumplir el
invariante de citar la fuente exacta aunque quiera, y acaba inventandola.

Las cifras las calcula Python, no el modelo. El LLM decide QUE preguntar y QUE
herramienta usar; los numeros salen siempre de codigo verificable.
"""
from __future__ import annotations

from langchain_core.tools import tool

from src.rag.hibrido import buscar
from src.tools.catalogo import capacidad_legible, cargar_catalogo, filtrar_candidatos
from src.tools.dimensionar import dimensionar

# El tier gratuito de Groq limita tokens por dia, y cada fragmento que se
# devuelve al modelo los consume. Se recortan a lo justo para poder citar y
# justificar: mas texto no mejoraba la respuesta y agotaba la cuota en pocas
# consultas.
MAX_CHARS_FRAGMENTO = 420
MAX_FRAGMENTOS = 3
MAX_CANDIDATOS = 4


@tool
def buscar_documentacion(consulta: str, solo_tablas: bool = False) -> str:
    """Busca en la documentación oficial pública de Pfannenberg (60 PDFs).

    Úsala para respaldar cualquier afirmación técnica, o para responder
    preguntas sobre productos, aplicaciones o características.

    Args:
        consulta: qué buscar, EN INGLÉS. Los documentos están en inglés y el
            buscador compara la consulta contra su texto, así que una consulta
            en español devuelve resultados irrelevantes. Traduce siempre los
            términos: "lavado a presión" -> "washdown", "gabinete" ->
            "enclosure", "refrigeración" -> "cooling". Incluye los códigos de
            modelo tal cual si los conoces (ej. "DTS 3161 cooling capacity").
        solo_tablas: True para restringir a tablas de especificaciones, donde
            viven las capacidades y dimensiones. Úsalo cuando busques un dato
            numérico concreto.
    """
    fragmentos = buscar(consulta, k=MAX_FRAGMENTOS, solo_tablas=solo_tablas)
    if not fragmentos:
        return (
            "Sin resultados en la documentación oficial. No inventes el dato: "
            "dilo explícitamente y pide la información que falte."
        )

    partes = []
    for f in fragmentos:
        texto = f.texto[:MAX_CHARS_FRAGMENTO]
        partes.append(f"[FUENTE: {f.cita()}]\n{texto}")
    return "\n\n---\n\n".join(partes)


@tool
def calcular_dimensionamiento(
    disipacion_w: float,
    t_ambiente_c: float,
    t_interior_objetivo_c: float,
    alto_mm: float,
    ancho_mm: float,
    fondo_mm: float,
) -> str:
    """Estima la carga térmica a extraer de un gabinete y qué tecnología aplica.

    IMPORTANTE: el resultado es una estimación propia, NO un cálculo oficial de
    Pfannenberg. Debes trasladar al usuario los supuestos que devuelve esta
    herramienta y la derivación al Pfannenberg Sizing Software (PSS).

    Llámala solo cuando tengas los seis parámetros. Si falta alguno, pregúntalo
    antes; no lo asumas.

    Args:
        disipacion_w: potencia disipada por los componentes internos, en vatios.
        t_ambiente_c: temperatura ambiente máxima del entorno, en °C.
        t_interior_objetivo_c: temperatura máxima admisible dentro, en °C.
        alto_mm: alto del gabinete en mm.
        ancho_mm: ancho del gabinete en mm.
        fondo_mm: fondo del gabinete en mm.
    """
    d = dimensionar(
        disipacion_w=disipacion_w,
        t_ambiente_c=t_ambiente_c,
        t_interior_objetivo_c=t_interior_objetivo_c,
        alto_mm=alto_mm,
        ancho_mm=ancho_mm,
        fondo_mm=fondo_mm,
    )
    supuestos = "\n".join(f"  - {s}" for s in d.supuestos)
    return (
        f"Superficie efectiva: {d.superficie_efectiva_m2:.2f} m²\n"
        f"ΔT (interior − ambiente): {d.delta_t_k:+.0f} K\n"
        f"Disipación pasiva por paredes: {d.disipacion_pasiva_w:+.0f} W\n"
        f"CARGA A EXTRAER: {d.rango_legible}\n"
        f"TECNOLOGÍA APLICABLE: {d.tecnologia}\n"
        f"Motivo: {d.motivo}\n"
        f"SUPUESTOS (debes comunicarlos al usuario):\n{supuestos}"
    )


@tool
def consultar_catalogo(tecnologia: str, carga_w: float, delta_t_k: float) -> str:
    """Lista los equipos del catálogo que cubren una carga térmica dada.

    Devuelve candidatos con su capacidad y su fuente, más los descartados con
    el motivo. Usa `calcular_dimensionamiento` antes para saber qué tecnología
    y qué carga pedir.

    Args:
        tecnologia: "refrigeracion activa", "aire/aire", "aire/agua" o "ventilacion".
        carga_w: vatios que hay que extraer.
        delta_t_k: salto térmico disponible, necesario para los equipos aire/aire
            que se especifican en W/K.
    """
    productos, _ = cargar_catalogo()
    candidatos, descartes = filtrar_candidatos(
        productos,
        tecnologia=tecnologia,
        carga_min_w=carga_w,
        carga_max_w=carga_w,
        delta_t_k=delta_t_k,
    )
    if not candidatos:
        return (
            f"Ningún equipo de tipo '{tecnologia}' cubre {carga_w:.0f} W con un solo módulo.\n"
            "Descartados: " + "; ".join(descartes[:6])
        )

    lineas = [f"Candidatos para {carga_w:.0f} W ({tecnologia}), del más ajustado al mayor:"]
    for p in candidatos[:MAX_CANDIDATOS]:
        aviso = " ⚠️ atribución ambigua en la tabla de origen" if p.confianza != "alta" else ""
        articulo = f", art. {p.articulo}" if p.articulo else ""
        lineas.append(
            f"  - {p.modelo}: {capacidad_legible(p, delta_t_k)}{articulo} "
            f"[FUENTE: {p.cita()}]{aviso}"
        )
    if descartes:
        lineas.append("Descartados por capacidad insuficiente: " + "; ".join(descartes[:3]))
    return "\n".join(lineas)


HERRAMIENTAS = [buscar_documentacion, calcular_dimensionamiento, consultar_catalogo]
