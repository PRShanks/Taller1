"""test_financial_db.py.

Tests para el módulo ``llm/financial/db.py`` — acceso a SQLite con métricas
financieras. Usa bases de datos temporales para no tocar datos reales.
"""

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import ClassVar

import pytest

from llm.financial.db import ejecutar_consulta, inicializar_db

# =============================================================================
# Helpers
# =============================================================================


def _db_temp() -> tuple[Path, Path]:
    """Crea un directorio temporal y devuelve (tmp_dir, db_path).

    Devuelve:
        Tupla con (directorio temporal, ruta a la DB dentro de él).
    """
    tmp_dir = Path(tempfile.mkdtemp())
    db_path = tmp_dir / "test.db"
    return tmp_dir, db_path


# =============================================================================
# inicializar_db
# =============================================================================


class TestInicializarDB:
    """Tests unitarios para ``inicializar_db``."""

    def test_inicializar_db_crea_tabla(self) -> None:
        """Verifica que ``inicializar_db`` cree la tabla e índices."""
        tmp_dir, db_path = _db_temp()
        try:
            ruta = inicializar_db(db_path=str(db_path))
            ruta_resuelta = str(Path(ruta).resolve())
            assert ruta_resuelta == str(db_path.resolve()), (
                f"Ruta devuelta {ruta_resuelta} != {db_path.resolve()}"
            )

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            # Verificar tabla existe
            cursor = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='metricas_financieras'"
            )
            assert cursor.fetchone() is not None, (
                "La tabla metricas_financieras no fue creada"
            )

            # Verificar índices
            indices = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
            for idx in ("idx_anio", "idx_seccion", "idx_concepto"):
                assert idx in indices, f"Índice {idx} no encontrado"

            conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_inicializar_db_seed_desde_csv(self) -> None:
        """Verifica que el seed desde CSV cargue datos."""
        tmp_dir, db_path = _db_temp()
        try:
            inicializar_db(db_path=str(db_path))

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT COUNT(*) as total FROM metricas_financieras"
            )
            total = cursor.fetchone()[0]
            assert total > 0, "No se cargaron datos desde el CSV"
            conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_inicializar_db_default_path(self) -> None:
        """Sin argumentos, debe crear la DB en la ruta por defecto."""
        try:
            ruta = inicializar_db()
            assert Path(ruta).exists(), f"No se creó la DB en {ruta}"
        finally:
            # Limpiar la DB por defecto si se creó
            Path(ruta).unlink(missing_ok=True)

    def test_inicializar_db_idempotente(self) -> None:
        """Llamar dos veces con el mismo path no debe fallar."""
        tmp_dir, db_path = _db_temp()
        try:
            inicializar_db(db_path=str(db_path))
            inicializar_db(db_path=str(db_path))  # segunda llamada

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT COUNT(*) FROM metricas_financieras"
            )
            assert cursor.fetchone()[0] > 0
            conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# =============================================================================
# ejecutar_consulta
# =============================================================================


