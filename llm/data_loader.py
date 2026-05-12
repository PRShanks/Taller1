"""data_loader.py.

--------------
Lee DOS archivos .md del scraper:
  1. HOTELES_ESTELAR_890304099.md  -> datos financieros
  2. hoteles_estelar.md            -> información corporativa completa

Los combina y limpia en un solo .txt para alimentar al LLM.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_MD_FINANCIERO = ROOT / "data" / "estelar_reportes" / "HOTELES_ESTELAR_890304099.md"
RAW_MD_CORPORATIVO = ROOT / "data" / "estelar_reportes" / "hoteles_estelar.md"
PROCESSED_TXT = ROOT / "data" / "processed" / "estelar_consolidado.txt"

GLOSARIO = """
GLOSARIO DE INDICADORES FINANCIEROS
-----------------------------------
- Ingresos: Total de ventas o facturación de la empresa en el período.
- EBITDA: Utilidad antes de intereses, impuestos, depreciación y amortización.
- Utilidad operativa: Resultado antes de gastos financieros e impuestos.
- Margen bruto: (Utilidad bruta / Ingresos) x 100. Indica eficiencia productiva.
- Margen EBITDA: (EBITDA / Ingresos) x 100. Rentabilidad operativa.
- Margen operativo: (Utilidad operativa / Ingresos) x 100.
- Deuda/EBITDA: Veces que la deuda cubre el EBITDA. Mide apalancamiento.
- Capital de trabajo / Ingresos: Mide liquidez relativa al volumen de ventas.
Cifras en COP millones. Fuente: Supersociedades / Estrategia en Acción.
"""


def limpiar_markdown(texto: str) -> str:
    """Quita marcadores Markdown sin perder la información."""
    lineas_limpias = []
    for linea in texto.split("\n"):
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", linea):
            continue
        if linea.strip().startswith("|") and linea.strip().endswith("|"):
            celdas = [c.strip() for c in linea.strip("|").split("|")]
            if len(celdas) == 2 and celdas[0].lower() == "campo" and celdas[1].lower() == "valor":
                continue
            if len(celdas) == 2:
                linea = f"  - {celdas[0]}: {celdas[1]}"
            else:
                linea = "  - " + " | ".join(celdas)
        linea = re.sub(r"^#+\s*", "", linea)
        linea = re.sub(r"^>\s*", "", linea)
        lineas_limpias.append(linea)
    return "\n".join(lineas_limpias)


def consolidar_datos() -> Path:
    """Lee ambos .md, los limpia y los combina en un solo .txt.

    Si alguno no existe, lanza error indicando cuál falta.
    """
    for ruta in [RAW_MD_FINANCIERO, RAW_MD_CORPORATIVO]:
        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontró: {ruta}\n"
                "Asegúrate de que el archivo esté en data/estelar_reportes/"
            )

    texto_financiero = limpiar_markdown(RAW_MD_FINANCIERO.read_text(encoding="utf-8"))
    texto_corporativo = limpiar_markdown(RAW_MD_CORPORATIVO.read_text(encoding="utf-8"))

    contenido_final = (
        "==============================================\n"
        "DATOS FINANCIEROS - HOTELES ESTELAR S.A.\n"
        "==============================================\n\n"
        f"{texto_financiero}\n\n"
        "==============================================\n"
        "INFORMACIÓN CORPORATIVA - HOTELES ESTELAR S.A.\n"
        "==============================================\n\n"
        f"{texto_corporativo}\n\n"
        "==============================================\n"
        "GLOSARIO\n"
        "==============================================\n"
        f"{GLOSARIO}"
    )

    PROCESSED_TXT.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_TXT.write_text(contenido_final, encoding="utf-8")
    return PROCESSED_TXT


def cargar_contexto() -> str:
    """Devuelve el texto consolidado. Lo genera si no existe."""
    if not PROCESSED_TXT.exists():
        consolidar_datos()
    return PROCESSED_TXT.read_text(encoding="utf-8")


if __name__ == "__main__":
    ruta = consolidar_datos()
    print(f"✓ Archivo consolidado: {ruta}")
    print(f"  Tamaño: {ruta.stat().st_size} bytes")
