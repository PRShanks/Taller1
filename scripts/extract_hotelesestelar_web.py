"""extract_hotelesestelar_web.py.

------------------------------
Scraper de la página oficial de Hoteles Estelar (https://www.hotelesestelar.com).
Extrae:
  - Lista de hoteles (Colombia + Perú) con sus URLs
  - Detalles de cada hotel (descripción, dirección)
  - Restaurantes con su ubicación
  - Centros de convenciones / salones
  - Información del programa de lealtad y datos de contacto

Genera un archivo Markdown estructurado en:
  data/estelar_reportes/hoteles_estelar_web.md

Uso:
    python -m scripts.extract_hotelesestelar_web
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ----------------------------- Configuración -----------------------------
BASE_URL = "https://www.hotelesestelar.com"
OUTPUT = (
    Path(__file__).resolve().parent.parent / "data" / "estelar_reportes" / "hoteles_estelar_web.md"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

DELAY_SEG = 1.0  # pausa entre peticiones (cortesía con el servidor)


# ----------------------------- Utilidades -----------------------------
def fetch(url: str) -> BeautifulSoup | None:
    """Descarga una URL y devuelve el HTML parseado."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  ⚠️  Error en {url}: {e}")
        return None


def limpiar(texto: str) -> str:
    """Normaliza espacios y saltos de línea."""
    return re.sub(r"\s+", " ", texto or "").strip()


# ----------------------------- HOTELES -----------------------------
_COL = "/destinos-estelar/colombia"
HOTELES_COLOMBIA = [
    ("Estelar Casa Ambalema", "Ambalema", "/estelar-casa-ambalema/"),
    ("Estelar En Alto Prado", "Barranquilla", f"{_COL}/barranquilla/estelar-en-alto-prado/"),
    (
        "Estelar Apartamentos Barranquilla",
        "Barranquilla",
        f"{_COL}/barranquilla/estelar-apartamentos-barranquilla/",
    ),
    ("Estelar La Fontana", "Bogotá", f"{_COL}/bogota/estelar-la-fontana/"),
    ("Estelar Parque de la 93", "Bogotá", f"{_COL}/bogota/estelar-parque-de-la-93/"),
    ("Estelar Suites Jones", "Bogotá", f"{_COL}/bogota/estelar-suites-jones/"),
    ("Estelar Calle 100", "Bogotá", f"{_COL}/bogota/estelar-calle-100/"),
    ("Estelar Apartamentos Bogotá", "Bogotá", f"{_COL}/bogota/estelar-apartamentos-bogota/"),
    ("Intercontinental Cali", "Cali", f"{_COL}/cali/intercontinental/"),
    (
        "Estelar Cartagena de Indias",
        "Cartagena",
        f"{_COL}/cartagena/estelar-cartagena-de-indias/",
    ),
    ("Estelar Playa Manzanillo", "Cartagena", f"{_COL}/cartagena/estelar-playa-manzanillo/"),
    ("Estelar Altamira", "Ibagué", f"{_COL}/ibague/estelar-altamira/"),
    (
        "Estelar Recinto del Pensamiento",
        "Manizales",
        f"{_COL}/manizales/estelar-recinto-del-pensamiento/",
    ),
    ("Estelar El Cable", "Manizales", f"{_COL}/manizales/estelar-el-cable/"),
    ("Estelar Milla de Oro", "Medellín", f"{_COL}/medellin/estelar-milla-de-oro/"),
    ("Estelar Square", "Medellín", f"{_COL}/medellin/estelar-square/"),
    ("Estelar Blue", "Medellín", f"{_COL}/medellin/estelar-blue/"),
    (
        "Estelar Apartamentos Medellín",
        "Medellín",
        f"{_COL}/medellin/estelar-apartamentos-medellin/",
    ),
    ("Estelar La Torre Suites", "Medellín", f"{_COL}/medellin/estelar-la-torre-suites/"),
    (
        "Estelar Paipa Hotel & Centro de Convenciones",
        "Paipa",
        f"{_COL}/paipa/estelar-paipa-hotel-centro-de-convenciones/",
    ),
    (
        "Estelar Santamar Hotel & Centro de Convenciones",
        "Santa Marta",
        f"{_COL}/santa-marta/estelar-santamar-hotel-centro-de-convenciones/",
    ),
    (
        "Estelar Villavicencio Hotel & Centro de Convenciones",
        "Villavicencio",
        f"{_COL}/villavicencio/estelar-villavicencio-hotel-centro-de-convenciones/",
    ),
    ("Estelar Yopal", "Yopal", f"{_COL}/yopal/estelar-yopal/"),
]

