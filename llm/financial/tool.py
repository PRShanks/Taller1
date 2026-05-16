"""tool.py.

----------
LangChain tool para consultas financieras deterministas vía SQLite.

Define ``query_financiero``, un ``@tool`` de LangChain que expone consultas
a la tabla ``metricas_financieras`` de Hoteles Estelar como una herramienta
invocable por el LLM con parámetros estructurados (sección, año, concepto).
"""

from langchain_core.tools import tool

from llm.financial.db import ejecutar_consulta

_MAX_FILAS_RESPUESTA = 50  # límite para no saturar el contexto del LLM


def _formatear_resultados(resultados: list[dict]) -> str:
    """Convierte los resultados de la DB en texto legible para el LLM.

    En lugar de devolver JSON crudo, produce texto tabular que el LLM
    puede interpretar directamente sin parsing adicional.

    Parámetros:
        resultados: Lista de dicts con los campos de ``metricas_financieras``.

    Devuelve:
        Texto formateado con los resultados o mensaje de vacío.
    """
    if not resultados:
        return (
            "No se encontraron datos financieros para los filtros indicados. "
            "Intenta ampliar la búsqueda: omite 'seccion' o usa un 'concepto' "
            "más corto (ej: 'EBITDA' en lugar de 'Margen EBITDA (%)' )."
        )

    truncado = len(resultados) > _MAX_FILAS_RESPUESTA
    filas = resultados[:_MAX_FILAS_RESPUESTA]

    lineas = [f"Datos financieros Hoteles Estelar ({len(filas)} registros):"]
    lineas.append("-" * 65)

    for r in filas:
        # valor_raw preserva el formato original del reporte (ej. "303.068")
        # valor_num es el float limpio — usamos raw para la presentación
        valor = r["valor_raw"] if r["valor_raw"] else str(r["valor_num"])
        lineas.append(
            f"[{r['anio']}] {r['seccion']} › {r['concepto']}: "
            f"{valor} {r['unidad']}"
        )

    if truncado:
        lineas.append(
            f"\n⚠ Resultado truncado: se muestran {_MAX_FILAS_RESPUESTA} de "
            f"{len(resultados)} registros. Filtra por 'seccion', 'anio' o "
            "'concepto' para obtener el subconjunto que necesitas."
        )

    return "\n".join(lineas)


