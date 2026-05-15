# =============================================================================
# Makefile — Hoteles Estelar Chat Assistant
# =============================================================================
# Uso: make <target>
# Help: make help
# =============================================================================

.PHONY: help setup venv sync lock dev \
       run run-qa run-summary run-faq run-data run-memory \
       lint format typecheck \
       test test-verbose test-cov \
       clean clean-data clean-cache clean-all \
       check install-scraping install-hooks pre-commit pre-commit-autoupdate \
       ingest reindex

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
PYTHON       := python3
VENV         := .venv
UV           := uv
STREAMLIT    := streamlit
PYTEST       := pytest
RUFF         := ruff
MYPY         := mypy
SRC_DIRS     := llm app scripts
TEST_DIR     := tests
DATA_RAW     := data/estelar_reportes
DATA_PROC    := data/processed

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Mostrar este mensaje de ayuda
	@echo "Makefile — Hoteles Estelar Chat Assistant"
	@echo ""
	@echo "Uso: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}' | \
		sort

# ---------------------------------------------------------------------------
# Setup e Instalación
# ---------------------------------------------------------------------------
setup: venv sync install-hooks ## Setup completo: crear venv + instalar dependencias + hooks
	@echo "✓ Proyecto listo. Ejecuta 'make dev' para iniciar."

venv: ## Crear entorno virtual con Python 3.12
	$(UV) venv --python 3.12
	@echo "✓ Entorno virtual creado en $(VENV)/"

sync: ## Instalar/sincronizar dependencias desde pyproject.toml
	$(UV) sync
	@echo "✓ Dependencias sincronizadas."

lock: ## Regenerar uv.lock (después de cambios manuales en pyproject.toml)
	$(UV) lock
	@echo "✓ Lockfile actualizado."

# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
dev: ## Iniciar dashboard de Streamlit
	$(UV) run $(STREAMLIT) run app/dashboard.py

run: dev ## Alias para 'dev'

run-qa: ## Ejecutar Q&A chain standalone
	$(UV) run $(PYTHON) -m llm.qa_chain

run-summary: ## Ejecutar generador de resumen standalone
	$(UV) run $(PYTHON) -m llm.summarizer

run-faq: ## Ejecutar generador de FAQ standalone
	$(UV) run $(PYTHON) -m llm.faq_generator

run-data: ## Regenerar archivo consolidado de datos
	$(UV) run $(PYTHON) -m llm.data_loader

run-memory: ## Ejecutar demo de memoria de sesión
	$(UV) run $(PYTHON) -m llm.memory

# ---------------------------------------------------------------------------
# Scraping y extracción de datos
# ---------------------------------------------------------------------------
install-scraping: ## Instalar Playwright browsers para scraping
	$(UV) run playwright install chromium
	@echo "✓ Chromium instalado."

scrape: ## Ejecutar extracción de datos de Power BI
	$(UV) run $(PYTHON) scripts/extract_estelar_report.py

scrape-quick: ## Extracción rápida (reutiliza datos existentes)
	$(UV) run $(PYTHON) scripts/extract_estelar_report.py --skip-discovery --skip-capture

consolidate: ## Consolidar archivos .md en .txt procesado
	$(UV) run $(PYTHON) scripts/consolidar_estelar.py

ingest: ## Ingestar documentos corporativos en Supabase (primera carga)
	@echo "Ingesta de documentos a Supabase..."
	$(UV) run python -m scripts.ingestar_supabase
	@echo "Ingesta completada."

reindex: ## Reindexar documentos en Supabase (borra y recarga todo)
	@echo "Reindexando documentos en Supabase..."
	$(UV) run python -m scripts.ingestar_supabase --force
	@echo "Reindexado completado."

# ---------------------------------------------------------------------------
# Linting y Formateo
# ---------------------------------------------------------------------------
lint: ## Ejecutar ruff linter
	$(UV) run $(RUFF) check $(SRC_DIRS) $(TEST_DIR)

lint-fix: ## Ejecutar ruff linter con autocorrección
	$(UV) run $(RUFF) check --fix $(SRC_DIRS) $(TEST_DIR)

format: ## Formatear código con ruff format
	$(UV) run $(RUFF) format $(SRC_DIRS) $(TEST_DIR)

format-check: ## Verificar formato sin modificar archivos
	$(UV) run $(RUFF) format --check $(SRC_DIRS) $(TEST_DIR)

typecheck: ## Verificar tipos con mypy
	$(UV) run $(MYPY) $(SRC_DIRS) --ignore-missing-imports

check: lint format-check ## Lint + formato (sin modificar archivos)

# ---------------------------------------------------------------------------
# Pre-commit hooks
# ---------------------------------------------------------------------------
install-hooks: ## Instalar pre-commit hooks (requiere dependencias de dev)
	$(UV) run pre-commit install
	@echo "✓ Pre-commit hooks instalados. Se ejecutarán antes de cada commit."

pre-commit: ## Ejecutar todos los pre-commit hooks manualmente
	$(UV) run pre-commit run --all-files

pre-commit-autoupdate: ## Actualizar versiones de los hooks
	$(UV) run pre-commit autoupdate
	@echo "✓ Hooks actualizados a las últimas versiones."

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: ## Ejecutar tests con pytest
	$(UV) run $(PYTEST) $(TEST_DIR)/ -v

test-verbose: ## Ejecutar tests con output detallado
	$(UV) run $(PYTEST) $(TEST_DIR)/ -vv -s

test-cov: ## Ejecutar tests con reporte de cobertura
	$(UV) run $(PYTEST) $(TEST_DIR)/ --cov=llm --cov=app --cov-report=term-missing

# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------
clean-cache: ## Eliminar __pycache__ y .pyc
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cache eliminado."

clean-data: ## Eliminar datos procesados (regenerables)
	rm -rf $(DATA_PROC)
	@echo "✓ Datos procesados eliminados. Ejecuta 'make run-data' para regenerar."

clean-all: clean-cache clean-data ## Eliminar cache + datos procesados
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	@echo "✓ Limpieza completa."

nuke: clean-all ## Eliminar TODO (cache, datos, venv, lock)
	rm -rf $(VENV)
	rm -f uv.lock
	@echo "⚠ Entorno destruido. Ejecuta 'make setup' para reconstruir."