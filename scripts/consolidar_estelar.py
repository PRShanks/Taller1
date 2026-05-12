"""consolidar_estelar.py.

---------------------
Une todos los archivos de texto/markdown que están directamente en
data/estelar_reportes/ (sin entrar en subcarpetas) en un único
archivo data/processed/estelar_consolidado.txt.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUENTE = ROOT / "data" / "estelar_reportes"
DESTINO = ROOT / "data" / "processed" / "estelar_consolidado.txt"

EXTENSIONES = {".txt", ".md"}


def consolidar() -> None:
    """Une todos los .md/.txt de estelar_reportes/ en un único archivo consolidado."""
    archivos = sorted(
        f for f in FUENTE.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSIONES
    )

    if not archivos:
        print(f"No se encontraron archivos en {FUENTE}")
        return

    DESTINO.parent.mkdir(parents=True, exist_ok=True)

    with DESTINO.open("w", encoding="utf-8") as salida:
        for archivo in archivos:
            print(f"  + {archivo.name}")
            salida.write(f"\n\n{'=' * 60}\n")
            salida.write(f"FUENTE: {archivo.name}\n")
            salida.write(f"{'=' * 60}\n\n")
            salida.write(archivo.read_text(encoding="utf-8"))

    print(f"\n✓ Consolidado en: {DESTINO}")
    print(f"  {len(archivos)} archivos  |  {DESTINO.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    consolidar()
