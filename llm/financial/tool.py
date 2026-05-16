"""tool.py.

----------
LangChain tool para consultas financieras deterministas vía SQLite.

Define ``query_financiero``, un ``@tool`` de LangChain que expone consultas
a la tabla ``metricas_financieras`` de Hoteles Estelar como una herramienta
invocable por el LLM con parámetros estructurados (sección, año, concepto).
"""

import json

from langchain_core.tools import tool

from llm.financial.db import ejecutar_consulta


@tool
def query_financiero(
    seccion: str | None = None,
    anio: int | None = None,
    concepto: str | None = None,
) -> str:
    """Consulta métricas financieras de Hoteles Estelar desde la base local.

    Útil cuando el colaborador pregunta por cifras financieras, indicadores,
    comparaciones entre años, márgenes, ratios, deuda, balance general,
    estado de resultados o flujo de caja.

    Los valores monetarios están en millones de COP.

    Parámetros:
        seccion: Categoría financiera
            (ej: ``"Estado de resultados"``, ``"Balance general"``,
            ``"Flujo de caja"``, ``"EBITDA"``, ``"Ingresos"``).
            Usar ``None`` para buscar en todas las secciones.
        anio: Año fiscal (2019—2024). Usar ``None`` para todos los años.
        concepto: Nombre de la métrica
            (ej: ``"EBITDA"``, ``"Ingresos"``, ``"Utilidad neta"``,
            ``"Deuda/EBITDA"``, ``"Margen bruto"``).
            La búsqueda es parcial, no necesita el nombre exacto.

    Devuelve:
        str: JSON con lista de resultados. Cada elemento tiene los campos
        ``anio``, ``seccion``, ``concepto``, ``valor_num``, ``valor_raw``,
        ``unidad``, ``es_ratio``. Vacío (``"[]"``) si no encuentra datos.
    """
    resultados = ejecutar_consulta(seccion=seccion, anio=anio, concepto=concepto)
    return json.dumps(resultados, ensure_ascii=False)
