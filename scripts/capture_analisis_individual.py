"""scripts/capture_analisis_individual.py.

Captura dirigida de la página 'Análisis individual' del reporte Power BI
para HOTELES ESTELAR (NIT 890304099).

Uso:
  uv run python scripts/capture_analisis_individual.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

POWERBI_EMBED = (
    "https://app.powerbi.com/view"
    "?r=eyJrIjoiOWZmMjZiZjEtMTlmNy00OTk4LTg1NmQtYTM3MTQ2ZTA2NzUzIiwidCI6ImYyNzg0NmU4LTBhYWItNGJkZS04ZDcwLWFkZDQ2Y2FiMGUwMSJ9"
    "&pageName=110a327b235d48000067"
)
NIT = "890304099"
COMPANY_TERMS = ["HOTELES ESTELAR", "890304099", "ESTELAR"]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
OUT_DIR = Path("data/estelar_reportes/powerbi/analisis_individual")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    """Retorna el timestamp actual en formato ISO 8601."""
    return datetime.now(UTC).isoformat()


def dump_json(p: Path, obj: Any) -> None:
    """Serializa obj como JSON y lo escribe en p, creando directorios si faltan."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def wait_visuals(page: Any, timeout_ms: int = 25_000) -> None:
    """Espera a que los objetos visuales de Power BI terminen de cargar."""
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
    page.wait_for_timeout(3_000)


def navigate_to_button(page: Any, button_name: str) -> bool:
    """Hace clic en un botón de navegación del menú interno de Power BI."""
    strategies = [
        lambda n=button_name: page.get_by_role("button", name=re.compile(n, re.IGNORECASE)).first,
        lambda n=button_name: page.locator(f"[aria-label*='{n}']").first,
        lambda n=button_name: page.get_by_text(re.compile(n, re.IGNORECASE)).first,
    ]
    for get_el in strategies:
        try:
            el = get_el()
            if el.is_visible(timeout=3_000):
                el.click(timeout=6_000)
                wait_visuals(page, 25_000)
                return True
        except Exception:
            pass
    return False


def try_select_estelar(page: Any) -> bool:
    """Intenta seleccionar HOTELES ESTELAR en el slicer de la página."""
    # Esperar a que aparezca algún slicer de empresa
    page.wait_for_timeout(4_000)

    # Estrategia A: buscar inputs de texto y escribir el NIT
    for search_term in [NIT, "HOTELES ESTELAR", "ESTELAR"]:
        try:
            inputs = page.locator(
                "input[type='text'], input[type='search'],"
                " input:not([type='hidden']):not([type='button'])"
            ).all()
            for inp in inputs:
                try:
                    if not inp.is_visible(timeout=1_000):
                        continue
                    inp.triple_click(timeout=2_000)
                    inp.fill(search_term, timeout=2_000)
                    page.wait_for_timeout(2_500)

                    # Buscar resultado en dropdown
                    for role in ["option", "listitem"]:
                        for opt in page.get_by_role(role).all():
                            try:
                                txt = opt.inner_text(timeout=500)
                                if NIT in txt or "ESTELAR" in txt.upper():
                                    opt.click(timeout=2_000)
                                    page.wait_for_timeout(4_000)
                                    return True
                            except Exception:
                                pass

                    # Enter directo
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2_000)
                    body = page.inner_text("body")
                    if NIT in body or "ESTELAR" in body.upper():
                        return True
                except Exception:
                    continue
        except Exception:
            pass

    # Estrategia B: items de lista visibles
    try:
        for item in page.get_by_role("listitem").all():
            try:
                txt = item.inner_text(timeout=400)
                if NIT in txt or "ESTELAR" in txt.upper():
                    item.click(timeout=2_000)
                    page.wait_for_timeout(4_000)
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # Estrategia C: texto directo del NIT
    try:
        el = page.locator(f"text={NIT}").first
        el.click(timeout=3_000)
        page.wait_for_timeout(3_000)
        return True
    except Exception:
        pass

    return False


