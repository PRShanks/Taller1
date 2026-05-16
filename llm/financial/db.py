"""db.py.

Módulo de acceso a SQLite para métricas financieras.

Proporciona inicialización de la base de datos (creación de tabla, índices
y seed desde CSV) y consultas parametrizadas con filtros por sección, año
y concepto.

Todas las consultas usan parámetros ``?`` para prevenir inyección SQL.
"""

import csv
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas por defecto (resueltas desde la raíz del proyecto)
_RAIZ = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB_PATH = _RAIZ / "data" / "processed" / "metricas_financieras.db"
_CSV_PATH = _RAIZ / "data" / "estelar_reportes" / "metricas_financieras.csv"

# ---------------------------------------------------------------------------
# SQL DDL y consultas
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metricas_financieras (
    id TEXT PRIMARY KEY,
    anio INTEGER NOT NULL,
    seccion TEXT NOT NULL,
    concepto TEXT NOT NULL,
    valor_num REAL,
    valor_raw TEXT,
    unidad TEXT NOT NULL,
    es_ratio INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_anio ON metricas_financieras(anio);
CREATE INDEX IF NOT EXISTS idx_seccion ON metricas_financieras(seccion);
CREATE INDEX IF NOT EXISTS idx_concepto ON metricas_financieras(concepto);
"""

_SELECT_SQL = """
SELECT anio, seccion, concepto, valor_num, valor_raw, unidad, es_ratio
FROM metricas_financieras
WHERE (? IS NULL OR seccion LIKE ?)
  AND (? IS NULL OR anio = ?)
  AND (? IS NULL OR concepto LIKE '%' || ? || '%')
ORDER BY anio, seccion
LIMIT 500
"""


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------


def inicializar_db(db_path: str | Path | None = None) -> str:
    """Crea DB + seed desde CSV si no existe o CSV es más nuevo.

    Parámetros:
        db_path: Ruta a la DB. Si es ``None``, usa la variable de entorno
            ``FINANCIAL_DB_PATH`` o el default
            ``data/processed/metricas_financieras.db``.

    Devuelve:
        Ruta absoluta a la base de datos.
    """
    if db_path is None:
        db_path = os.getenv("FINANCIAL_DB_PATH", str(_DEFAULT_DB_PATH))

    db_path = Path(db_path).resolve()
    csv_path = Path(_CSV_PATH).resolve()

    # Crear directorio padre si no existe
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Verificar si necesita seed ANTES de conectar: en Windows, connect()
    # crea el archivo inmediatamente, lo que haría que db_path.exists()
    # siempre devuelva True después de la conexión.
    necesita_seed = not db_path.exists()
    if not necesita_seed and csv_path.exists():
        db_mtime = db_path.stat().st_mtime
        csv_mtime = csv_path.stat().st_mtime
        necesita_seed = csv_mtime > db_mtime

    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    try:
        # Crear tablas (siempre, por si la DB está vacía o es nueva)
        conn.executescript(_SCHEMA_SQL)

        if necesita_seed and csv_path.exists():
            _seed_desde_csv(conn, csv_path)
    except sqlite3.Error as exc:
        logger.warning("Error al inicializar DB (%s): %s", db_path, exc)
    finally:
        conn.close()

    return str(db_path)


def ejecutar_consulta(
    seccion: str | None = None,
    anio: int | None = None,
    concepto: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Ejecuta SELECT parametrizado contra ``metricas_financieras``.

    Todos los filtros son opcionales. Si se omite ``db_path``, se llama a
    ``inicializar_db()`` para obtener la ruta por defecto.

    Parámetros:
        seccion:  Filtrar por sección (LIKE case-insensitive).
        anio:     Filtrar por año exacto.
        concepto: Filtrar por concepto (LIKE case-insensitive).
        db_path:  Ruta a la DB. Si es ``None``, se usa la ruta por defecto.

    Devuelve:
        Lista de diccionarios con los resultados. Vacía si no hay.
    """
    if db_path is None:
        db_path = inicializar_db()

    resultados: list[dict] = []
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    try:
        # Preparar parámetros: para LIKE se envuelve con % si no es None
        seccion_like = f"%{seccion}%" if seccion else None

        cursor = conn.execute(
            _SELECT_SQL,
            [seccion, seccion_like, anio, anio, concepto, concepto],
        )

        for row in cursor.fetchall():
            resultados.append({
                "anio": row["anio"],
                "seccion": row["seccion"],
                "concepto": row["concepto"],
                "valor_num": row["valor_num"],
                "valor_raw": row["valor_raw"],
                "unidad": row["unidad"],
                "es_ratio": bool(row["es_ratio"]),
            })
    except sqlite3.Error as exc:
        logger.warning("Error al ejecutar consulta: %s", exc)
    finally:
        conn.close()

    return resultados


# ---------------------------------------------------------------------------
# Funciones privadas
# ---------------------------------------------------------------------------


def _seed_desde_csv(conn: sqlite3.Connection, csv_path: Path) -> None:
    """Lee el CSV e inserta datos en la tabla.

    Parámetros:
        conn:     Conexión abierta a SQLite.
        csv_path: Ruta absoluta al archivo CSV.
    """
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        filas = []
        for row in reader:
            es_ratio = 1 if row["es_ratio"].strip().lower() == "true" else 0
            valor_num = _parsear_valor_num(row.get("valor_num", ""))
            filas.append((
                row["id"],
                int(row["anio"]),
                row["seccion"],
                row["concepto"],
                valor_num,
                row.get("valor_raw", ""),
                row["unidad"],
                es_ratio,
            ))

    if filas:
        conn.executemany(
            "INSERT OR REPLACE INTO metricas_financieras "
            "(id, anio, seccion, concepto, valor_num, valor_raw, unidad, es_ratio) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )
        conn.commit()


def _parsear_valor_num(valor: str) -> float | None:
    """Convierte string a ``float``, devuelve ``None`` si no es posible.

    Parámetros:
        valor: String con el valor numérico.

    Devuelve:
        ``float`` o ``None`` si el valor no es convertible.
    """
    valor = valor.strip()
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None
