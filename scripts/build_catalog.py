"""Extrae un catalogo estructurado de productos de refrigeracion desde las tablas del corpus.

    python scripts/build_catalog.py    # chunks.jsonl -> data/processed/productos.json

El corpus trae dos layouts de tabla y cada uno falla de una forma distinta:

  A) Fila por modelo (tablas resumen de Thermal_Management_EN_V4.pdf):

        | DTS 3031 | 306 W | 230 V | 394 x 178 x 229 mm | 82 |

     Limpio: cada modelo tiene su celda propia. De aqui sale la confianza "alta".

  B) Columna por modelo (fichas de los catalogos):

        | PRODUCT                   |  |  |  | PAS 6043 | PAS 6133 | PAS 6203 | Unit |
        | Specific cooling capacity |  |  |  | 20       | 65       | 100      | W/K  |
        | Power consumption         |  |  |  | 50 | 56  | 310 | 420 |        | W    |

     La fila de capacidad alinea 3 valores con 3 modelos. La de consumo trae 4
     valores para 3 modelos (variantes 50/60 Hz colapsadas): la atribucion
     columna -> modelo es indecidible. CLAUDE.md ("Zonas de baja confianza")
     avisa de esto y el invariante "no inventar especificaciones" obliga a
     descartarla, no a repartir los valores por orden de aparicion.

La regla que ordena todo el script: una spec se acepta solo si la fila se alinea
posicionalmente con la cabecera. Si la fila tiene otro ancho, se descarta y se
reporta. Preferimos 15 productos ciertos a 60 inventados.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.contracts import Producto  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
CHUNKS_PATH = RAIZ / "data" / "processed" / "chunks.jsonl"
SALIDA_PATH = RAIZ / "data" / "processed" / "productos.json"

# Familias de refrigeracion y su tipo segun la nomenclatura del propio catalogo
# (Thermal_Management_EN_V4.pdf, p.58 y p.91).
FAMILIAS = {
    "DTS": "refrigeracion activa",
    "DTI": "refrigeracion activa",
    "DTT": "refrigeracion activa",
    "PAS": "aire/aire",
    "PWS": "aire/agua",
}

# Marketing, no specs (CLAUDE.md): los case studies citan modelos usados en un
# proyecto, sin datos tecnicos que atribuir.
FUENTES_EXCLUIDAS = ("pfannenberg_cut-out_compatibility_list", "case_study")

# Una celda debe SER el dato, no contenerlo. "1150 W" vale; "Cooling capacity
# (EN 14511) @ A35/A35" no. Asi una etiqueta nunca se cuela como valor.
RE_MODELO = re.compile(
    r"^(DTS|DTI|DTT|PAS|PWS)\s*-?\s*(\d{3,4}[A-Z]?)((?:\s+[A-Z]{1,3})?)$", re.I
)
# Solo detecta la mencion, sin exigir que la celda sea el modelo. Sirve para
# reconocer cabeceras donde una columna cubre varios productos a la vez.
RE_MENCIONA_MODELO = re.compile(r"\b(DTS|DTI|DTT|PAS|PWS)\s*-?\s*\d{3,4}", re.I)
RE_CAPACIDAD = re.compile(r"^(\d{2,5}(?:[.,]\d+)?)\s*(W/K|W)$", re.I)
RE_NUMERO = re.compile(r"^(\d{2,5}(?:[.,]\d+)?)$")
RE_DIMENSIONES = re.compile(
    r"^\d{2,4}(?:\.\d+)?\s*x\s*\d{2,4}(?:\.\d+)?\s*x\s*\d{2,4}(?:\.\d+)?(\s*mm)?$", re.I
)
RE_TENSION = re.compile(r"^\d{2,3}(?:/\d{2,3})?\s*V(\s*\d\s*~)?$", re.I)
RE_ARTICULO = re.compile(r"^\d{10,11}$")

RE_ETIQUETA_CAPACIDAD = re.compile(r"cooling capacity", re.I)
RE_ETIQUETA_ARTICULO = re.compile(r"article no", re.I)
RE_ETIQUETA_DIMENSION = re.compile(r"^dimension", re.I)
RE_ETIQUETA_TENSION = re.compile(r"rated voltage", re.I)

UNIDADES_CAPACIDAD = {"w", "w/k"}


# ---------------------------------------------------------------------------
# Lectura de las tablas Markdown que produjo scripts/process_pdfs.py
# ---------------------------------------------------------------------------


def leer_filas(texto: str) -> list[list[str]]:
    """Convierte un bloque Markdown en filas de celdas ya normalizadas."""
    filas: list[list[str]] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in celdas):  # separador o fila vacia
            continue
        filas.append(celdas)
    return filas


def leer_modelo(celda: str) -> str | None:
    """Devuelve el modelo normalizado si la celda es exactamente un modelo."""
    coincidencia = RE_MODELO.match(celda.strip())
    if not coincidencia:
        return None
    familia, numero, sufijo = coincidencia.groups()
    modelo = f"{familia.upper()} {numero.upper()}"
    return f"{modelo} {sufijo.strip().upper()}" if sufijo.strip() else modelo


def normalizar_dimensiones(celda: str) -> str:
    """Las fichas sacan la unidad a su propia columna ("380 x 618 x 212 | mm")."""
    celda = " ".join(celda.split())
    return celda if celda.lower().endswith("mm") else f"{celda} mm"


def leer_capacidad(celda: str, unidad_fila: str | None = None) -> tuple[float, str] | None:
    """Lee una capacidad de la celda, o del numero + la unidad de la columna final.

    Las fichas del tipo B sacan la unidad a una columna aparte ("... | 100 | W/K"),
    asi que un "100" pelado solo es interpretable con esa unidad de fila.
    """
    celda = celda.strip()
    coincidencia = RE_CAPACIDAD.match(celda)
    if coincidencia:
        return float(coincidencia.group(1).replace(",", ".")), coincidencia.group(2).upper()

    if unidad_fila and unidad_fila.lower() in UNIDADES_CAPACIDAD:
        numero = RE_NUMERO.match(celda)
        if numero:
            return float(numero.group(1).replace(",", ".")), unidad_fila.upper()
    return None


# ---------------------------------------------------------------------------
# Extractor A — tablas con un modelo por fila
# ---------------------------------------------------------------------------


def extraer_por_filas(chunk: dict, descartes: Counter) -> list[tuple[Producto, str]]:
    """Cada fila abre con un modelo y lleva sus specs a la derecha.

    Cuando una fila no trae capacidad propia es porque el PDF la fusiono
    verticalmente con la de arriba (DTI 6201 / DTS 6201 comparten 1150 W). El
    valor se hereda, pero la atribucion depende de interpretar esa fusion: eso
    es confianza "media", no "alta".
    """
    encontrados: list[tuple[Producto, str]] = []
    capacidad_previa: tuple[float, str] | None = None

    for fila in leer_filas(chunk["text"]):
        modelo = leer_modelo(fila[0]) if fila else None
        if not modelo:
            continue
        if any(leer_modelo(c) for c in fila[1:]):
            descartes["fila con varios modelos"] += 1
            continue

        resto = fila[1:]
        capacidades = [c for c in (leer_capacidad(x) for x in resto) if c]

        if len(capacidades) == 1:
            capacidad, confianza = capacidades[0], "alta"
            capacidad_previa = capacidad
        elif not capacidades and capacidad_previa:
            capacidad, confianza = capacidad_previa, "media"
        elif len(capacidades) > 1:
            descartes["fila con varias capacidades"] += 1
            continue
        else:
            descartes["fila sin capacidad"] += 1
            continue

        dimensiones = [c for c in resto if RE_DIMENSIONES.match(c)]
        tensiones = [c for c in resto if RE_TENSION.match(c)]
        articulos = [c for c in resto if RE_ARTICULO.match(c)]

        encontrados.append(
            (
                Producto(
                    modelo=modelo,
                    familia=modelo.split()[0],
                    tipo=FAMILIAS[modelo.split()[0]],
                    capacidad_valor=capacidad[0],
                    capacidad_unidad=capacidad[1],
                    fuente=chunk["source"],
                    pagina=chunk["page"],
                    # Varias tensiones = variantes reales del modelo, no ambiguedad.
                    tension=" / ".join(tensiones) or None,
                    dimensiones_mm=(
                        normalizar_dimensiones(dimensiones[0])
                        if len(dimensiones) == 1
                        else None
                    ),
                    articulo=articulos[0] if len(articulos) == 1 else None,
                    confianza=confianza,
                ),
                "fila-por-modelo",
            )
        )

    return encontrados


# ---------------------------------------------------------------------------
# Extractor B — fichas con un modelo por columna
# ---------------------------------------------------------------------------


def _valores_alineados(
    fila: list[str], columnas: dict[int, str], validador
) -> dict[str, str] | None:
    """Mapea modelo -> valor solo si la fila se alinea con la cabecera.

    Devuelve None ante cualquier duda. Es la funcion que impide el error que
    documenta CLAUDE.md: repartir "50 | 56 | 310 | 420" entre tres modelos.
    """
    unidad_fila = fila[-1] if fila else None
    valores: dict[str, str] = {}
    for indice, modelo in columnas.items():
        celda = fila[indice]
        if not celda:
            continue
        if validador(celda, unidad_fila):
            valores[modelo] = celda

    if len(valores) == len(columnas):
        return valores  # 1:1, sin ambiguedad
    if len(valores) == 1 and all(not fila[i] for i in columnas if columnas[i] not in valores):
        return valores  # celda fusionada: un valor, el resto de columnas vacias
    return None


def _cabecera_ambigua(cabecera: list[str], columnas: dict[int, str]) -> bool:
    """Detecta cabeceras donde una columna no corresponde a un unico modelo.

    Caso real (Pfannenberg_Compact_catalogue_30_en.pdf, p.20):

        | PRODUCT | DTI 9041 DTS 9041 | DTS 9041 |
        | Cooling capacity ...        | 870 W     | 810 W    |

    La primera columna cubre dos productos y "DTS 9041" aparece en ambas: las
    columnas son variantes de tension (230 V / 400 V), no modelos distintos.
    Leer solo la columna que si parsea daria "DTS 9041 = 810 W" con apariencia
    de certeza, ocultando los 870 W de la otra variante. Se descarta la tabla.
    """
    if any(
        RE_MENCIONA_MODELO.search(celda)
        for indice, celda in enumerate(cabecera)
        if indice not in columnas
    ):
        return True
    return len(set(columnas.values())) != len(columnas)


def extraer_por_columnas(chunk: dict, descartes: Counter) -> list[tuple[Producto, str]]:
    filas = leer_filas(chunk["text"])

    cabecera: list[str] | None = None
    columnas: dict[int, str] = {}
    for fila in filas:
        candidatas = {i: leer_modelo(c) for i, c in enumerate(fila)}
        candidatas = {i: m for i, m in candidatas.items() if m}
        if candidatas and not leer_modelo(fila[0]):
            cabecera, columnas = fila, candidatas
            break

    if not cabecera:
        return []

    if _cabecera_ambigua(cabecera, columnas):
        descartes["ficha: columna cubre varios modelos"] += 1
        return []

    capacidades: dict[str, tuple[float, str]] = {}
    fusionada = False
    articulos: dict[str, str] = {}
    dimensiones: dict[str, str] = {}
    tensiones: dict[str, str] = {}

    for fila in filas:
        if fila is cabecera or len(fila) != len(cabecera):
            if fila is not cabecera and any(RE_ETIQUETA_CAPACIDAD.search(c) for c in fila):
                descartes["ficha: fila de capacidad desalineada"] += 1
            continue

        etiqueta = fila[0]
        if RE_ETIQUETA_CAPACIDAD.search(etiqueta):
            valores = _valores_alineados(
                fila, columnas, lambda c, u: leer_capacidad(c, u) is not None
            )
            if valores is None:
                descartes["ficha: capacidad ambigua"] += 1
                continue
            fusionada = len(valores) < len(columnas)
            unidad_fila = fila[-1]
            for modelo, celda in valores.items():
                leida = leer_capacidad(celda, unidad_fila)
                if leida:
                    capacidades[modelo] = leida
        elif RE_ETIQUETA_ARTICULO.search(etiqueta):
            valores = _valores_alineados(fila, columnas, lambda c, u: RE_ARTICULO.match(c))
            # Un articulo fusionado no existe: cada modelo tiene su referencia.
            if valores and len(valores) == len(columnas):
                articulos.update(valores)
        elif RE_ETIQUETA_DIMENSION.search(etiqueta):
            valores = _valores_alineados(fila, columnas, lambda c, u: RE_DIMENSIONES.match(c))
            if valores and len(valores) == len(columnas):
                dimensiones.update(
                    {m: normalizar_dimensiones(v) for m, v in valores.items()}
                )
        elif RE_ETIQUETA_TENSION.search(etiqueta):
            valores = _valores_alineados(fila, columnas, lambda c, u: RE_TENSION.match(c))
            if valores and len(valores) == len(columnas):
                tensiones.update(valores)

    if not capacidades:
        return []

    # Una capacidad fusionada se lee literal del PDF, pero atribuirla a cada
    # modelo exige interpretar la fusion -> "media", igual que en el extractor A.
    confianza = "media" if fusionada else "alta"
    modelos_capacidad = set(capacidades)
    if fusionada:
        capacidad_unica = next(iter(capacidades.values()))
        capacidades = {m: capacidad_unica for m in columnas.values()}

    return [
        (
            Producto(
                modelo=modelo,
                familia=modelo.split()[0],
                tipo=FAMILIAS[modelo.split()[0]],
                capacidad_valor=capacidad[0],
                capacidad_unidad=capacidad[1],
                fuente=chunk["source"],
                pagina=chunk["page"],
                tension=tensiones.get(modelo),
                dimensiones_mm=dimensiones.get(modelo),
                articulo=articulos.get(modelo),
                confianza="alta" if modelo in modelos_capacidad and not fusionada else confianza,
            ),
            "columna-por-modelo",
        )
        for modelo, capacidad in capacidades.items()
    ]


# ---------------------------------------------------------------------------
# Consolidacion
# ---------------------------------------------------------------------------

RANGO_CONFIANZA = {"alta": 2, "media": 1}


def _completitud(producto: Producto) -> int:
    """Peso para desempatar lecturas del mismo modelo.

    El numero de articulo pesa mas porque es lo que cierra hacia una referencia
    comprable, y ademas es autovalidable (11 digitos, solo se extrae con
    alineacion 1:1).
    """
    return (
        3 * bool(producto.articulo)
        + bool(producto.dimensiones_mm)
        + bool(producto.tension)
    )


def consolidar(
    candidatos: list[tuple[Producto, str]]
) -> tuple[list[Producto], Counter, int]:
    """Un registro por modelo: gana la lectura mas confiable y mas completa.

    Nunca se mezclan specs de varias paginas en un mismo registro. Un producto
    con capacidad de la p.45 y articulo de la p.47 no existe tal cual en ninguna
    pagina, y `fuente` + `pagina` tienen que poder verificarse abriendo esa
    pagina exacta -- es la regla de citar la fuente exacta. Cada registro es la
    lectura fiel de una sola tabla; las demas lecturas solo sirven para
    corroborar o para detectar conflictos.
    """
    por_modelo: dict[str, list[Producto]] = defaultdict(list)
    for producto, _ in candidatos:
        por_modelo[producto.modelo].append(producto)

    conflictos: Counter = Counter()
    corroborados = 0
    catalogo: list[Producto] = []

    for modelo, opciones in sorted(por_modelo.items()):
        opciones.sort(
            key=lambda p: (RANGO_CONFIANZA[p.confianza], _completitud(p)), reverse=True
        )
        elegido = opciones[0]

        capacidades = {(p.capacidad_valor, p.capacidad_unidad) for p in opciones}
        if len(capacidades) > 1:
            # Dos paginas discrepan sobre el mismo modelo: una esta mal leida.
            # Degradar es mas honesto que elegir a ciegas.
            conflictos[modelo] = len(capacidades)
            elegido.confianza = "media"
        elif len(opciones) > 1:
            corroborados += 1

        catalogo.append(elegido)

    return catalogo, conflictos, corroborados


def main() -> None:
    if not CHUNKS_PATH.exists():
        raise SystemExit(f"Falta {CHUNKS_PATH}. Corre antes: python scripts/process_pdfs.py")

    descartes: Counter = Counter()
    candidatos: list[tuple[Producto, str]] = []
    tablas = 0

    with CHUNKS_PATH.open(encoding="utf-8") as archivo:
        for linea in archivo:
            chunk = json.loads(linea)
            if chunk.get("type") != "table":
                continue
            fuente = chunk["source"].lower()
            if any(patron in fuente for patron in FUENTES_EXCLUIDAS):
                continue
            tablas += 1
            candidatos.extend(extraer_por_filas(chunk, descartes))
            candidatos.extend(extraer_por_columnas(chunk, descartes))

    catalogo, conflictos, corroborados = consolidar(candidatos)
    catalogo.sort(key=lambda p: (p.familia, p.capacidad_valor or 0))

    SALIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_PATH.write_text(
        json.dumps([p.to_dict() for p in catalogo], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ---- Reporte -----------------------------------------------------------
    altas = [p for p in catalogo if p.confianza == "alta"]
    medias = [p for p in catalogo if p.confianza == "media"]

    print(f"Tablas analizadas: {tablas}")
    print(f"Lecturas candidatas: {len(candidatos)}  ->  {len(catalogo)} modelos unicos\n")

    print(f"CATALOGO: {len(catalogo)} productos ({len(altas)} alta, {len(medias)} media)")
    for familia in sorted(FAMILIAS):
        de_familia = [p for p in catalogo if p.familia == familia]
        if not de_familia:
            continue
        n_altas = sum(1 for p in de_familia if p.confianza == "alta")
        unidades = sorted({p.capacidad_unidad for p in de_familia if p.capacidad_unidad})
        valores = [p.capacidad_valor for p in de_familia if p.capacidad_valor]
        rango = f"{min(valores):g}-{max(valores):g} {'/'.join(unidades)}" if valores else "-"
        print(f"  {familia}: {len(de_familia):>3} modelos ({n_altas} alta)   {rango}")

    con_articulo = sum(1 for p in catalogo if p.articulo)
    print(f"\n  {con_articulo} con numero de articulo")
    print(f"  {corroborados} confirmados por 2+ paginas independientes (misma capacidad)")

    print(f"\nDESCARTADOS: {sum(descartes.values())} lecturas")
    for motivo, cuantas in descartes.most_common():
        print(f"  {cuantas:>4}  {motivo}")

    if conflictos:
        print("\nCONFLICTOS (dos lecturas 'alta' discrepan -> degradado a media):")
        for modelo, cuantas in conflictos.items():
            print(f"  {modelo}: {cuantas} capacidades distintas")

    print(f"\nGuardado en: {SALIDA_PATH}")


if __name__ == "__main__":
    main()
