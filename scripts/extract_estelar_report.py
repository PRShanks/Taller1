"""scripts/extract_estelar_report.py.

Extracción exhaustiva de HOTELES ESTELAR (NIT 890304099)
desde el reporte Power BI embebido en:
  https://www.estrategiaenaccion.com/es/reportes

Fases:
  1. HTTP Discovery  — metadatos del modelo (páginas, entidades, medidas)
  2. UI Automation   — Playwright: navegar, filtrar empresa, recorrer páginas
  3. Parsing         — extraer datos de /querydata interceptado + aria_snapshot
  4. Markdown        — documento por año con toda la información capturada

Uso:
  uv run python scripts/extract_estelar_report.py
  uv run python scripts/extract_estelar_report.py --skip-discovery --max-pages 14
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import requests

# ── Configuración ──────────────────────────────────────────────────────────────
POWERBI_EMBED = (
    "https://app.powerbi.com/view"
    "?r=eyJrIjoiOWZmMjZiZjEtMTlmNy00OTk4LTg1NmQtYTM3MTQ2ZTA2NzUzIiwidCI6ImYyNzg0NmU4LTBhYWItNGJkZS04ZDcwLWFkZDQ2Y2FiMGUwMSJ9"
    "&pageName=110a327b235d48000067"
)
REPORT_ID = "9ff26bf1-19f7-4998-856d-a37146e06753"
API_BASE = "https://wabi-paas-1-scus-api.analysis.windows.net"

NIT = "890304099"
COMPANY_NAME = "HOTELES ESTELAR"
COMPANY_TERMS = ["HOTELES ESTELAR", "890304099", "ESTELAR"]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

FINANCIAL_CATEGORIES: dict[str, list[str]] = {
    "identificacion": [
        "nit", "razon social", "razón social", "empresa", "sociedad",
        "ciiu", "codigo", "código", "sector", "razon", "nombre",
    ],
    "estado_resultados": [
        "ingreso", "venta", "utilidad", "pérdida", "perdida",
        "ebitda", "ganancia", "gasto", "costo", "resultado",
        "margen", "operacion", "operación", "revenue", "income",
    ],
    "balance": [
        "activo", "pasivo", "patrimonio", "capital", "deuda",
        "inventario", "cartera", "caja", "efectivo",
        "obligacion", "obligación", "total asset", "liability",
    ],
    "indicadores": [
        "liquidez", "endeudamiento", "rentabilidad", "rotacion", "rotación",
        "dias", "días", "cobertura", "ratio", "índice", "indice",
        "roe", "roa", "roi", "corriente",
    ],
}

# ── Utilidades ─────────────────────────────────────────────────────────────────

def now_iso() -> str:
    """Retorna el timestamp actual en formato ISO 8601."""
    return datetime.now(UTC).isoformat()


def mkdirs(p: Path) -> Path:
    """Crea el directorio p y sus padres; retorna p."""
    p.mkdir(parents=True, exist_ok=True)
    return p


def dump_json(p: Path, obj: Any) -> None:
    """Serializa obj como JSON y lo escribe en p."""
    mkdirs(p.parent)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_text(p: Path, text: str) -> None:
    """Escribe text en p con encoding UTF-8."""
    mkdirs(p.parent)
    p.write_text(text, encoding="utf-8")


def find_company_hits(text: str) -> list[dict[str, Any]]:
    """Retorna las líneas del texto que mencionan algún término de COMPANY_TERMS."""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for t in COMPANY_TERMS:
            if t.lower() in line.lower():
                hits.append({"line": i, "term": t, "text": line.strip()})
    return hits


def categorize_field(name: str) -> str:
    """Clasifica el nombre de un campo en una de las categorías financieras."""
    name_lower = name.lower()
    for category, keywords in FINANCIAL_CATEGORIES.items():
        if any(kw in name_lower for kw in keywords):
            return category
    return "otros"


def fmt_value(v: Any, col_name: str = "") -> str:
    """Formatea un valor para presentación en markdown."""
    if v is None:
        return "N/D"
    # Intentar parsear strings que parecen numéricas
    if isinstance(v, str):
        try:
            v = float(v)
        except (ValueError, TypeError):
            return v
    if isinstance(v, (int, float)):
        f = float(v)
        col_lower = col_name.lower()
        # Columnas de margen/ratio con valores entre -5 y 5 → tratar como porcentaje
        is_pct = (
            abs(f) <= 5
            and any(kw in col_lower for kw in [
                "margen", "margin", "%", "tasa", "rate",
                "rendimiento", "cobertura", "capital de trabajo",
            ])
        )
        if is_pct:
            return f"{f * 100:.2f} %"
        if f == int(f) and abs(f) < 1e12:
            return f"{int(f):,}"
        return f"{f:,.2f}"
    return str(v)


# ── FASE 1: Discovery HTTP ─────────────────────────────────────────────────────

def phase1_discovery(out: Path) -> dict[str, Any]:
    """Descarga metadatos del modelo Power BI vía API pública sin autenticación.

    Obtiene: páginas, entidades, medidas y esquema conceptual.
    """
    disc_dir = mkdirs(out / "discovery")
    result: dict[str, Any] = {
        "fetched_at": now_iso(),
        "model_id": None,
        "pages": [],
        "entities": [],
        "measures": [],
        "errors": [],
    }

    # ── modelsAndExploration ──
    url = f"{API_BASE}/public/reports/{REPORT_ID}/modelsAndExploration?preferReadOnlySession=true"
    print("  [1/2] GET modelsAndExploration…")
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        dump_json(disc_dir / "models_exploration.json", data)

        models = data.get("models", [])
        if models:
            result["model_id"] = models[0].get("id")

        # Extraer páginas desde la exploración del modelo
        model_exp = data.get("exploration", {}).get("modelExploration", {})
        sections = model_exp.get("Sections") or model_exp.get("sections") or []
        for s in sections:
            result["pages"].append({
                "id": s.get("Id") or s.get("id"),
                "name": s.get("DisplayName") or s.get("displayName", ""),
                "ordinal": s.get("Ordinal") or s.get("ordinal", 0),
            })
        result["pages"].sort(key=lambda x: x.get("ordinal", 0))

        print(f"  → Model ID: {result['model_id']} | Páginas: {len(result['pages'])}")

    except Exception as e:
        result["errors"].append(f"modelsAndExploration: {e}")
        print(f"  [WARN] modelsAndExploration falló: {e}")

    # ── Conceptual Schema ──
    if result.get("model_id"):
        print("  [2/2] POST conceptualschema…")
        try:
            resp = requests.post(
                f"{API_BASE}/public/reports/conceptualschema",
                json={"modelIds": [result["model_id"]]},
                headers={"User-Agent": UA, "Content-Type": "application/json"},
                timeout=60,
            )
            resp.raise_for_status()
            schema = resp.json()
            dump_json(disc_dir / "schema.json", schema)

            for s in schema.get("schemas", []):
                for ent in s.get("schema", {}).get("Entities", []):
                    ent_name = ent.get("Name", "")
                    props = []
                    for p in ent.get("Properties", []):
                        prop_name = p.get("Name", "")
                        props.append(prop_name)
                        if "Column" not in p:  # Sin columna → es medida
                            result["measures"].append(f"{ent_name}.{prop_name}")
                    result["entities"].append({"name": ent_name, "properties": props})

            print(f"  → Entidades: {len(result['entities'])} | Medidas: {len(result['measures'])}")

        except Exception as e:
            result["errors"].append(f"conceptualschema: {e}")
            print(f"  [WARN] conceptualschema falló: {e}")

    dump_json(disc_dir / "summary.json", result)
    return result


# ── FASE 2: Helpers Playwright ─────────────────────────────────────────────────

def wait_visuals(page: Any, timeout_ms: int = 30_000) -> None:
    """Espera a que los card visuals de Power BI terminen de renderizar."""
    import contextlib

    with contextlib.suppress(Exception):
        page.wait_for_function(
            r"""() => {
                const t = document.body.innerText || '';
                const loading = (t.match(/Cargando objetos visuales/g) || []).length;
                return loading === 0 && t.replace(/\s/g, '').length > 200;
            }""",
            timeout=timeout_ms,
        )
    page.wait_for_timeout(2_500)


def snap_page(page: Any, label: str, pbi_dir: Path) -> dict[str, Any]:
    """Captura texto completo, aria_snapshot y screenshot de la página actual."""
    import contextlib

    wait_visuals(page, 20_000)
    text = aria = ""
    with contextlib.suppress(Exception):
        text = page.inner_text("body")
    with contextlib.suppress(Exception):
        aria = page.locator("body").aria_snapshot()

    dump_text(pbi_dir / "aria" / f"{label}.yaml", aria)
    dump_text(pbi_dir / "aria" / f"{label}.txt", text)

    shot_path = pbi_dir / "screenshots" / f"{label}.png"
    with contextlib.suppress(Exception):
        page.screenshot(path=str(shot_path), full_page=True)

    return {
        "label": label,
        "text_len": len(text),
        "aria_len": len(aria),
        "company_hits": find_company_hits(text),
        "aria_file": str(pbi_dir / "aria" / f"{label}.yaml"),
        "text_file": str(pbi_dir / "aria" / f"{label}.txt"),
        "screenshot": str(shot_path),
    }


def navigate_pbi_page(page: Any, name_pattern: str) -> bool:
    """Navega a una página del reporte Power BI haciendo clic en el botón de navegación interno.

    En Power BI embed los elementos de menú son BUTTONS (no links).
    Prueba múltiples estrategias de localización.
    """
    strategies = [
        lambda: page.get_by_role("button", name=re.compile(name_pattern, re.IGNORECASE)).first,
        lambda: page.get_by_role("link", name=re.compile(name_pattern, re.IGNORECASE)).first,
        lambda: page.locator(f"[aria-label*='{name_pattern}']").first,
        lambda: page.get_by_text(re.compile(name_pattern, re.IGNORECASE)).first,
    ]
    for get_el in strategies:
        try:
            el = get_el()
            if el.is_visible(timeout=2_000):
                el.click(timeout=5_000)
                wait_visuals(page, 20_000)
                return True
        except Exception:
            pass
    return False


def try_select_company(page: Any) -> bool:
    """Intenta seleccionar HOTELES ESTELAR (NIT 890304099) en el slicer del reporte.

    Power BI puede tener slicers de distintos tipos:
      - Search input (tipo texto libre)
      - List slicer (ítems clicables)
      - Dropdown slicer
    Se prueban todas las estrategias en orden.
    """
    # ── Estrategia A: input de búsqueda (search slicer) ──
    for search_term in [NIT, "ESTELAR", COMPANY_NAME]:
        try:
            inputs = page.locator(
                "input[type='text'], input[type='search'],"
                " input:not([type='hidden']):not([type='button'])"
            ).all()
            for inp in inputs:
                try:
                    if not inp.is_visible(timeout=800):
                        continue
                    inp.triple_click(timeout=1_500)
                    inp.fill(search_term, timeout=1_500)
                    page.wait_for_timeout(1_800)

                    # Buscar en dropdown resultante
                    for role in ["option", "listitem"]:
                        for opt in page.get_by_role(role).all():
                            try:
                                txt = opt.inner_text(timeout=400)
                                if NIT in txt or "ESTELAR" in txt.upper():
                                    opt.click(timeout=2_000)
                                    page.wait_for_timeout(3_000)
                                    return True
                            except Exception:
                                pass

                    # Sin dropdown claro → Enter
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2_000)
                    body_text = page.inner_text("body")
                    if NIT in body_text or "ESTELAR" in body_text.upper():
                        return True
                except Exception:
                    continue
        except Exception:
            pass

    # ── Estrategia B: list slicer (ítems ya visibles) ──
    try:
        for item in page.get_by_role("listitem").all():
            try:
                txt = item.inner_text(timeout=400)
                if NIT in txt or "ESTELAR" in txt.upper():
                    item.click(timeout=2_000)
                    page.wait_for_timeout(3_000)
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # ── Estrategia C: clic directo sobre texto con el NIT ──
    try:
        el = page.locator(f"text={NIT}").first
        el.click(timeout=3_000)
        page.wait_for_timeout(3_000)
        return True
    except Exception:
        pass

    return False


# ── FASE 2+3: Captura Playwright ───────────────────────────────────────────────

def phase2_capture(out: Path, max_pages: int = 14) -> dict[str, Any]:
    """Abre el embed de Power BI con Playwright y captura todos los datos disponibles.

    Intercepta TODAS las respuestas de red (/querydata con datos financieros reales),
    navega a 'Análisis individual', selecciona HOTELES ESTELAR en el slicer,
    y recorre todas las páginas del reporte capturando:
      - aria_snapshot (YAML accesible de los visuals)
      - texto plano
      - screenshots PNG
      - respuestas JSON de /querydata
    """
    try:
        from playwright.sync_api import TimeoutError as PWT  # noqa: N814
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright no instalado. Ejecuta: uv run playwright install chromium"
        ) from exc

    pbi_dir = out / "powerbi"
    for sub in ["screenshots", "querydata", "aria"]:
        mkdirs(pbi_dir / sub)

    querydata_entries: list[dict] = []
    req_log: list[dict] = []
    lock = Lock()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        ctx = browser.new_context(
            locale="es-CO",
            viewport={"width": 1920, "height": 1080},
            user_agent=UA,
        )
        pg = ctx.new_page()

        # ── Interceptor de red ──────────────────────────────────────────────
        def on_resp(resp: Any) -> None:
            url = resp.url
            req_log.append({
                "ts": now_iso(),
                "method": resp.request.method,
                "url": url,
                "status": resp.status,
            })

            # querydata → datos financieros reales por empresa/visual
            if "querydata" in url.lower() and resp.status == 200:
                import contextlib

                with contextlib.suppress(Exception):
                    body = resp.json()
                    digest = hashlib.sha1((url + now_iso()).encode()).hexdigest()[:12]
                    path = pbi_dir / "querydata" / f"{digest}.json"
                    dump_json(path, {"url": url, "response": body})
                    with lock:
                        querydata_entries.append({"url": url, "file": str(path)})

            # modelsAndExploration live → backup de estructura
            elif "modelsandexploration" in url.lower() and resp.status == 200:
                import contextlib

                with contextlib.suppress(Exception):
                    dump_json(pbi_dir / "models_exploration_live.json", resp.json())

        pg.on("response", on_resp)

        # ── 1. Cargar el embed ──────────────────────────────────────────────
        print("  [PBI] Cargando embed Power BI…")
        pg.goto(POWERBI_EMBED, wait_until="domcontentloaded", timeout=120_000)
        pg.wait_for_timeout(12_000)  # Power BI necesita tiempo para inicializar

        pages_data: list[dict] = []

        # ── 2. Capturar home ───────────────────────────────────────────────
        print("  [PBI] Snapshot: home")
        pages_data.append(snap_page(pg, "00_home", pbi_dir))

        # ── 3. Ir primero a 'Análisis por sector' para activar el menú ──
        # La página de inicio a veces no tiene el menú visible; la página 2 sí.
        # Hacemos clic en 'Página siguiente' para llegar al menú de navegación.
        pg.wait_for_timeout(3_000)
        try:
            pg.get_by_role(
                "button", name=re.compile("Página siguiente", re.IGNORECASE)
            ).click(timeout=5_000)
            pg.wait_for_timeout(5_000)
        except Exception:
            pass

        # ── 4. Navegar a 'Análisis individual' con botón del menú ─────────
        print("  [PBI] Navegando a 'Análisis individual'…")
        nav_ok = (
            navigate_pbi_page(pg, "Análisis individual") or navigate_pbi_page(pg, "individual")
        )
        nav_msg = "✓ OK" if nav_ok else "✗ no encontrado — se recorren páginas en orden"
        print(f"  [PBI] Navegación: {nav_msg}")
        pg.wait_for_timeout(6_000)

        # ── 5. Seleccionar empresa en el slicer ───────────────────────────
        print(f"  [PBI] Buscando slicer para NIT {NIT}…")
        sel_ok = try_select_company(pg)
        print(f"  [PBI] Selección empresa: {'✓ OK' if sel_ok else '✗ no encontrado'}")
        if sel_ok:
            pg.wait_for_timeout(5_000)

        print("  [PBI] Snapshot: 01_analisis_individual")
        snap = snap_page(pg, "01_analisis_individual", pbi_dir)
        snap["company_selected"] = sel_ok
        pages_data.append(snap)

        # ── 6. Recorrer páginas restantes ─────────────────────────────────
        for i in range(2, max_pages + 2):
            try:
                next_btn = pg.get_by_role(
                    "button", name=re.compile("Página siguiente", re.IGNORECASE)
                )
                if next_btn.is_disabled():
                    print(f"  [PBI] Última página alcanzada ({i - 1} páginas totales).")
                    break
                next_btn.click(timeout=5_000)
                pg.wait_for_timeout(5_000)
                label = f"{i:02d}_page"
                print(f"  [PBI] Snapshot: {label}")
                pages_data.append(snap_page(pg, label, pbi_dir))
            except PWT:
                print("  [PBI] Botón 'siguiente' no disponible. Fin.")
                break
            except Exception as exc:
                print(f"  [PBI] Error en página {i}: {exc}")
                break

        browser.close()

    result = {
        "fetched_at": now_iso(),
        "powerbi_url": POWERBI_EMBED,
        "pages_captured": len(pages_data),
        "querydata_captured": len(querydata_entries),
        "pages": pages_data,
        "querydata_files": [e["file"] for e in querydata_entries],
    }
    dump_json(pbi_dir / "capture_summary.json", result)
    dump_json(pbi_dir / "request_log.json", req_log)
    print(f"  [PBI] Resultado: {len(pages_data)} páginas | {len(querydata_entries)} querydata")
    return result


# ── FASE 3: Parsing ─────────────────────────────────────────────────────────────

# Reconoce valores numéricos típicos de reportes financieros (con separadores ES/EN)
_NUMERIC_RE = re.compile(
    r"^[\$\-\+]?\s*[\d]{1,3}(?:[.,\s'\u00a0]\d{3})*(?:[.,]\d+)?\s*[%MKBG$Mm]?\s*$"
)


def parse_aria_kv(aria_text: str) -> list[dict[str, str]]:
    """Extrae pares (indicador → valor) del aria_snapshot de Power BI.

    Los card visuals de Power BI se representan como bloques consecutivos:
      - paragraph: "$ 1,234,567"   ← valor
      - paragraph: "Ingresos"      ← etiqueta
    Se detectan estos pares y se invierte a (etiqueta → valor).
    """
    pairs: list[dict[str, str]] = []
    # Limpiar el YAML a líneas de texto puro
    clean_lines = []
    for line in aria_text.splitlines():
        stripped = line.strip()
        # Remover prefijos de YAML: '- ', '* ', decoradores de tipo, etc.
        stripped = re.sub(
            r"^[-*>|]+\s*|^(paragraph|text|generic|document|group|heading|listitem|link|button)[:\s]*",
            "",
            stripped,
            flags=re.IGNORECASE,
        ).strip().strip("\"'")
        if stripped:
            clean_lines.append(stripped)

    i = 0
    while i < len(clean_lines):
        line = clean_lines[i]
        if _NUMERIC_RE.match(line):
            # El siguiente elemento no numérico es la etiqueta
            j = i + 1
            while j < len(clean_lines) and _NUMERIC_RE.match(clean_lines[j]):
                j += 1
            if j < len(clean_lines):
                label = clean_lines[j]
                if len(label) < 150:  # Filtrar párrafos muy largos (disclaimer, etc.)
                    pairs.append({"key": label, "value": line})
            i = j + 1
        else:
            i += 1

    return pairs


def parse_dsr_rows(descriptor_select: list, ds: list) -> list[dict]:
    """Parser del formato DSR (Data Shape Result) de Power BI.

    El formato DSR usa arrays 'C' dentro de DM0 donde cada elemento es
    una fila con [grupo_key, valor1, valor2, ...]. También usa RT (Reference
    Table) para datos comprimidos delta-encoded. Esta función maneja el
    caso común de rows-as-C-arrays que es el más frecuente en reportes
    públicos de embed.
    """
    col_names = [s.get("Name", f"col_{i}") for i, s in enumerate(descriptor_select)]
    rows: list[dict] = []

    for ds_entry in ds:
        # Buscar datos en los grupos PH/DM0
        for ph in ds_entry.get("PH", []):
            for dm_key in ("DM0", "DM1", "DM2"):
                for row in ph.get(dm_key, []):
                    c = row.get("C")
                    if isinstance(c, list) and c:
                        row_dict: dict[str, Any] = {}
                        for j, val in enumerate(c):
                            if j < len(col_names):
                                row_dict[col_names[j]] = val
                        if row_dict:
                            rows.append(row_dict)

        # También chequear RT (Reference Table) que a veces tiene la primera fila
        rt = ds_entry.get("RT", [])
        for rt_row in rt:
            if isinstance(rt_row, list) and len(rt_row) >= 2:
                rt_dict: dict[str, Any] = {}
                for j, val in enumerate(rt_row):
                    if j < len(col_names) and val is not None and val is not False:
                        rt_dict[col_names[j]] = val
                if rt_dict:
                    rows.append(rt_dict)

    return rows


def phase3_parse(out: Path) -> dict[str, Any]:
    """Extrae y estructura datos financieros desde los archivos capturados.

    Fuentes:
    1. Respuestas /querydata interceptadas (datos financieros estructurados)
    2. aria_snapshot (valores de card visuals)
    3. Texto plano (menciones de la empresa)
    """
    qd_rows: list[dict] = []
    aria_kv: list[dict] = []
    text_company: list[dict] = []

    # ── 1. Querydata ──
    qd_dir = out / "powerbi" / "querydata"
    if qd_dir.exists():
        files = sorted(qd_dir.glob("*.json"))
        print(f"  [PARSE] Procesando {len(files)} archivos querydata…")
        for f in files:
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                response = raw.get("response", raw)
                for res in response.get("results", []):
                    result_data = res.get("result", {}).get("data", {})
                    descriptor_select = result_data.get("descriptor", {}).get("Select", [])
                    dsr_ds = result_data.get("dsr", {}).get("DS", [])

                    if descriptor_select and dsr_ds:
                        # Formato DSR real (Power BI)
                        rows_parsed = parse_dsr_rows(descriptor_select, dsr_ds)
                        for row_dict in rows_parsed:
                            # Filtrar solo filas que mencionan ESTELAR o no tienen filtro
                            row_str = json.dumps(row_dict, ensure_ascii=False)
                            row_dict["_src"] = f.name
                            row_dict["_has_estelar"] = any(
                                t.lower() in row_str.lower() for t in COMPANY_TERMS
                            )
                            qd_rows.append(row_dict)
                    else:
                        # Formato tabla clásico (fallback)
                        for table in res.get("tables", []):
                            cols = [
                                c.get("queryName") or c.get("name") or f"col_{i}"
                                for i, c in enumerate(table.get("columns", []))
                            ]
                            for row in table.get("rows", []):
                                if isinstance(row, list):
                                    row_dict = {
                                        cols[j]: v for j, v in enumerate(row) if j < len(cols)
                                    }
                                elif isinstance(row, dict):
                                    row_dict = dict(row)
                                else:
                                    continue
                                row_dict["_src"] = f.name
                                row_dict["_has_estelar"] = False
                                qd_rows.append(row_dict)
            except Exception as exc:
                print(f"  [WARN] Querydata {f.name}: {exc}")

    # ── 2. Aria snapshots ──
    aria_dir = out / "powerbi" / "aria"
    if aria_dir.exists():
        yaml_files = sorted(aria_dir.glob("*.yaml"))
        print(f"  [PARSE] Procesando {len(yaml_files)} aria snapshots…")
        for f in yaml_files:
            try:
                text = f.read_text(encoding="utf-8")
                for kv in parse_aria_kv(text):
                    kv["_src_page"] = f.stem
                    aria_kv.append(kv)
            except Exception as exc:
                print(f"  [WARN] Aria {f.name}: {exc}")

    # ── 3. Texto plano (menciones de empresa) ──
    if aria_dir.exists():
        for f in sorted(aria_dir.glob("*.txt")):
            try:
                text = f.read_text(encoding="utf-8")
                hits = find_company_hits(text)
                if hits:
                    text_company.append({
                        "page": f.stem,
                        "hits": hits,
                        "sample": text[:3000],
                    })
            except Exception:
                pass

    # ── Separar filas de ESTELAR del resto ──
    estelar_rows = [r for r in qd_rows if r.get("_has_estelar")]
    print(f"  [PARSE] Filas directas de ESTELAR: {len(estelar_rows)}")

    # ── Detectar año del reporte desde los aria snapshots ──
    # El aria de página 2 contiene: combobox "Año": 2024
    report_year = "sin_año"
    aria_dir = out / "powerbi" / "aria"
    if aria_dir.exists():
        for af in sorted(aria_dir.glob("*.yaml")):
            try:
                atxt = af.read_text(encoding="utf-8")
                # Buscar: combobox "Año": YYYY  o  Año (seleccionado): YYYY
                m_yr = re.search(r'combobox\s+["Año]+.*?(20\d{2})', atxt)
                if not m_yr:
                    m_yr = re.search(r'"Año"[^\n]*(20\d{2})', atxt)
                if m_yr:
                    yr = int(m_yr.group(1))
                    if 2010 <= yr <= 2030:
                        report_year = str(yr)
                        break
            except Exception:
                pass

    # ── Agrupar querydata por año (solo filas de ESTELAR) ──
    by_year: dict[str, list[dict]] = defaultdict(list)
    target_rows = estelar_rows if estelar_rows else qd_rows
    for row in target_rows:
        year = report_year  # usar el año detectado del reporte como default
        for k, v in row.items():
            if k.startswith("_"):
                continue
            # Solo buscar año en columnas que son explícitamente temporales
            if any(kw in k.lower() for kw in ["year", "año", "periodo", "period", "fecha", "date"]):
                if isinstance(v, str):
                    m_y = re.search(r"20\d{2}", v)
                    if m_y:
                        yr_candidate = int(m_y.group(0))
                        if 2010 <= yr_candidate <= 2030:
                            year = m_y.group(0)
                            break
                elif isinstance(v, int) and 2010 <= v <= 2030:
                    year = str(v)
                    break
        by_year[year].append(row)

    result = {
        "querydata_rows": qd_rows,
        "estelar_rows": estelar_rows,
        "aria_kv": aria_kv,
        "text_company_pages": text_company,
        "by_year": dict(by_year),
        "years": sorted(by_year.keys()),
    }
    dump_json(out / "parsed_data.json", result)
    print(
        f"  [PARSE] → {len(qd_rows)} filas querydata total | "
        f"{len(estelar_rows)} de ESTELAR | "
        f"{len(aria_kv)} pares KV aria | "
        f"{len(text_company)} páginas con menciones"
    )
    return result


# ── FASE 4: Generación de Markdown ────────────────────────────────────────────

def _table_rows_by_category(
    lines: list[str], rows: list[dict], category: str, cat_title: str
) -> None:
    """Agrega al markdown una sección de tabla para una categoría específica."""
    cat_keys = [
        (row, k)
        for row in rows
        for k in row
        if not k.startswith("_") and categorize_field(k) == category
    ]
    if not cat_keys:
        return

    lines += [f"## {cat_title}", "", "| Campo | Valor |", "|---|---|"]
    seen = set()
    for row, k in cat_keys:
        display = k.split(".")[-1] if "." in k else k
        if display in seen:
            continue
        seen.add(display)
        v = row.get(k)
        if v is not None:
            lines.append(f"| {display} | {fmt_value(v, col_name=k)} |")
    lines.append("")


def _render_year_section(lines: list[str], rows: list[dict]) -> None:
    """Renderiza todos los datos de un año agrupados por categoría financiera."""
    if not rows:
        lines += ["_Sin datos disponibles para este período._", ""]
        return

    category_map = {
        "identificacion": "Identificación",
        "estado_resultados": "Estado de Resultados",
        "balance": "Balance General",
        "indicadores": "Indicadores Financieros",
        "otros": "Otros Datos",
    }
    for cat, title in category_map.items():
        _table_rows_by_category(lines, rows, cat, title)


def phase4_markdown(parsed: dict, discovery: dict, out: Path) -> str:
    """Genera el Markdown final estructurado por año con toda la información capturada.

    Incluye datos de HOTELES ESTELAR organizados por año, sector y card visuals.
    """
    lines: list[str] = []

    # ── Encabezado ────────────────────────────────────────────────────────
    lines += [
        "# HOTELES ESTELAR S.A.",
        "",
        "> **Nota:** Las cifras monetarias están expresadas en **COP millones**"
        " según la fuente (Estrategia en Acción / Supersociedades).",
        "",
        "| Campo | Valor |",
        "|---|---|",
        "| **NIT** | 890304099 |",
        "| **Razón social** | HOTELES ESTELAR SA |",
        "| **Sector** | Turismo / Hoteles (CIIU H5510) |",
        "| **Fuente** | Supersociedades (vía Estrategia en Acción) |",
        "| **Reporte** | https://www.estrategiaenaccion.com/es/reportes |",
        "| **Dataset actualizado** | 2024 |",
        f"| **Extracción** | {now_iso()[:10]} |",
        "| **Unidades** | COP millones |",
        "",
        "---",
        "",
    ]

    # ── Estructura del modelo (discovery) ─────────────────────────────────
    if discovery.get("pages"):
        lines += ["## Páginas del reporte Power BI", ""]
        for pg in discovery["pages"]:
            lines.append(
                f"- **{pg.get('name', '—')}** "
                f"(id: `{pg.get('id', '?')}`, ordinal: {pg.get('ordinal', '?')})"
            )
        lines.append("")

    if discovery.get("entities"):
        lines += ["## Modelo de datos — Entidades y propiedades", ""]
        for ent in discovery["entities"]:
            lines += [f"### `{ent['name']}`", "", "| Propiedad |", "|---|"]
            for prop in ent.get("properties", []):
                lines.append(f"| {prop} |")
            lines.append("")

    if discovery.get("measures"):
        lines += ["## Medidas disponibles", ""]
        for m in discovery["measures"]:
            lines.append(f"- `{m}`")
        lines.append("")

    if discovery.get("pages") or discovery.get("entities") or discovery.get("measures"):
        lines += ["---", ""]

    # ── Datos por año ──────────────────────────────────────────────────────
    by_year = parsed.get("by_year", {})
    years = sorted([y for y in by_year if y != "sin_año"], reverse=True)

    if years:
        for year in years:
            lines += [f"# {year}", ""]
            _render_year_section(lines, by_year[year])
            lines += ["---", ""]

    if "sin_año" in by_year:
        lines += ["# Datos (período no identificado)", ""]
        _render_year_section(lines, by_year["sin_año"])
        lines += ["---", ""]

    # ── Contexto del sector extraído de aria snapshots ─────────────────────
    # Los aria snapshots de la página 2 (Análisis por sector) tienen datos del
    # sector completo seleccionado que son útiles como contexto comparativo.
    aria_sector: list[tuple[str, str]] = []
    try:
        for af in sorted((out / "powerbi" / "aria").glob("*.yaml")):
            txt = af.read_text(encoding="utf-8")
            # Separar por botones individuales para evitar capturar valores de otros botones
            btn_blocks = re.split(r'\n\s*- button "', txt)
            for block in btn_blocks[1:]:
                m_label = re.match(r'^([^"]{5,100})"', block)
                if not m_label:
                    continue
                label = m_label.group(1).replace(" tarjeta", "").strip()
                # Tomar solo el PRIMER paragraph del bloque (sin DOTALL agresivo)
                m_val = re.search(
                    r'paragraph:\s+"?([0-9][0-9.,\s]*[0-9])"?', block[:300]
                )
                if m_val:
                    val = m_val.group(1).strip()
                    aria_sector.append((label, val))
            # Agregar año del reporte
            yr_m = re.search(r'combobox "[^"]*A[ñn]o[^"]*":\s*(\d{4})', txt)
            if yr_m:
                aria_sector.append(("Año del reporte", yr_m.group(1)))
            if aria_sector:
                break
    except Exception:
        pass

    if aria_sector:
        lines += [
            "# Contexto del sector (datos agrupados — fuente: reporte Power BI)",
            "",
            "_Valores agregados del sector visible en el reporte (no filtrados por empresa)_",
            "",
            "| Indicador | Valor |",
            "|---|---|",
        ]
        seen_labels: set[str] = set()
        for label, val in aria_sector:
            if label not in seen_labels:
                seen_labels.add(label)
                lines.append(f"| {label} | {val} |")
        lines += ["", "---", ""]

    # ── Card visuals (aria_snapshot) ───────────────────────────────────────
    aria_kv = parsed.get("aria_kv", [])
    if aria_kv:
        lines += [
            "# Valores de card visuals (aria_snapshot)",
            "",
            "_Extraídos directamente de los visuals renderizados — sin filtrar por empresa_",
            "",
        ]
        by_page: dict[str, list] = defaultdict(list)
        for kv in aria_kv:
            by_page[kv.get("_src_page", "?")].append(kv)

        for page_label, items in sorted(by_page.items()):
            lines += [f"## `{page_label}`", "", "| Indicador | Valor |", "|---|---|"]
            for kv in items:
                lines.append(f"| {kv['key']} | {kv['value']} |")
            lines.append("")

        lines += ["---", ""]

    # ── Menciones de texto ─────────────────────────────────────────────────
    text_pages = parsed.get("text_company_pages", [])
    if text_pages:
        lines += ["# Menciones de la empresa en texto extraído", ""]
        for tp in text_pages:
            lines += [f"## `{tp['page']}`", ""]
            for hit in tp.get("hits", [])[:30]:
                lines.append(f"- L{hit['line']} `[{hit['term']}]` → {hit['text'][:200]}")
            lines.append("")
        lines += ["---", ""]

    # ── Metadata ───────────────────────────────────────────────────────────
    lines += [
        "## Metadata de extracción",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Filas querydata capturadas | {len(parsed.get('querydata_rows', []))} |",
        f"| Pares KV de card visuals | {len(aria_kv)} |",
        f"| Páginas con menciones de empresa | {len(text_pages)} |",
        f"| Años identificados | {', '.join(years) if years else 'ninguno'} |",
        f"| Fuente API | {API_BASE} |",
        f"| Report ID | {REPORT_ID} |",
        "",
    ]

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parsea los argumentos de línea de comandos."""
    p = argparse.ArgumentParser(
        description="Extractor exhaustivo HOTELES ESTELAR — Power BI Estrategia en Acción"
    )
    p.add_argument("--output-dir", default="data/estelar_reportes", help="Directorio de salida")
    p.add_argument(
        "--max-pages", type=int, default=14, help="Máximo páginas Power BI a recorrer"
    )
    p.add_argument("--skip-discovery", action="store_true", help="Reusar discovery existente")
    p.add_argument(
        "--skip-capture", action="store_true", help="Reusar captura Playwright existente"
    )
    return p.parse_args()


