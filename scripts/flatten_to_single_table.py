"""
flatten_financiero.py
=====================
Lee directamente:
    data/estelar_reportes/reporte-financiero-completo.md

Genera:
    data/estelar_reportes/metricas_financieras.csv

Una fila = un dato atómico:
    id | anio | seccion | concepto | valor_num | valor_raw | unidad | es_ratio

Deduplicación: cuando la misma cifra aparece en varias secciones del .md,
se conserva solo la ocurrencia de la sección más específica.
"""

from pathlib import Path
from bs4 import BeautifulSoup
from collections import Counter
import csv, re, uuid

# ── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
INPUT_FILE  = BASE_DIR / "data" / "estelar_reportes" / "reporte-financiero-completo.md"
OUTPUT_FILE = BASE_DIR / "data" / "estelar_reportes" / "metricas_financieras.csv"

YEARS = {"2019", "2020", "2021", "2022", "2023", "2024"}

# Prioridad de secciones para deduplicación (menor número = más específica = se conserva)
PRIORIDAD_SECCION = {
    "Estado de resultados":                          1,
    "Balance general":                               2,
    "Flujo de caja":                                 3,
    "Capital de trabajo neto":                       4,
    "Activos de largo plazo":                        5,
    "Otros activos y otros pasivos no operacionales":6,
    "Días de capital de trabajo":                    7,
    "CapEx y Capital de trabajo / Ingresos":         8,
    "EBITDA vs Flujo operativo":                     9,
    "Ingresos":                                     10,
    "EBITDA":                                       11,
    "Deuda":                                        12,
    "Utilidad bruta":                               13,
    "Gastos operacionales":                         14,
    "Capital de trabajo":                           15,
}

# ── Normalización numérica ────────────────────────────────────────────────────
def normalizar(raw: str) -> float | None:
    """
    Convierte cualquier formato numérico del reporte a float estándar.

    Casos presentes en el .md:
      '303.068'  → 303068.0   (punto = separador de miles, 3 decimales → entero)
      '-9.364'   → -9364.0    (ídem con negativo)
      '10.2'     → 10.2       (punto = decimal real, solo 1 decimal)
      '-3,5'     → -3.5       (coma = decimal)
      '5,1'      → 5.1        (ídem)
      '-28.6'    → -28.6      (punto decimal real, no miles)
      '0'        → 0.0
    """
    s = raw.strip()
    if not s or s in ("-", "N/A", "n/a", ""):
        return None

    s = s.rstrip("x%").strip()

    if "," in s:
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    m = re.match(r"^(-?)(\d+)\.(\d+)$", s)
    if m:
        signo, entero, decimales = m.groups()
        if len(decimales) == 3:
            s = signo + entero + decimales
    try:
        return float(s)
    except ValueError:
        return None


def detectar_unidad(concepto: str, raw: str) -> str:
    c = concepto.lower()
    r = raw.strip()
    if "%" in r or "(%)" in c or "margen" in c or "crecimiento" in c or "/ingresos" in c:
        return "%"
    if r.endswith("x") or "(x)" in c or "/ebitda" in c:
        return "x"
    if "días" in c or "dias" in c:
        return "días"
    return "millones COP"


def es_ratio(concepto: str, raw: str) -> bool:
    señales_c = ["(%)", "margen", "crecimiento", "/ingresos", "(x)", "/ebitda", "días", "dias"]
    señales_r = ["%", "x", ","]
    return (any(s in concepto.lower() for s in señales_c) or
            any(s in raw for s in señales_r))