@tool
def query_financiero(
    seccion: str | None = None,
    anio: int | None = None,
    concepto: str | None = None,
) -> str:
    """Consulta métricas financieras históricas de Hoteles Estelar (2019–2024).

    Úsala cuando el usuario pregunte por cifras financieras, indicadores,
    comparaciones entre años, márgenes, ratios, deuda, balance general,
    estado de resultados o flujo de caja.

    CUÁNDO USAR ESTA TOOL:
    - Valores absolutos: ingresos totales, EBITDA, utilidad neta, deuda, CapEx.
    - Ratios y márgenes: margen bruto, margen EBITDA, Deuda/EBITDA.
    - Comparaciones entre años: "¿cómo evolucionó X entre 2022 y 2024?".
    - Flujo de caja, capital de trabajo, balance de activos/pasivos.
    - Días de rotación: cartera, inventario, proveedores.

    CUÁNDO NO USAR ESTA TOOL:
    - Preguntas sobre servicios, habitaciones, políticas o procesos internos
      (esa información está en el contexto RAG).
    - Proyecciones o presupuestos posteriores a 2024 (no hay datos).

    ── PARÁMETRO: seccion ──────────────────────────────────────────────────
    Filtra por categoría financiera. Usa None para buscar en todo.

    SECCIONES DISPONIBLES y sus conceptos:

    "Estado de resultados"
        Tabla P&G completa. Conceptos disponibles:
        Ingresos, Δ Ingresos, Costos, Utilidad bruta, Margen bruto,
        Gastos de administración, Gastos de ventas, Otros gastos operacionales,
        Total gastos operacionales, Gastos operacionales/Ingresos,
        Otras ganancias/perdidas, Otros ingresos operacionales,
        Utilidad operativa, D&A, EBITDA, Margen EBITDA,
        Ingresos financieros, Costos financieros, Otros financieros (neto),
        Coberturas, EBITDA/Costos financieros, Utilidades en subsidiarias,
        Otros ingresos no operacionales, Otros egresos no operacionales,
        UAI, Impuestos, Utilidad neta, Margen Neto, Deuda/EBITDA.
        → Usar para: P&G completo, cualquier línea del estado de resultados.

    "Balance general"
        Activos, pasivos y patrimonio. Conceptos disponibles:
        Caja y bancos, Inversiones, Cuentas por cobrar, Inventario,
        Activos biológicos CP, Impuestos a favor, Otros activos corrientes,
        Total activos corrientes, PPyE, Intangibles, Activos biológicos LP,
        Intercompanies, Otras CxC no corrientes, Otros activos no corrientes,
        Total activos no corrientes, Total activos, Deuda, Proveedores,
        Obligaciones laborales, Impuestos por pagar, Provisiones,
        Otros pasivos, Total pasivos, Capitales, Reservas,
        Resultado de Ej. Ant., Superavit, Total patrimonio,
        Check ecuación contable.
        → Usar para: estructura financiera, activos/pasivos, patrimonio.

    "Flujo de caja"
        Flujo completo. Conceptos disponibles:
        (+) EBITDA, (-) Impuestos, (-) Δ Capital de trabajo neto,
        (-) Δ CapEx, (1) Flujo de caja operativo, (+) Δ Deuda,
        (-) Costos financieros, (2) Flujo financiero, (-) Δ OAOP neto,
        (+) Δ Patrimonio, (+) Ingresos financieros,
        (+) Otros Ingresos/Egresos no operacionales, (3) Flujo no operativo,
        (1+2+3) Flujo del periodo, Caja inicial, Caja final, Check caja.
        → Usar para: generación de caja, variación de caja, flujo operativo.

    "Capital de trabajo neto"
        Conceptos: Capital de trabajo neto, Activos Wk, Pasivos Wk,
        Capital de trabajo/Ingresos (%), Δ Capital de trabajo neto.
        → Usar para: WK neto, variación de capital de trabajo.

    "Activos de largo plazo"
        Conceptos: Activos fijos y CapEx, Δ CapEx.
        → Usar para: inversión en activos fijos, variación de CapEx.

    "Días de capital de trabajo"
        Conceptos: Dias cuentas por cobrar, Dias inventario, Dias proveedores.
        → Usar para: eficiencia operativa, ciclo de conversión de caja.

    "EBITDA vs Flujo operativo"
        Conceptos: Flujo de caja operativo, Flujo operativo/EBITDA (%).
        → Usar para: conversión de EBITDA a caja operativa.

    "CapEx y Capital de trabajo / Ingresos"
        Conceptos: % CapEx/Ingresos, % Capital de trabajo/Ingresos.
        → Usar para: ratios de inversión y eficiencia sobre ingresos.

    "Otros activos y otros pasivos no operacionales"
        Conceptos: Otros activos no operacionales, Otros pasivos no operacionales,
        OAOP neto, Δ OAOP neto.
        → Usar para: activos/pasivos fuera de la operación principal.

    "Ingresos"  ← SOLO contiene: Crecimiento (%)
        → Usar para: tasa de crecimiento de ingresos año a año.
        ⚠ Para el valor absoluto de ingresos en COP, usar "Estado de resultados".

    "EBITDA"  ← SOLO contiene: Margen EBITDA (%)
        → Usar para: margen EBITDA como porcentaje de ingresos.
        ⚠ Para el valor absoluto del EBITDA en COP, usar "Estado de resultados".

    "Utilidad bruta"  ← SOLO contiene: Margen bruto (%)
        → Usar para: margen bruto como porcentaje de ingresos.
        ⚠ Para el valor absoluto, usar "Estado de resultados".

    "Gastos operacionales"
        Conceptos: Gastos operacionales (COP), Gastos operacionales/Ingresos (%).
        → Usar para: nivel de gastos operativos absolutos y su peso relativo.

    "Deuda"  ← SOLO contiene: Deuda/EBITDA (x)
        → Usar para: ratio de apalancamiento (veces).
        ⚠ Para el saldo absoluto de deuda en COP, usar "Balance general".

    "Capital de trabajo"  ← SOLO contiene: Deuda/Capital de trabajo
        → Usar para: ratio de deuda sobre capital de trabajo.

    ── PARÁMETRO: anio ─────────────────────────────────────────────────────
    Año fiscal exacto. Valores disponibles: 2019, 2020, 2021, 2022, 2023, 2024.
    Usar None para obtener la serie histórica completa (todos los años).

    ── PARÁMETRO: concepto ─────────────────────────────────────────────────
    Nombre parcial de la métrica, búsqueda case-insensitive.
    No necesitas el nombre exacto — "EBITDA" encuentra "Margen EBITDA (%)",
    "caja" encuentra "Caja y bancos" y "Flujo de caja operativo".
    OJO: "EBITDA", "Ingresos" y "Deuda" son también nombres de sección —
    si quieres su resumen use 'seccion'; si quieres el concepto dentro de
    "Estado de resultados", úsalos aquí junto con seccion="Estado de resultados".

    ── UNIDADES en los resultados ──────────────────────────────────────────
    "millones COP" → valor monetario en millones de pesos colombianos.
    "%"            → porcentaje (márgenes, crecimientos, ratios).
    "x"            → veces (ej: Deuda/EBITDA = 5.1x → 5.1 veces el EBITDA).
    "días"         → días de rotación (cartera, inventario, proveedores).

    Devuelve:
        Texto con los resultados formateados listos para incluir en la
        respuesta al usuario. Si no hay datos, lo indica con sugerencias
        para ampliar la búsqueda.
    """
    resultados = ejecutar_consulta(seccion=seccion, anio=anio, concepto=concepto)
    return _formatear_resultados(resultados)