def main() -> None:
    """Ejecuta el pipeline completo de extracción de datos de Hoteles Estelar."""
    args = parse_args()
    out = Path(args.output_dir)
    mkdirs(out)

    # ── Fase 1 ──────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print("  FASE 1: Discovery HTTP")
    print("═══════════════════════════════════════════")
    disc_summary = out / "discovery" / "summary.json"
    if args.skip_discovery and disc_summary.exists():
        discovery = json.loads(disc_summary.read_text(encoding="utf-8"))
        print("  (reutilizando discovery existente)")
    else:
        discovery = phase1_discovery(out)

    # ── Fase 2 ──────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print("  FASE 2: Captura Playwright (UI + red)")
    print("═══════════════════════════════════════════")
    cap_summary = out / "powerbi" / "capture_summary.json"
    if args.skip_capture and cap_summary.exists():
        print("  (reutilizando captura existente)")
    else:
        phase2_capture(out, max_pages=args.max_pages)

    # ── Fase 3 ──────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print("  FASE 3: Parsing")
    print("═══════════════════════════════════════════")
    parsed = phase3_parse(out)

    # ── Fase 4 ──────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print("  FASE 4: Generando Markdown")
    print("═══════════════════════════════════════════")
    md_content = phase4_markdown(parsed, discovery, out)
    md_path = out / "HOTELES_ESTELAR_890304099.md"
    dump_text(md_path, md_content)
    print(f"  → {md_path} ({len(md_content):,} caracteres)")

    # ── Resumen ─────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print("  ✓ EXTRACCIÓN COMPLETADA")
    print("═══════════════════════════════════════════")
    print(f"  Markdown      : {md_path}")
    print(f"  Datos crudos  : {out / 'parsed_data.json'}")
    print(f"  Querydata     : {out / 'powerbi' / 'querydata'}/")
    print(f"  Screenshots   : {out / 'powerbi' / 'screenshots'}/")
    print(f"  Aria snapshots: {out / 'powerbi' / 'aria'}/")
    print()


if __name__ == "__main__":
    main()