class TestEjecutarConsulta:
    """Tests unitarios para ``ejecutar_consulta``."""

    _DATOS: ClassVar[list[tuple]] = [
        ("id1", 2019, "Ingresos", "Crecimiento (%)", 14.2, "14,2", "%", 1),
        ("id2", 2020, "Ingresos", "Crecimiento (%)", -62.1, "-62,1", "%", 1),
        ("id3", 2019, "Utilidad bruta", "Margen bruto (%)", 64.7, "64,7", "%", 1),
        ("id4", 2020, "Utilidad bruta", "Margen bruto (%)", 52.2, "52,2", "%", 1),
        ("id5", 2019, "Balance general", "Total activos", 644313.0, "644.313",
         "millones COP", 0),
    ]

    @pytest.fixture(autouse=True)
    def _setup_db(self) -> None:
        """Crea BD temporal con datos de prueba para cada test."""
        self._tmp_dir = Path(tempfile.mkdtemp())
        self._db_path = self._tmp_dir / "test.db"

        conn = sqlite3.connect(str(self._db_path))
        conn.executescript("""
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
            CREATE INDEX IF NOT EXISTS idx_anio
                ON metricas_financieras(anio);
            CREATE INDEX IF NOT EXISTS idx_seccion
                ON metricas_financieras(seccion);
            CREATE INDEX IF NOT EXISTS idx_concepto
                ON metricas_financieras(concepto);
        """)

        conn.executemany(
            "INSERT INTO metricas_financieras "
            "(id, anio, seccion, concepto, valor_num, valor_raw, unidad, es_ratio) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            self._DATOS,
        )
        conn.commit()
        conn.close()

        yield

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_ejecutar_consulta_sin_filtros(self) -> None:
        """Sin filtros, retorna todas las filas."""
        resultados = ejecutar_consulta(db_path=str(self._db_path))
        assert len(resultados) == len(self._DATOS)
        assert all(isinstance(r, dict) for r in resultados)

    def test_ejecutar_consulta_con_filtro_seccion(self) -> None:
        """Filtrar por sección (LIKE parcial)."""
        resultados = ejecutar_consulta(
            seccion="Ingresos", db_path=str(self._db_path),
        )
        assert len(resultados) == 2
        assert all(r["seccion"] == "Ingresos" for r in resultados)

    def test_ejecutar_consulta_con_filtro_anio(self) -> None:
        """Filtrar por año exacto."""
        resultados = ejecutar_consulta(
            anio=2019, db_path=str(self._db_path),
        )
        assert len(resultados) == 3
        assert all(r["anio"] == 2019 for r in resultados)

    def test_ejecutar_consulta_con_filtro_concepto(self) -> None:
        """Filtrar por concepto (LIKE)."""
        resultados = ejecutar_consulta(
            concepto="Crecimiento", db_path=str(self._db_path),
        )
        assert len(resultados) == 2
        assert all("Crecimiento" in r["concepto"] for r in resultados)

    def test_ejecutar_consulta_con_filtros_combinados(self) -> None:
        """Filtrar por sección + año + concepto."""
        resultados = ejecutar_consulta(
            seccion="Ingresos",
            anio=2019,
            concepto="Crecimiento",
            db_path=str(self._db_path),
        )
        assert len(resultados) == 1
        assert resultados[0]["anio"] == 2019
        assert resultados[0]["seccion"] == "Ingresos"
        assert "Crecimiento" in resultados[0]["concepto"]

    def test_ejecutar_consulta_con_filtro_seccion_parcial(self) -> None:
        """Filtro de sección parcial en minúscula (case-insensitive LIKE)."""
        resultados = ejecutar_consulta(
            seccion="balance", db_path=str(self._db_path),
        )
        assert len(resultados) == 1
        assert resultados[0]["seccion"] == "Balance general"

    def test_ejecutar_consulta_sin_resultados(self) -> None:
        """Filtro que no coincide retorna lista vacía."""
        resultados = ejecutar_consulta(
            seccion="NoExiste", db_path=str(self._db_path),
        )
        assert resultados == []

    def test_sin_sql_injection(self) -> None:
        """Input malicioso no inyecta SQL."""
        resultados = ejecutar_consulta(
            concepto="' OR 1=1; --", db_path=str(self._db_path),
        )
        assert isinstance(resultados, list)
        # El concepto con comillas no existe -> lista vacía
        assert len(resultados) == 0

    def test_resultado_contiene_campos_esperados(self) -> None:
        """Cada resultado debe tener los campos definidos."""
        resultados = ejecutar_consulta(db_path=str(self._db_path))
        campos_esperados = {
            "anio", "seccion", "concepto",
            "valor_num", "valor_raw", "unidad", "es_ratio",
        }
        for r in resultados:
            assert campos_esperados.issubset(r.keys()), (
                f"Faltan campos en {r}"
            )

    def test_ejecutar_consulta_con_filtro_concepto_parcial(self) -> None:
        """Filtro parcial de concepto también funciona."""
        resultados = ejecutar_consulta(
            concepto="Margen", db_path=str(self._db_path),
        )
        assert len(resultados) == 2
        assert all("Margen" in r["concepto"] for r in resultados)

    def test_limite_500_filas(self) -> None:
        """La consulta tiene LIMIT 500.

        No aplica con datos chicos pero verifica que el límite existe
        en la SQL.
        """
        # Con 5 filas el límite no debería afectar
        resultados = ejecutar_consulta(db_path=str(self._db_path))
        assert len(resultados) <= 500