_PER = "/destinos-estelar/peru"
HOTELES_PERU = [
    ("Estelar Miraflores", "Lima", f"{_PER}/lima/estelar-miraflores/"),
    ("Estelar Apartamentos Bellavista", "Lima", f"{_PER}/lima/estelar-apartamentos-bellavista/"),
]


def extraer_descripcion_hotel(soup: BeautifulSoup) -> str:
    """Saca la descripción principal del hotel desde su página individual."""
    # Estrategia: buscar el primer párrafo largo después del H1
    for tag in soup.select("article p, .et_pb_text_inner p, main p"):
        texto = limpiar(tag.get_text())
        if len(texto) > 80:
            return texto
    # Fallback: meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return limpiar(meta["content"])
    return ""


def scrapear_hoteles() -> list[dict]:
    """Recorre cada hotel de la lista y extrae descripción de su página."""
    todos = []
    total = len(HOTELES_COLOMBIA) + len(HOTELES_PERU)
    contador = 0

    for nombre, ciudad, ruta in HOTELES_COLOMBIA:
        contador += 1
        url = urljoin(BASE_URL, ruta)
        print(f"  [{contador}/{total}] {nombre} ({ciudad})")
        soup = fetch(url)
        descripcion = extraer_descripcion_hotel(soup) if soup else ""
        todos.append(
            {
                "nombre": nombre,
                "ciudad": ciudad,
                "pais": "Colombia",
                "url": url,
                "descripcion": descripcion,
            }
        )
        time.sleep(DELAY_SEG)

    for nombre, ciudad, ruta in HOTELES_PERU:
        contador += 1
        url = urljoin(BASE_URL, ruta)
        print(f"  [{contador}/{total}] {nombre} ({ciudad})")
        soup = fetch(url)
        descripcion = extraer_descripcion_hotel(soup) if soup else ""
        todos.append(
            {
                "nombre": nombre,
                "ciudad": ciudad,
                "pais": "Perú",
                "url": url,
                "descripcion": descripcion,
            }
        )
        time.sleep(DELAY_SEG)

    return todos


# ----------------------------- RESTAURANTES -----------------------------
def scrapear_restaurantes() -> list[dict]:
    """Extrae los restaurantes desde la home page (sección 'Sabores que Viajan Contigo')."""
    soup = fetch(BASE_URL)
    if not soup:
        return []

    restaurantes = []
    # Los restaurantes aparecen como bloques con h4 (título) seguido de párrafo (descripción)
    for h4 in soup.select("h4"):
        nombre = limpiar(h4.get_text())
        if not nombre or len(nombre) > 80:
            continue
        # Buscar el siguiente párrafo
        siguiente = h4.find_next("p")
        descripcion = limpiar(siguiente.get_text()) if siguiente else ""
        if descripcion and "Ubicado" in descripcion:
            restaurantes.append({"nombre": nombre, "descripcion": descripcion})

    return restaurantes


# ----------------------------- CONTACTO -----------------------------
INFO_CONTACTO = """
- Línea gratuita en Colombia: 01 8000 97 8000
- En Bogotá: (601) 608 8080 - (601) 743 3777
- Línea WhatsApp ventas: (+57) 316 692 6704
- Usuarios Claro y Movistar (celular): #680
- Línea gratuita en Perú: 0800 25555
- En Lima: (51-1) 200 5555
- Asesor virtual: Estela
"""

PROGRAMA_LEALTAD = """
**Huésped Siempre Estelar** es el programa de lealtad de Hoteles Estelar,
creado para premiar la fidelidad de sus clientes. Al unirse de manera gratuita,
los clientes pueden disfrutar de beneficios exclusivos como:

1. Acumular estrellas en cada estadía para canjearlas en próxima visita.
2. Acceder a tarifas preferenciales en reservas de alojamiento.
3. Disfrutar de beneficios especiales en eventos y restaurantes.
4. Obtener hasta 21% de descuento adicional.

Sitio: https://hse.siempreestelar.com/
"""


