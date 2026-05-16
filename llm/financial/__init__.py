"""financial.

Package de consulta financiera estructurada para Hoteles Estelar Chat.

Proporciona acceso a métricas financieras vía SQLite, reemplazando/ampliando
la recuperación RAG con datos numéricos tabulares.

Módulos:
    db:     Inicialización y consultas parametrizadas a SQLite.
    tool:   Herramienta LangChain para invocar consultas desde el LLM (Batch 2).

Exporta:
    inicializar_db   — Crea DB + seed desde CSV si es necesario.
    ejecutar_consulta — Consulta parametrizada con filtros por sección, año
                        y concepto.
"""

from llm.financial.db import ejecutar_consulta, inicializar_db

__all__ = [
    "ejecutar_consulta",
    "inicializar_db",
]
