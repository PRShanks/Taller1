"""test_financial_tool.py.

Tests para el LangChain tool ``query_financiero`` del módulo
``llm/financial/tool.py``.

Usa una base de datos SQLite con datos inline para no depender
del CSV real ni contaminar datos de producción.
"""

import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest
from langchain_core.tools import BaseTool

from llm.financial.tool import query_financiero

# =============================================================================
# Datos de prueba inline (misma estructura que metricas_financieras)
# =============================================================================

_DATOS: list[tuple] = [
    ("id1", 2019, "Ingresos", "Crecimiento (%)", 14.2, "14,2", "%", 1),
    ("id2", 2020, "Ingresos", "Crecimiento (%)", -62.1, "-62,1", "%", 1),
    ("id3", 2019, "Utilidad bruta", "Margen bruto (%)", 64.7, "64,7", "%", 1),
    ("id4", 2020, "Utilidad bruta", "Margen bruto (%)", 52.2, "52,2", "%", 1),
    ("id5", 2019, "Balance general", "Total activos", 644313.0, "644.313", "millones COP", 0),
    ("id6", 2020, "EBITDA", "EBITDA", -18211.0, "-18.211", "millones COP", 0),
    ("id7", 2021, "EBITDA", "EBITDA", 24503.0, "24.503", "millones COP", 0),
]


def _crear_db_temp(db_path: Path) -> None:
    """Crea DB temporal con esquema y datos de prueba.

    Parámetros:
        db_path: Ruta donde crear la base de datos.
    """
    conn = sqlite3.connect(str(db_path))
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
        "(id, anio, seccion, concepto, valor_num, valor_raw, unidad, "
        "es_ratio) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        _DATOS,
    )
    conn.commit()
    conn.close()


# =============================================================================
# Tests — estructura del tool
# =============================================================================


class TestToolEstructura:
    """Verifica que el tool esté correctamente definido como LangChain tool."""

    def test_tool_es_base_tool(self) -> None:
        """query_financiero debe ser instancia de BaseTool."""
        assert isinstance(query_financiero, BaseTool)

    def test_tool_name(self) -> None:
        """El nombre del tool debe ser 'query_financiero'."""
        assert query_financiero.name == "query_financiero"

    def test_tool_description(self) -> None:
        """La descripción no debe estar vacía."""
        assert query_financiero.description
        assert len(query_financiero.description.strip()) > 0

    def test_tool_args(self) -> None:
        """Todos los argumentos (seccion, anio, concepto) deben ser opcionales."""
        args_schema = query_financiero.get_input_schema().model_json_schema()
        props = args_schema["properties"]
        assert "seccion" in props, "Falta argumento 'seccion'"
        assert "anio" in props, "Falta argumento 'anio'"
        assert "concepto" in props, "Falta argumento 'concepto'"

        required = args_schema.get("required", [])
        assert "seccion" not in required, "'seccion' no debería ser obligatorio"
        assert "anio" not in required, "'anio' no debería ser obligatorio"
        assert "concepto" not in required, "'concepto' no debería ser obligatorio"


# =============================================================================
# Tests — ejecución del tool con datos reales
# =============================================================================


class TestToolEjecucion:
    """Ejecuta el tool contra una base SQLite temporal con datos inline.

    Configura la variable de entorno ``FINANCIAL_DB_PATH`` para que apunte
    a la DB temporal, y la restaura al finalizar cada test.
    """

    _tmp_dir: Path
    _db_path: Path
    _env_backup: str | None = None

    @pytest.fixture(autouse=True)
    def _setup_db(self) -> None:
        """Crea BD temporal con datos de prueba antes de cada test."""
        # Backup de la env var
        self._env_backup = os.environ.get("FINANCIAL_DB_PATH")

        self._tmp_dir = Path(tempfile.mkdtemp())
        self._db_path = self._tmp_dir / "test.db"
        _crear_db_temp(self._db_path)

        # Apuntar tool a la DB temporal
        os.environ["FINANCIAL_DB_PATH"] = str(self._db_path)

        yield

        # Restaurar env var y limpiar
        if self._env_backup is not None:
            os.environ["FINANCIAL_DB_PATH"] = self._env_backup
        else:
            os.environ.pop("FINANCIAL_DB_PATH", None)

        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_tool_con_ebitda(self) -> None:
        """Buscar por concepto 'EBITDA' debe retornar 2 filas."""
        resultado = query_financiero.invoke({"concepto": "EBITDA"})
        datos = json.loads(resultado)
        assert isinstance(datos, list)
        assert len(datos) == 2
        for r in datos:
            assert "EBITDA" in r["concepto"]

    def test_tool_con_anio(self) -> None:
        """Filtrar por anio=2019 debe retornar 3 filas."""
        resultado = query_financiero.invoke({"anio": 2019})
        datos = json.loads(resultado)
        assert len(datos) == 3
        assert all(r["anio"] == 2019 for r in datos)

    def test_tool_sin_resultados(self) -> None:
        """Concepto inexistente retorna lista vacía como JSON."""
        resultado = query_financiero.invoke({"concepto": "NO_EXISTE"})
        assert resultado == "[]"

    def test_tool_sin_parametros(self) -> None:
        """Sin parámetros debe retornar todas las filas."""
        resultado = query_financiero.invoke({})
        datos = json.loads(resultado)
        assert len(datos) == len(_DATOS)

    def test_tool_resultados_tienen_campos_correctos(self) -> None:
        """Cada resultado debe contener los campos del schema esperado."""
        resultado = query_financiero.invoke({"concepto": "EBITDA"})
        datos = json.loads(resultado)
        campos_esperados = {
            "anio",
            "seccion",
            "concepto",
            "valor_num",
            "valor_raw",
            "unidad",
            "es_ratio",
        }
        for r in datos:
            assert set(r.keys()) == campos_esperados, f"Campos incorrectos en {r}"

    def test_tool_con_seccion(self) -> None:
        """Filtrar por seccion parcial debe funcionar."""
        resultado = query_financiero.invoke({"seccion": "Balance"})
        datos = json.loads(resultado)
        assert len(datos) == 1
        assert datos[0]["seccion"] == "Balance general"

    def test_tool_anio_int_en_json(self) -> None:
        """El campo 'anio' debe ser entero en el JSON."""
        resultado = query_financiero.invoke({"anio": 2019})
        datos = json.loads(resultado)
        for r in datos:
            assert isinstance(r["anio"], int), f"anio debe ser int, got {type(r['anio'])}"

    def test_tool_es_ratio_booleano(self) -> None:
        """El campo 'es_ratio' debe ser booleano en el JSON."""
        resultado = query_financiero.invoke({"concepto": "Crecimiento"})
        datos = json.loads(resultado)
        for r in datos:
            assert isinstance(r["es_ratio"], bool), (
                f"es_ratio debe ser bool, got {type(r['es_ratio'])}"
            )
            assert r["es_ratio"] is True

        # También verificar un ratio=false
        resultado2 = query_financiero.invoke({"concepto": "Total activos"})
        datos2 = json.loads(resultado2)
        for r in datos2:
            assert isinstance(r["es_ratio"], bool)
            assert r["es_ratio"] is False
