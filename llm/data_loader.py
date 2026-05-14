"""data_loader.py.

------------------
Lee todos los archivos ``.md`` de ``data/estelar_reportes/`` usando glob,
los limpia de marcas Markdown y los combina en un solo archivo ``.txt``
para alimentar al LLM.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTES_DIR = ROOT / "data" / "estelar_reportes"
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


def _nombre_seccion(archivo: Path) -> str:
    """Genera un nombre de sección legible a partir del nombre del archivo.

    Parámetros:
        archivo: Ruta al archivo ``.md``.

    Devuelve:
        Nombre de sección en mayúsculas, formateado para el encabezado.
    """
    nombre = archivo.stem
    nombre = re.sub(r"[-_]+", " ", nombre)
    return nombre.upper()


def consolidar_datos() -> Path:
    """Lee todos los ``.md`` de ``REPORTES_DIR``, los limpia y los combina.

    Si no se encuentra ningún archivo ``.md``, lanza ``FileNotFoundError``
    listando los archivos existentes en el directorio.

    Devuelve:
        Ruta al archivo ``.txt`` consolidado.
    """
    md_files = sorted(REPORTES_DIR.glob("*.md"))

    if not md_files:
        existentes = (
            [str(p.name) for p in sorted(REPORTES_DIR.iterdir())]
            if REPORTES_DIR.exists()
            else []
        )
        msg = (
            f"No se encontraron archivos .md en {REPORTES_DIR}.\n"
            "Asegúrate de que existan reportes en data/estelar_reportes/"
        )
        if existentes:
            msg += f"\nArchivos encontrados: {', '.join(existentes)}"
        raise FileNotFoundError(msg)

    partes: list[str] = []

    for ruta in md_files:
        titulo = _nombre_seccion(ruta)
        texto_limpio = limpiar_markdown(ruta.read_text(encoding="utf-8"))
        partes.append(
            "=" * 46
            + "\n"
            + f"{titulo}\n"
            + "=" * 46
            + "\n\n"
            + f"{texto_limpio}\n"
        )

    contenido_final = (
        "\n".join(partes)
        + "\n"
        + "=" * 46
        + "\n"
        + "GLOSARIO\n"
        + "=" * 46
        + "\n"
        + f"{GLOSARIO}"
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
