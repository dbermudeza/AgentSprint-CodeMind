from __future__ import annotations


def responder(mensaje: str, sesion: dict) -> dict:
    caso = dict(sesion.get("caso") or {})
    tiene_caso = bool(caso)

    if not tiene_caso:
        return {
            "mensaje": (
                "Tengo una ruta de demo lista, pero todavía faltan datos para recomendar con seguridad. "
                "Puedes cargar el caso de ejemplo o decirme dimensiones, disipación, temperatura ambiente y objetivo interior."
            ),
            "preguntas_pendientes": [
                "¿Cuál es la disipación térmica del gabinete en W?",
                "¿Cuáles son alto, ancho y fondo del gabinete?",
                "¿Qué temperatura ambiente y objetivo interior quieres mantener?",
            ],
            "recomendacion": None,
            "alternativa": None,
            "supuestos": [
                "La estimación térmica se mostrará solo cuando exista un caso cargado en la sesión.",
                "El dimensionamiento certificado debe validarse después en el Pfannenberg Sizing Software.",
            ],
            "fuentes": [],
            "trazas": [
                "Mock backend activo.",
                "No se detectó caso cargado en la sesión.",
            ],
            "caso": {},
        }

    return {
        "mensaje": (
            "Con el caso cargado, la recomendación principal para la demo es PAS 6133. "
            "El objetivo es mostrar una selección trazable, no sustituir el cálculo certificado."
        ),
        "preguntas_pendientes": [],
        "recomendacion": {
            "modelo": "PAS 6133",
            "capacidad": "65 W/K",
            "porque": (
                "Encaja como opción principal para la demostración: se alinea con el caso dorado, "
                "permite explicar el filtrado por catálogo y deja visible la diferencia entre estimación y dato oficial."
            ),
            "articulo": "12982411055",
            "fuentes": [
                {"fuente": "Thermal_Management_EN_V4.pdf", "pagina": 45},
                {"fuente": "Thermal_Management_EN_V4.pdf", "pagina": 52},
            ],
        },
        "alternativa": {
            "modelo": "PAS 6112",
            "capacidad": "55 W/K",
            "porque": (
                "Sirve como alternativa más conservadora cuando se quiere mostrar un segundo candidato "
                "de la misma familia y dejar claro por qué se prioriza la opción principal."
            ),
            "articulo": "12982411045",
            "fuentes": [
                {"fuente": "Thermal_Management_EN_V4.pdf", "pagina": 45},
            ],
        },
        "supuestos": [
            "La selección mostrada es una estimación propia basada en el caso de demo cargado, no un cálculo certificado por Pfannenberg.",
            "El caso se presenta con gabinete 2000 × 800 × 600 mm, disipación interna de 1200 W, ambiente de 35 °C y objetivo interior de 40 °C.",
            "La validación final debe hacerse en el Pfannenberg Sizing Software antes de usar el resultado en producción.",
        ],
        "fuentes": [
            {"fuente": "Thermal_Management_EN_V4.pdf", "pagina": 45},
            {"fuente": "Thermal_Management_EN_V4.pdf", "pagina": 52},
        ],
        "trazas": [
            "Caso detectado en la sesión y precargado desde CASO_DORADO.",
            "Se priorizó la familia PAS por ser una demo de selección térmica de gabinete aire/aire.",
            "Se eligió PAS 6133 como recomendación principal y PAS 6112 como alternativa de contraste.",
            "Las fuentes citadas apuntan a Thermal_Management_EN_V4.pdf, p.45 y p.52.",
        ],
        "caso": caso,
    }