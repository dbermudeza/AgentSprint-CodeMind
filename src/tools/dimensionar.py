"""Estimacion de la carga termica de un gabinete electrico.

⚠️ LEER ANTES DE TOCAR ESTE ARCHIVO ⚠️

La documentacion publica de Pfannenberg NO publica su formula de
dimensionamiento: delega el calculo al Pfannenberg Sizing Software (PSS)
—ver CLAUDE.md, "Restriccion sobre el calculo termico"—. El invariante del
proyecto prohibe inventar formulas y atribuirlas a Pfannenberg.

Por tanto todo lo que hay aqui es un SUPUESTO PROPIO Y DECLARADO, basado en
practica estandar de ingenieria y en la norma publica IEC 60890. Cada
resultado viaja acompanado de `supuestos`, que la UI muestra siempre, y de la
derivacion al PSS para el dimensionamiento certificado.

Nunca presentar esta estimacion como respaldada por documentacion oficial de
Pfannenberg.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Transmitancia termica de chapa de acero pintada. Valor de practica comun de
# ingenieria (rango habitual 5.0-6.0 W/m2K). NO es un dato de Pfannenberg.
K_ACERO_PINTADO_W_M2K = 5.5

# Margen sobre la carga calculada: cubre envejecimiento del equipo, suciedad
# del filtro y error de estimacion. Criterio propio.
MARGEN_SEGURIDAD = 0.15

# Capacidad especifica maxima disponible en la familia aire/aire (PAS 6203,
# 100 W/K). Se usa solo para avisar cuando un solo equipo no alcanza.
MAX_CAPACIDAD_AIRE_AIRE_W_K = 100.0


@dataclass
class Dimensionamiento:
    """Resultado de la estimacion. Nunca se muestra sin `supuestos`."""

    superficie_efectiva_m2: float
    delta_t_k: float
    disipacion_pasiva_w: float
    carga_neta_w: float
    # Rango, no un numero falsamente preciso.
    rango_min_w: float
    rango_max_w: float
    tecnologia: str  # "ventilacion" | "aire/aire" | "refrigeracion activa"
    motivo: str
    supuestos: list[str] = field(default_factory=list)
    trazas: list[str] = field(default_factory=list)
    capacidad_aire_aire_requerida_w_k: float | None = None

    @property
    def rango_legible(self) -> str:
        return f"{self.rango_min_w:.0f}–{self.rango_max_w:.0f} W"


def superficie_efectiva_iec60890(
    alto_mm: float, ancho_mm: float, fondo_mm: float
) -> float:
    """Superficie efectiva de intercambio, segun IEC 60890.

    Ae = 1.8 · H · (W + D) + 1.4 · W · D

    Corresponde al caso de gabinete exento con todas las caras expuestas al
    ambiente. IEC 60890 es una norma publica; no es una formula de Pfannenberg.
    Si el gabinete va adosado a pared o en fila, la superficie util es menor y
    esta estimacion queda del lado optimista.
    """
    h, w, d = alto_mm / 1000, ancho_mm / 1000, fondo_mm / 1000
    return 1.8 * h * (w + d) + 1.4 * w * d


def dimensionar(
    disipacion_w: float,
    t_ambiente_c: float,
    t_interior_objetivo_c: float,
    alto_mm: float,
    ancho_mm: float,
    fondo_mm: float,
) -> Dimensionamiento:
    """Estima la carga termica a extraer y que tecnologia la puede cubrir.

    Balance (supuesto propio, no oficial):

        carga_neta = disipacion_interna − k · Ae · (T_interior − T_ambiente)

    El segundo termino es lo que el propio gabinete disipa por sus paredes.
    Cuando el ambiente esta mas caliente que el objetivo interior ese termino
    se invierte: el gabinete *gana* calor del exterior y hay que extraerlo
    ademas de la disipacion interna.
    """
    trazas: list[str] = []

    area = superficie_efectiva_iec60890(alto_mm, ancho_mm, fondo_mm)
    delta_t = t_interior_objetivo_c - t_ambiente_c
    disipacion_pasiva = K_ACERO_PINTADO_W_M2K * area * delta_t
    carga_neta = disipacion_w - disipacion_pasiva

    trazas.append(
        f"superficie efectiva (IEC 60890): {area:.2f} m² "
        f"para {alto_mm:.0f}x{ancho_mm:.0f}x{fondo_mm:.0f} mm"
    )
    trazas.append(f"ΔT = {t_interior_objetivo_c:.0f} − {t_ambiente_c:.0f} = {delta_t:+.0f} K")
    trazas.append(
        f"disipacion pasiva por paredes: {disipacion_pasiva:+.0f} W "
        f"(k={K_ACERO_PINTADO_W_M2K} W/m²K)"
    )
    trazas.append(f"carga neta a extraer: {disipacion_w:.0f} − {disipacion_pasiva:.0f} = {carga_neta:.0f} W")

    supuestos = [
        f"Transmitancia k = {K_ACERO_PINTADO_W_M2K} W/m²K (chapa de acero pintada), "
        "valor de práctica común de ingeniería.",
        f"Superficie efectiva {area:.2f} m² calculada con IEC 60890 "
        "(norma pública), asumiendo gabinete exento con todas las caras expuestas.",
        f"Margen de seguridad del {MARGEN_SEGURIDAD:.0%} sobre la carga calculada.",
        "⚠️ Pfannenberg no publica su fórmula de dimensionamiento en la documentación "
        "oficial: esta estimación es un supuesto propio, no un cálculo certificado. "
        "Para el dimensionamiento definitivo use el Pfannenberg Sizing Software (PSS).",
    ]

    # --- Caso 1: el gabinete se refrigera solo -------------------------------
    if carga_neta <= 0:
        trazas.append("carga neta <= 0: la disipacion natural cubre la carga interna")
        return Dimensionamiento(
            superficie_efectiva_m2=area,
            delta_t_k=delta_t,
            disipacion_pasiva_w=disipacion_pasiva,
            carga_neta_w=carga_neta,
            rango_min_w=0.0,
            rango_max_w=0.0,
            tecnologia="ventilacion",
            motivo=(
                f"La disipación natural por las paredes ({disipacion_pasiva:.0f} W) ya supera "
                f"la carga interna ({disipacion_w:.0f} W). No se requiere refrigeración: "
                "bastaría ventilación forzada con filtro para homogeneizar la temperatura."
            ),
            supuestos=supuestos,
            trazas=trazas,
        )

    rango_min = carga_neta
    rango_max = carga_neta * (1 + MARGEN_SEGURIDAD)

    # --- Caso 2: el ambiente esta igual o mas caliente que el objetivo -------
    # Un intercambiador aire/aire mueve calor por diferencia de temperatura.
    # Sin diferencia favorable no hay nada que lo empuje: es fisicamente
    # imposible, por muy grande que sea el equipo.
    if delta_t <= 0:
        trazas.append("ΔT <= 0: aire/aire fisicamente inviable, se exige refrigeracion activa")
        motivo = (
            f"El ambiente ({t_ambiente_c:.0f} °C) está por encima o al nivel de la temperatura "
            f"objetivo del interior ({t_interior_objetivo_c:.0f} °C). Un intercambiador aire/aire "
            "o una ventilación con filtro no pueden funcionar aquí: ambos dependen de que el aire "
            "exterior esté más frío, y no lo está. Se requiere refrigeración activa (ciclo "
            "frigorífico), que sí puede enfriar por debajo de la temperatura ambiente."
        )
        if delta_t < 0:
            motivo += (
                f" Además el gabinete gana {abs(disipacion_pasiva):.0f} W del exterior, "
                "que se suman a la carga interna."
            )
        return Dimensionamiento(
            superficie_efectiva_m2=area,
            delta_t_k=delta_t,
            disipacion_pasiva_w=disipacion_pasiva,
            carga_neta_w=carga_neta,
            rango_min_w=rango_min,
            rango_max_w=rango_max,
            tecnologia="refrigeracion activa",
            motivo=motivo,
            supuestos=supuestos,
            trazas=trazas,
        )

    # --- Caso 3: hay ΔT favorable; ¿alcanza un aire/aire? -------------------
    # Los intercambiadores aire/aire se especifican en W/K: entregan su
    # capacidad multiplicada por la diferencia de temperatura disponible.
    capacidad_requerida_w_k = rango_max / delta_t
    trazas.append(
        f"aire/aire requeriria {capacidad_requerida_w_k:.0f} W/K "
        f"(max disponible en catalogo: {MAX_CAPACIDAD_AIRE_AIRE_W_K:.0f} W/K)"
    )

    if capacidad_requerida_w_k <= MAX_CAPACIDAD_AIRE_AIRE_W_K:
        tecnologia = "aire/aire"
        motivo = (
            f"Con ΔT favorable de {delta_t:.0f} K, un intercambiador aire/aire de "
            f"{capacidad_requerida_w_k:.0f} W/K cubre la carga sin ciclo frigorífico, "
            "con menor consumo y mantenimiento que una unidad de refrigeración."
        )
    else:
        tecnologia = "refrigeracion activa"
        motivo = (
            f"Aunque el ΔT de {delta_t:.0f} K es favorable, cubrir {rango_max:.0f} W por "
            f"intercambio aire/aire exigiría {capacidad_requerida_w_k:.0f} W/K, por encima "
            f"del mayor equipo del catálogo ({MAX_CAPACIDAD_AIRE_AIRE_W_K:.0f} W/K). "
            "Se descarta por capacidad, no por física, y se recomienda refrigeración activa."
        )

    return Dimensionamiento(
        superficie_efectiva_m2=area,
        delta_t_k=delta_t,
        disipacion_pasiva_w=disipacion_pasiva,
        carga_neta_w=carga_neta,
        rango_min_w=rango_min,
        rango_max_w=rango_max,
        tecnologia=tecnologia,
        motivo=motivo,
        supuestos=supuestos,
        trazas=trazas,
        capacidad_aire_aire_requerida_w_k=capacidad_requerida_w_k,
    )