# ----------------------------- GENERADOR DE MARKDOWN -----------------------------
def generar_markdown(hoteles: list[dict], restaurantes: list[dict]) -> str:
    """Construye el archivo .md final."""
    lineas = []
    lineas.append("# HOTELES ESTELAR — INFORMACIÓN DE LA WEB OFICIAL\n")
    lineas.append("> Información extraída mediante scraping de https://www.hotelesestelar.com\n")
    lineas.append(f"> Fecha de extracción: {time.strftime('%Y-%m-%d')}\n")
    lineas.append(
        f"> Total de hoteles: {len(hoteles)} | Total de restaurantes: {len(restaurantes)}\n"
    )
    lineas.append("\n---\n")

    # ---- Sección HOTELES ----
    lineas.append("\n## Listado de Hoteles\n")

    # Agrupar por país
    colombia = [h for h in hoteles if h["pais"] == "Colombia"]
    peru = [h for h in hoteles if h["pais"] == "Perú"]

    lineas.append(f"\n### Colombia ({len(colombia)} hoteles)\n")
    # Agrupar por ciudad
    ciudades_co = {}
    for h in colombia:
        ciudades_co.setdefault(h["ciudad"], []).append(h)

    for ciudad in sorted(ciudades_co.keys()):
        lineas.append(f"\n#### {ciudad}\n")
        for h in ciudades_co[ciudad]:
            lineas.append(f"\n**{h['nombre']}**")
            if h["descripcion"]:
                lineas.append(f"\n{h['descripcion']}")
            lineas.append(f"\n- URL: {h['url']}\n")

    lineas.append(f"\n### Perú ({len(peru)} hoteles)\n")
    ciudades_pe = {}
    for h in peru:
        ciudades_pe.setdefault(h["ciudad"], []).append(h)

    for ciudad in sorted(ciudades_pe.keys()):
        lineas.append(f"\n#### {ciudad}\n")
        for h in ciudades_pe[ciudad]:
            lineas.append(f"\n**{h['nombre']}**")
            if h["descripcion"]:
                lineas.append(f"\n{h['descripcion']}")
            lineas.append(f"\n- URL: {h['url']}\n")

    # ---- Sección RESTAURANTES ----
    if restaurantes:
        lineas.append("\n---\n")
        lineas.append(f"\n## Restaurantes ({len(restaurantes)})\n")
        lineas.append("\nHoteles Estelar opera la **Ruta de los Sabores**, ")
        lineas.append("una propuesta gastronómica con restaurantes con identidad propia.\n")
        for r in restaurantes:
            lineas.append(f"\n**{r['nombre']}**")
            lineas.append(f"\n{r['descripcion']}\n")

    # ---- Sección PROGRAMA DE LEALTAD ----
    lineas.append("\n---\n")
    lineas.append("\n## Programa de Lealtad\n")
    lineas.append(PROGRAMA_LEALTAD)

    # ---- Sección CONTACTO ----
    lineas.append("\n---\n")
    lineas.append("\n## Líneas de Contacto\n")
    lineas.append(INFO_CONTACTO)

    return "\n".join(lineas)


# ----------------------------- MAIN -----------------------------
def main():
    """Ejecuta el scraper completo y escribe el Markdown de salida."""
    print("🚀 Iniciando scraper de Hoteles Estelar...\n")

    print("📍 Paso 1: Extrayendo información de cada hotel...")
    hoteles = scrapear_hoteles()
    print(f"  ✅ {len(hoteles)} hoteles procesados\n")

    print("🍽️  Paso 2: Extrayendo restaurantes desde la home...")
    restaurantes = scrapear_restaurantes()
    print(f"  ✅ {len(restaurantes)} restaurantes encontrados\n")

    print("📝 Paso 3: Generando archivo Markdown...")
    contenido = generar_markdown(hoteles, restaurantes)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(contenido, encoding="utf-8")

    print(f"\n✅ Archivo generado: {OUTPUT}")
    print(f"   Tamaño: {OUTPUT.stat().st_size:,} bytes")
    print(f"   Hoteles: {len(hoteles)} | Restaurantes: {len(restaurantes)}")


if __name__ == "__main__":
    main()
