"""
data_loader.py
--------------
Toma el archivo .md generado por el scraper y lo transforma en un archivo
de texto limpio (.txt) que servirá de contexto para las tareas de LLM.

También enriquece el contenido con información estática de contexto
(descripción de la empresa, glosario de indicadores) para que el Q&A
tenga más material para trabajar.
"""

from pathlib import Path
import re

# Rutas del proyecto
ROOT = Path(__file__).resolve().parent.parent
RAW_MD = ROOT / "data" / "estelar_reportes" / "HOTELES_ESTELAR_890304099.md"
PROCESSED_TXT = ROOT / "data" / "processed" / "estelar_consolidado.txt"


# Contexto adicional para enriquecer el Q&A.
# Estos son hechos públicos y conocidos sobre la empresa que ayudan al LLM
# a contestar preguntas que no estarían en el .md crudo.
CONTEXTO_EMPRESA = """
INFORMACIÓN GENERAL DE LA EMPRESA
---------------------------------
Hoteles Estelar S.A. es una de las cadenas hoteleras más importantes de Colombia.
Opera bajo la marca "Estelar" y tiene presencia en las principales ciudades del país
y en algunos destinos internacionales. Su actividad económica principal está
clasificada bajo el código CIIU H5510 (Alojamiento en hoteles).

GLOSARIO DE INDICADORES FINANCIEROS
-----------------------------------
- Ingresos: Total de ventas o facturación de la empresa en el período.
- EBITDA: Utilidad antes de intereses, impuestos, depreciación y amortización.
  Mide la generación de caja operativa.
- Utilidad operativa: Resultado del negocio antes de gastos financieros e impuestos.
- Margen bruto: (Utilidad bruta / Ingresos) x 100. Indica eficiencia productiva.
- Margen EBITDA: (EBITDA / Ingresos) x 100. Indica rentabilidad operativa.
- Margen operativo: (Utilidad operativa / Ingresos) x 100.
- Deuda/EBITDA: Veces que la deuda total cubre el EBITDA. Mide apalancamiento.
  Valores superiores a 4x se consideran altos en sectores no apalancados.
- Capital de trabajo / Ingresos: Mide la liquidez relativa al volumen de ventas.
  Valores negativos pueden indicar dependencia de financiamiento de proveedores.

NOTAS METODOLÓGICAS
-------------------
Los datos provienen del reporte de Supersociedades de Colombia, accesibles
mediante la plataforma Estrategia en Acción. Las cifras monetarias están
expresadas en pesos colombianos (COP) en millones.
"""


def limpiar_markdown(texto: str) -> str:
    """Quita marcadores de Markdown sin perder la información."""
    # Tablas Markdown -> formato "Campo: Valor"
    lineas_limpias = []
    for linea in texto.split("\n"):
        # Saltar líneas separadoras de tabla (|---|---|)
        if re.match(r"^\s*\|[\s\-:|]+\|\s*$", linea):
            continue
        # Convertir filas de tabla "| x | y |" a "x: y"
        if linea.strip().startswith("|") and linea.strip().endswith("|"):
            celdas = [c.strip() for c in linea.strip("|").split("|")]
            # Saltar header si dice "Campo | Valor"
            if len(celdas) == 2 and celdas[0].lower() == "campo" and celdas[1].lower() == "valor":
                continue
            if len(celdas) == 2:
                linea = f"  - {celdas[0]}: {celdas[1]}"
            else:
                linea = "  - " + " | ".join(celdas)
        # Quitar #, >, * de Markdown manteniendo el contenido
        linea = re.sub(r"^#+\s*", "", linea)
        linea = re.sub(r"^>\s*", "", linea)
        lineas_limpias.append(linea)
    return "\n".join(lineas_limpias)


def consolidar_datos() -> Path:
    """
    Lee el .md crudo, lo limpia, le agrega contexto y guarda un .txt
    listo para alimentar al LLM.
    """
    if not RAW_MD.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de datos: {RAW_MD}\n"
            "Ejecuta primero el scraper para generarlo."
        )

    texto_crudo = RAW_MD.read_text(encoding="utf-8")
    texto_limpio = limpiar_markdown(texto_crudo)

    contenido_final = (
        "==============================================\n"
        "DATOS FINANCIEROS - HOTELES ESTELAR S.A.\n"
        "==============================================\n\n"
        f"{texto_limpio}\n\n"
        "==============================================\n"
        "CONTEXTO ADICIONAL\n"
        "==============================================\n"
        f"{CONTEXTO_EMPRESA}"
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
    print(f"✓ Archivo consolidado generado en: {ruta}")
    print(f"  Tamaño: {ruta.stat().st_size} bytes")