def main() -> None:
    """Ejecuta la captura dirigida de la página Análisis individual."""
    from playwright.sync_api import sync_playwright

    querydata: list[dict] = []
    lock = Lock()

    print("\n═══════════════════════════════════════════")
    print("  Captura dirigida: Análisis individual")
    print("═══════════════════════════════════════════")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        ctx = browser.new_context(
            locale="es-CO",
            viewport={"width": 1920, "height": 1080},
            user_agent=UA,
        )
        pg = ctx.new_page()

        # ── Interceptar querydata ──────────────────────────────────────────
        def on_resp(resp: Any) -> None:
            if "querydata" in resp.url.lower() and resp.status == 200:
                try:
                    body = resp.json()
                    digest = hashlib.sha1((resp.url + now_iso()).encode()).hexdigest()[:12]
                    path = OUT_DIR / f"qd_{digest}.json"
                    dump_json(path, {"url": resp.url, "response": body})
                    with lock:
                        querydata.append({"url": resp.url, "file": str(path)})
                    print(f"  [NET] querydata capturado → {path.name}")
                except Exception:
                    pass

        pg.on("response", on_resp)

        # ── 1. Cargar embed ────────────────────────────────────────────────
        print("  [1] Cargando embed Power BI…")
        pg.goto(POWERBI_EMBED, wait_until="domcontentloaded", timeout=120_000)
        pg.wait_for_timeout(12_000)
        wait_visuals(pg, 20_000)

        # Screenshot inicial
        pg.screenshot(path=str(OUT_DIR / "01_home.png"))

        # ── 2. Ir a página 2 (donde aparece el menú de navegación) ────────
        print("  [2] Ir a página 2 para activar menú…")
        try:
            pg.get_by_role("button", name=re.compile("Página siguiente", re.IGNORECASE)).click(
                timeout=6_000
            )
            pg.wait_for_timeout(6_000)
            wait_visuals(pg, 20_000)
        except Exception as e:
            print(f"  [WARN] No pudo ir a página 2: {e}")

        pg.screenshot(path=str(OUT_DIR / "02_page2.png"))

        # Guardar aria de página 2 para diagnóstico
        try:
            aria2 = pg.locator("body").aria_snapshot()
            (OUT_DIR / "02_aria_page2.yaml").write_text(aria2, encoding="utf-8")
        except Exception:
            pass

        # ── 3. Navegar a 'Análisis individual' ────────────────────────────
        print("  [3] Navegando a 'Análisis individual'…")
        nav_ok = navigate_to_button(pg, "Análisis individual")
        print(f"  [3] Navegación: {'✓ OK' if nav_ok else '✗ no encontrado'}")
        pg.wait_for_timeout(8_000)
        wait_visuals(pg, 25_000)

        pg.screenshot(path=str(OUT_DIR / "03_analisis_individual.png"))

        # Guardar aria post-navegación
        try:
            aria3 = pg.locator("body").aria_snapshot()
            (OUT_DIR / "03_aria_analisis_individual.yaml").write_text(aria3, encoding="utf-8")
            print(f"  [3] Aria snapshot: {len(aria3)} chars")
            # Verificar si la empresa aparece
            if any(t.lower() in aria3.lower() for t in COMPANY_TERMS):
                print("  [3] ✓ ESTELAR visible en aria snapshot")
        except Exception:
            pass

        # ── 4. Seleccionar HOTELES ESTELAR ────────────────────────────────
        print(f"  [4] Buscando slicer para NIT {NIT}…")
        sel_ok = try_select_estelar(pg)
        print(f"  [4] Selección: {'✓ OK' if sel_ok else '✗ no encontrado'}")

        if sel_ok:
            pg.wait_for_timeout(6_000)
            wait_visuals(pg, 25_000)
            pg.screenshot(path=str(OUT_DIR / "04_estelar_selected.png"))
            try:
                aria4 = pg.locator("body").aria_snapshot()
                (OUT_DIR / "04_aria_estelar_selected.yaml").write_text(aria4, encoding="utf-8")
            except Exception:
                pass

        # ── 5. Esperar más querydata ───────────────────────────────────────
        print("  [5] Esperando querydata adicional (15s)…")
        pg.wait_for_timeout(15_000)

        # Screenshot final
        pg.screenshot(path=str(OUT_DIR / "05_final.png"))
        try:
            aria5 = pg.locator("body").aria_snapshot()
            (OUT_DIR / "05_aria_final.yaml").write_text(aria5, encoding="utf-8")
            txt5 = pg.inner_text("body")
            (OUT_DIR / "05_text_final.txt").write_text(txt5, encoding="utf-8")
        except Exception:
            pass

        browser.close()

    # ── Resumen ────────────────────────────────────────────────────────────
    print(f"\n  Querydata capturados: {len(querydata)}")
    for qd in querydata:
        print(f"    - {Path(qd['file']).name}")

    # ── Analizar archivos capturados ───────────────────────────────────────
    print("\n  Buscando ESTELAR en archivos capturados…")
    estelar_found = []
    for qd in querydata:
        try:
            raw = json.loads(Path(qd["file"]).read_text(encoding="utf-8"))
            content = json.dumps(raw, ensure_ascii=False)
            if any(t in content for t in ["890304099", "ESTELAR"]):
                estelar_found.append(qd["file"])
                print(f"  ✓ ESTELAR encontrado en: {Path(qd['file']).name}")

                # Mostrar columnas y datos
                r = raw.get("response", raw)
                for res in r.get("results", []):
                    rdata = res.get("result", {}).get("data", {})
                    sel = rdata.get("descriptor", {}).get("Select", [])
                    if sel:
                        cols = [s.get("Name", "?") for s in sel]
                        print(f"    Columnas ({len(cols)}): {cols}")
        except Exception as e:
            print(f"  [WARN] {e}")

    if not estelar_found:
        print("  ✗ ESTELAR NO encontrado en los querydata de esta captura")
        print("  → La selección de empresa en el slicer no activó nuevas consultas,")
        print("    o la navegación no llegó a 'Análisis individual'.")
        print("  → Ver screenshots en:", OUT_DIR)


if __name__ == "__main__":
    main()