def limpiar_texto(t: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", t).strip()


# ── Parseo de tablas HTML ─────────────────────────────────────────────────────
def parse_tabla(soup_table) -> tuple[list[str], list[list[str]]]:
    headers = [limpiar_texto(th.get_text()) for th in soup_table.find_all("th")]
    filas = []
    for tr in soup_table.find_all("tr"):
        celdas = [limpiar_texto(td.get_text()) for td in tr.find_all("td")]
        if celdas:
            filas.append(celdas)
    return headers, filas


# ── Construcción de filas de salida ──────────────────────────────────────────
def hacer_fila(anio, seccion, concepto, raw) -> dict:
    val = normalizar(raw)
    unidad = detectar_unidad(concepto, raw)
    return {
        "id":        str(uuid.uuid4()),
        "anio":      int(anio),
        "seccion":   seccion,
        "concepto":  concepto,
        "valor_num": val if val is not None else "",
        "valor_raw": raw,
        "unidad":    unidad,
        "es_ratio":  str(es_ratio(concepto, raw)).lower(),
    }


def procesar_tabla_long(headers, filas, seccion) -> list[dict]:
    rows = []
    conceptos = headers[1:]
    for fila in filas:
        if not fila or not fila[0].strip():
            continue
        anio = fila[0].strip()
        if anio not in YEARS:
            continue
        for i, concepto in enumerate(conceptos):
            raw = fila[i + 1].strip() if i + 1 < len(fila) else ""
            if raw:
                rows.append(hacer_fila(anio, seccion, concepto, raw))
    return rows


def procesar_tabla_wide(headers, filas, seccion) -> list[dict]:
    rows = []
    year_cols = headers[1:]
    for fila in filas:
        if not fila or not fila[0].strip():
            continue
        concepto = fila[0].strip()
        for j, yr in enumerate(year_cols):
            anio = yr.strip()
            if anio not in YEARS:
                continue
            raw = fila[j + 1].strip() if j + 1 < len(fila) else ""
            if raw:
                rows.append(hacer_fila(anio, seccion, concepto, raw))
    return rows


def detectar_formato(headers: list[str]) -> str:
    if not headers:
        return "long"
    if headers[0].strip() == "" or headers[0].strip() in YEARS:
        return "wide"
    if len(headers) > 1 and headers[1].strip() in YEARS:
        return "wide"
    return "long"


# ── Deduplicación ─────────────────────────────────────────────────────────────
def deduplicar(filas: list[dict]) -> list[dict]:
    """
    Cuando la misma combinación (anio, concepto, valor_num) aparece en
    varias secciones, conserva solo la de mayor prioridad (número más bajo).
    El orden de las filas se mantiene estable.
    """
    visto: dict[tuple, int] = {}

    for i, fila in enumerate(filas):
        clave = (fila["anio"], fila["concepto"], fila["valor_num"])
        prioridad_actual = PRIORIDAD_SECCION.get(fila["seccion"], 99)

        if clave not in visto:
            visto[clave] = i
        else:
            prioridad_guardada = PRIORIDAD_SECCION.get(filas[visto[clave]]["seccion"], 99)
            if prioridad_actual < prioridad_guardada:
                visto[clave] = i

    indices_ganadores = set(visto.values())
    return [f for i, f in enumerate(filas) if i in indices_ganadores]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Leyendo: {INPUT_FILE}")
    content = INPUT_FILE.read_text(encoding="utf-8")

    lineas = content.splitlines()
    filas_salida: list[dict] = []

    seccion_actual    = ""
    subseccion_actual = ""
    buffer_tabla      = []
    dentro_tabla      = False

    for linea in lineas:
        m2 = re.match(r"^## (.+)", linea)
        if m2:
            seccion_actual = re.sub(r"^\d+\.\s*", "", m2.group(1).strip())
            subseccion_actual = seccion_actual
            continue

        m3 = re.match(r"^### (.+)", linea)
        if m3:
            subseccion_actual = m3.group(1).strip()
            continue

        if "<table>" in linea.lower():
            dentro_tabla = True
            buffer_tabla = [linea]
            continue

        if dentro_tabla:
            buffer_tabla.append(linea)
            if "</table>" in linea.lower():
                dentro_tabla = False
                html_tabla = "\n".join(buffer_tabla)
                soup = BeautifulSoup(html_tabla, "html.parser")
                tabla = soup.find("table")
                if tabla:
                    headers, filas = parse_tabla(tabla)
                    fmt = detectar_formato(headers)
                    seccion_csv = subseccion_actual if subseccion_actual else seccion_actual
                    if fmt == "long":
                        filas_salida.extend(procesar_tabla_long(headers, filas, seccion_csv))
                    else:
                        filas_salida.extend(procesar_tabla_wide(headers, filas, seccion_csv))
                buffer_tabla = []

    # ── Deduplicar ────────────────────────────────────────────────────────────
    total_bruto = len(filas_salida)
    filas_salida = deduplicar(filas_salida)
    total_limpio = len(filas_salida)

    # ── Escribir CSV ──────────────────────────────────────────────────────────
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAMPOS = ["id", "anio", "seccion", "concepto", "valor_num", "valor_raw", "unidad", "es_ratio"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        writer.writerows(filas_salida)

    print(f"\n✅ CSV generado: {OUTPUT_FILE}")
    print(f"   Filas brutas         : {total_bruto}")
    print(f"   Duplicados eliminados: {total_bruto - total_limpio}")
    print(f"   Filas finales        : {total_limpio}")

    stats = Counter(r["seccion"] for r in filas_salida)
    print("\n── Filas por sección ───────────────────────────────────────────")
    for sec, n in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"   {sec:<45} {n:>4} filas")

    print("\n── Muestra (6 filas) ───────────────────────────────────────────")
    for r in filas_salida[:6]:
        print(f"   [{r['anio']}] {r['seccion']:<30} | {r['concepto']:<35} "
              f"| {r['valor_num']} {r['unidad']}")


if __name__ == "__main__":
    main()