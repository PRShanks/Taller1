"""
Web Scraper - Hoteles Estelar S.A.
Extrae información estática de cada hotel  y habitaciones
con precios en tiempo real desde el motor de reservas 
Salida: hoteles.json y hoteles.md
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

# ---------------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------------
BASE_URL = "https://www.hotelesestelar.com"
BOOKING_BASE = "https://bookings.hotelesestelar.com/es/bookcore/availability"
CARPETA = Path(__file__).parent

HOY = datetime.now()
FECHA_ENTRADA = (HOY + timedelta(days=1)).strftime("%Y-%m-%d")
FECHA_SALIDA = (HOY + timedelta(days=2)).strftime("%Y-%m-%d")
HUESPEDES = 2

DELAY_ESTATICO = 1.5   # segundos entre requests HTTP (Fase 1)
DELAY_BOOKING = 3      # segundos entre hoteles en el motor de reservas (Fase 2)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Variantes ortográficas / sinónimos que deben normalizarse a una etiqueta canónica
ALIAS_SERVICIOS = {
    "lavanderia":        "Lavandería",
    "lavandería":        "Lavandería",
    "elevador":          "Ascensor",
    "ascensor":          "Ascensor",
    "salon de eventos":  "Salón de Eventos",
    "salón de eventos":  "Salón de Eventos",
    "mascotas":          "Pet Friendly",
    "pet friendly":      "Pet Friendly",
    "secador":           "Secador de Cabello",
    "balcon":            "Balcón",
    "balcón":            "Balcón",
    "vista al rio":      "Vista al Río",
    "wifi":              "WiFi",
}

KEYWORDS_SERVICIOS = [
    "wifi", "piscina", "gimnasio", "spa", "parqueadero",
    "restaurante", "bar", "lavandería", "lavanderia",
    "ascensor", "elevador", "business center",
    "salón de eventos", "salon de eventos",
    "centro de convenciones", "mascotas", "pet friendly",
    "transporte", "concierge", "room service", "televisor",
    "aire acondicionado", "minibar", "caja fuerte",
    "secador", "terraza", "balcón", "balcon",
    "vista al mar", "vista al rio", "jacuzzi",
]

# Nombres genéricos que el motor de reservas muestra pero no son tipos de habitación
NOMBRES_HAB_IGNORAR = {
    "habitaciones", "habitacion", "rooms", "room",
    "mejor precio disponible", "mejor precio", "best available rate",
    "precio especial", "oferta", "promocion", "promoción",
    "siempre estelar", "tarifa",
}
NOMBRES_HAB_IGNORAR_PARTIAL = [
    "quedan", "queda ", "solo quedan", "disponib",
    "seleccionar", "ver detalle", "ver mas", "ver más",
    "añadir", "agregar", "reservar",
    "precio desde", "price from", "desde cop", "desde usd",
    "midnight sale", "weekend ", "dcto", "descuento",
    "tarifa flexible", "tarifa especial", "tarifa corp",
]


# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------

def limpiar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip() if texto else ""


def get_soup(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [ERROR] {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Fase 1 — Información estática
# ---------------------------------------------------------------------------

def extraer_lista_hoteles(soup: BeautifulSoup) -> list[dict]:
    """Lee el menú principal y devuelve la lista de hoteles con su URL."""
    hoteles, vistos = [], set()
    patron = re.compile(r"/destinos-estelar/([^/]+)/([^/]+)/([^/]+)/?$")

    for a in soup.find_all("a", href=True):
        m = patron.search(a["href"])
        if not m:
            continue
        url = a["href"] if a["href"].startswith("http") else BASE_URL + a["href"]
        if url in vistos:
            continue
        vistos.add(url)

        pais   = m.group(1).replace("-", " ").title()
        ciudad = m.group(2).replace("-", " ").title()
        slug   = m.group(3)
        nombre = limpiar_texto(a.get_text()) or slug.replace("-", " ").title()

        hoteles.append({"nombre": nombre, "ciudad": ciudad, "pais": pais,
                        "url": url, "slug": slug})
    return hoteles


def extraer_detalle_hotel(url: str) -> dict:
    """Descarga la página de un hotel y extrae todos los campos estáticos."""
    soup = get_soup(url)
    if not soup:
        return {"error": "No se pudo obtener la página"}

    datos = {}
    texto_completo = soup.get_text()

    # Descripción — primer párrafo sustancial sin textos de sistema
    descripcion = ""
    for tag in ["p", "div"]:
        for elem in soup.find_all(tag):
            t = limpiar_texto(elem.get_text())
            if len(t) > 80 and not any(s in t.lower() for s in
                    ["cookie", "política", "privacy", "©", "reserva", "javascript"]):
                descripcion = t
                break
        if descripcion:
            break
    datos["descripcion"] = descripcion

    # Dirección — el sitio coloca la dirección junto a Icon_Location.png
    direccion = ""
    patron_tel_inline = re.compile(r"\(?\d{3}\)?\s*\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}")
    for img in soup.find_all("img", src=re.compile(r"location|ubicacion|pin|map", re.I)):
        parent = img.parent
        for tag in parent.find_all("img"):
            tag.decompose()
        texto = limpiar_texto(parent.get_text())
        if len(texto) > 5:
            texto = patron_tel_inline.sub("", texto).strip()
            texto = limpiar_texto(texto)
            if len(texto) > 5:
                direccion = texto
                break
        siguiente = img.next_sibling
        if siguiente:
            texto = limpiar_texto(str(siguiente))
            texto = patron_tel_inline.sub("", texto).strip()
            if len(texto) > 5:
                direccion = limpiar_texto(texto)
                break
    datos["direccion"] = direccion

    # Teléfono
    telefono = ""
    patron_tel = re.compile(r"\(?\d{3}\)?\s*\d{3,4}[\s\-]?\d{4}")
    for elem in soup.find_all(string=patron_tel):
        m = patron_tel.search(str(elem))
        if m:
            telefono = m.group().strip()
            break
    if not telefono:
        for a in soup.find_all("a", href=re.compile(r"^tel:")):
            telefono = a["href"].replace("tel:", "").strip()
            break
    datos["telefono"] = telefono

    # RNT
    m_rnt = re.search(r"RNT\s*[:\-]?\s*(\d+)", texto_completo)
    datos["rnt"] = m_rnt.group(1) if m_rnt else ""

    # Rating y reseñas
    m_rating = re.search(r"(\d[,.]?\d?)\s*/\s*5", texto_completo)
    datos["rating"] = m_rating.group(1) if m_rating else ""
    m_res = re.search(r"([\d.,]+)\s*(reseñas|reviews|opiniones)", texto_completo, re.I)
    datos["num_resenas"] = (m_res.group(1).replace(".", "").replace(",", "")
                            if m_res else "")

    # Servicios
    servicios, etiquetas_vistas = [], set()
    texto_lower = texto_completo.lower()
    for keyword in KEYWORDS_SERVICIOS:
        if keyword in texto_lower:
            etiqueta = ALIAS_SERVICIOS.get(keyword, keyword.title())
            if etiqueta not in etiquetas_vistas:
                servicios.append(etiqueta)
                etiquetas_vistas.add(etiqueta)
    datos["servicios"] = servicios

    # Restaurantes — solo headings con nombres propios (no frases genéricas)
    restaurantes = []
    ignorar_resto = {
        "restaurante", "restaurantes", "bar", "bares", "café", "cafes", "cafés",
        "nuestros restaurantes", "conoce nuestros", "ver más", "ver mas",
        "nuestros bares", "gastronomia", "gastronomía",
    }
    for elem in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
        texto = limpiar_texto(elem.get_text())
        tl = texto.lower().strip()
        if any(kw in tl for kw in ["restaurante", "bar", "café", "cafe",
                                    "bistro", "grill", "sky bar", "lounge"]):
            if 4 < len(texto) < 50 and tl not in ignorar_resto:
                if not elem.find_parent(class_=re.compile(r"content|body|entry|post", re.I)):
                    restaurantes.append(texto)
                elif elem.name in ["h2", "h3", "h4"]:
                    restaurantes.append(texto)
    datos["restaurantes"] = list(dict.fromkeys(restaurantes))

    # Email
    email = ""
    m_email = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
                        texto_completo)
    if m_email:
        candidato = m_email.group()
        if not any(s in candidato for s in ["example", "wordpress", "plugin", "schema"]):
            email = candidato
    datos["email"] = email

    # WhatsApp
    whatsapp = ""
    for a in soup.find_all("a", href=re.compile(r"wa\.me|whatsapp", re.I)):
        whatsapp = a["href"]
        break
    datos["whatsapp"] = whatsapp

    # Tour 3D (Matterport)
    tour_3d = ""
    for iframe in soup.find_all("iframe", src=re.compile(r"matterport", re.I)):
        tour_3d = iframe.get("src", "")
        break
    if not tour_3d:
        for a in soup.find_all("a", href=re.compile(r"matterport", re.I)):
            tour_3d = a["href"]
            break
    datos["tour_3d"] = tour_3d

    # Booking slug y URL — el slug es distinto al slug del sitio principal
    booking_slug = ""
    booking_url = ""
    patron_booking = re.compile(
        r"bookings\.hotelesestelar\.com/\w+/bookcore/availability/([^/?]+)", re.I
    )
    for a in soup.find_all("a", href=patron_booking):
        m = patron_booking.search(a["href"])
        if not m:
            continue
        candidato = m.group(1)
        if candidato.lower() == "tomorrow" or re.match(r"\d{4}-\d{2}-\d{2}", candidato):
            m2 = re.search(
                r"bookings\.hotelesestelar\.com/\w+/bookcore/availability/[^/]+/([^/?]+)",
                a["href"], re.I,
            )
            candidato = m2.group(1) if m2 else candidato
        if re.match(r"\d", candidato):
            continue
        booking_slug = candidato
        booking_url = a["href"].split("?")[0].rstrip("/") + "/"
        break
    datos["booking_slug"] = booking_slug
    datos["booking_url"] = booking_url

    return datos


# ---------------------------------------------------------------------------
# Fase 2 — Habitaciones y precios (Playwright)
# ---------------------------------------------------------------------------

def _aceptar_cookies(page: Page):
    try:
        btn = page.locator("button, a").filter(
            has_text=re.compile(r"acepto|accept|aceptar|ok", re.I)
        ).first
        btn.click(timeout=3000)
    except Exception:
        pass


def _parsear_precio(texto: str) -> tuple[str, str, str]:
    """
    Extrae (precio_original, precio_final, moneda) de un bloque de texto de tarifa.
    Soporta ambos formatos: 'US$ 167,00' y '167,00 US$'.
    Si hay descuento, precio_final es el precio con descuento; si no es igual al original.
    """
    SIM = r"US[$]|USD|COP|PEN|S/[.]|[$]"
    # Número con al menos 3 dígitos antes del separador para evitar capturar porcentajes (33.7%)
    NUM = r"[\d]{1,3}(?:[.,][\d]{3})*[,.][\d]{2,3}"
    # Formato A: moneda primero  → US$ 1.291,08  o  COP 968.956
    pat_a = re.compile(rf"({SIM})\s*({NUM})(?!\s*%)", re.I)
    # Formato B: número primero  → 1.291,08 US$
    pat_b = re.compile(rf"({NUM})\s*({SIM})", re.I)

    # Recoger todos los precios (valor, símbolo) independientemente del orden
    precios = []
    for m in pat_a.finditer(texto):
        precios.append((m.group(2), m.group(1), m.start()))
    for m in pat_b.finditer(texto):
        precios.append((m.group(1), m.group(2), m.start()))
    # Ordenar por posición en el texto
    precios.sort(key=lambda x: x[2])

    moneda = "USD"
    if precios:
        sym = precios[0][1].upper()
        if "COP" in sym:
            moneda = "COP"
        elif "PEN" in sym or "S/." in sym:
            moneda = "PEN"

    precio_original = precios[0][0] if precios else ""

    # Precio con descuento: aparece tras la etiqueta explícita
    precio_final = precio_original
    m_desc = re.search(
        rf"Precio con descuento\s*(?:{SIM})?\s*({NUM})|"
        rf"(?:{SIM})\s*({NUM})\s*Anadir",   # algunos hoteles ponen el precio final antes de "Añadir"
        texto, re.I,
    )
    if m_desc:
        precio_final = m_desc.group(1) or m_desc.group(2) or precio_original

    return precio_original, precio_final, moneda


def extraer_habitaciones(page: Page, booking_slug: str) -> list[dict]:
    """Navega al motor de reservas y devuelve los tipos de habitación con precios."""
    url = f"{BOOKING_BASE}/{booking_slug}/{FECHA_ENTRADA}/{FECHA_SALIDA}/{HUESPEDES}/0/"
    print(f"    Booking: {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except PlaywrightTimeout:
        print("    [TIMEOUT] al cargar la pagina de reservas")
        return []
    except Exception as e:
        print(f"    [ERROR] {e}")
        return []

    # Esperar a que aparezca el contenedor de habitaciones (data-testid estable)
    try:
        page.wait_for_selector('[data-testid="fn-availability-item"]', timeout=12000)
    except PlaywrightTimeout:
        page.wait_for_timeout(5000)

    _aceptar_cookies(page)

    soup = BeautifulSoup(page.content(), "html.parser")

    # Cada figura es un tipo de habitación
    figuras = soup.find_all("figure", attrs={"data-testid": "fn-availability-item"})
    habitaciones = []

    for fig in figuras:
        # Nombre del tipo de habitación
        nombre_hab = ""
        for tag in ["h1", "h2", "h3", "h4"]:
            h = fig.find(tag)
            if h:
                nombre_hab = re.sub(r"[^\w\s\-\.,()/áéíóúÁÉÍÓÚñÑ]", "",
                                    h.get_text(strip=True)).strip()
                if len(nombre_hab) > 3:
                    break

        if not nombre_hab:
            continue

        # Capacidad
        capacidad = ""
        m_c = re.search(r"(\d)\s*(Adult|Adulto|persona|guest|pax)", fig.get_text(), re.I)
        if m_c:
            capacidad = m_c.group(1)

        # Planes de tarifa dentro de esta habitación
        planes = fig.find_all("div", attrs={"data-testid": "fn-accordion"})

        # Si no hay planes, registrar la habitación sin tarifas
        if not planes:
            habitaciones.append({
                "nombre": nombre_hab,
                "precio_original": "",
                "precio_final": "",
                "tiene_descuento": False,
                "moneda": "",
                "disponibilidad": "",
                "capacidad_personas": capacidad,
            })
            continue

        for plan in planes:
            # Nombre del plan de tarifa
            h3 = plan.find("h3")
            nombre_plan = re.sub(r"[^\w\s\-\.,()/áéíóúÁÉÍÓÚñÑ]", "",
                                 h3.get_text(strip=True)).strip() if h3 else ""

            # Disponibilidad ("Quedan X habitaciones") — solo aparece cuando es baja
            disp_elem = plan.find("div", class_=re.compile(r"RemainingRoom", re.I))
            disponibilidad = disp_elem.get_text(strip=True) if disp_elem else ""

            # Precios
            texto_plan = plan.get_text(" ", strip=True)
            precio_original, precio_final, moneda = _parsear_precio(texto_plan)
            tiene_descuento = precio_original != precio_final and bool(precio_original)

            habitaciones.append({
                "nombre": nombre_hab,
                "plan_tarifa": nombre_plan,
                "precio_original": precio_original,
                "precio_final": precio_final,
                "tiene_descuento": tiene_descuento,
                "moneda": moneda,
                "disponibilidad": disponibilidad,
                "capacidad_personas": capacidad,
            })

    return habitaciones


# ---------------------------------------------------------------------------
# Exportadores
# ---------------------------------------------------------------------------

def exportar_json(hoteles: list[dict], ruta: str):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generado_en": datetime.now().isoformat(),
                "fecha_consulta_precios": FECHA_ENTRADA,
                "huespedes_consulta": HUESPEDES,
                "total_hoteles": len(hoteles),
                "hoteles": hoteles,
            },
            f, ensure_ascii=False, indent=2,
        )
    print(f"[OK] JSON guardado en: {ruta}")


def exportar_markdown(hoteles: list[dict], ruta: str):
    lineas = [
        "# Hoteles Estelar S.A. — Directorio Completo",
        f"\n> Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}  ",
        f"> Precios para: **{FECHA_ENTRADA}** | {HUESPEDES} huespedes  ",
        f"> Total propiedades: **{len(hoteles)}**\n",
        "---\n",
        "## Indice\n",
    ]

    # Índice agrupado por país y ciudad
    por_pais: dict = {}
    for h in hoteles:
        por_pais.setdefault(h["pais"], {}).setdefault(h["ciudad"], []).append(h)

    for pais, ciudades in sorted(por_pais.items()):
        lineas.append(f"### {pais}")
        for ciudad, lista in sorted(ciudades.items()):
            lineas.append(f"- **{ciudad}**")
            for h in lista:
                anchor = re.sub(r"[^a-z0-9\-]", "",
                    h["nombre"].lower()
                    .replace(" ", "-")
                    .replace("á","a").replace("é","e")
                    .replace("í","i").replace("ó","o").replace("ú","u"))
                lineas.append(f"  - [{h['nombre']}](#{anchor})")
        lineas.append("")

    lineas.append("---\n")

    for h in hoteles:
        lineas.append(f"## {h['nombre']}")
        lineas.append(f"**Pais:** {h['pais']} | **Ciudad:** {h['ciudad']}\n")

        if h.get("direccion"):
            lineas.append(f"**Direccion:** {h['direccion']}  ")
        if h.get("telefono"):
            lineas.append(f"**Telefono:** {h['telefono']}  ")
        if h.get("email"):
            lineas.append(f"**Email:** {h['email']}  ")
        if h.get("whatsapp"):
            lineas.append(f"**WhatsApp:** {h['whatsapp']}  ")
        if h.get("rnt"):
            lineas.append(f"**RNT:** {h['rnt']}  ")
        if h.get("rating"):
            lineas.append(f"**Rating:** {h['rating']}/5  ")
        if h.get("num_resenas"):
            lineas.append(f"**Resenas:** {h['num_resenas']}  ")

        lineas.append(f"\n**URL:** [{h['url']}]({h['url']})\n")

        if h.get("descripcion"):
            lineas.append(f"### Descripcion\n{h['descripcion']}\n")

        if h.get("servicios"):
            lineas.append("### Servicios")
            for s in h["servicios"]:
                lineas.append(f"- {s}")
            lineas.append("")

        if h.get("restaurantes"):
            lineas.append("### Restaurantes y Bares")
            for r in h["restaurantes"]:
                lineas.append(f"- {r}")
            lineas.append("")

        habitaciones = h.get("habitaciones", [])
        if habitaciones:
            lineas.append("### Habitaciones y Precios")
            lineas.append(f"*Consulta: {FECHA_ENTRADA} | {HUESPEDES} huespedes*\n")
            lineas.append("| Habitacion | Plan | Precio Original | Precio Final | Descuento | Moneda | Disponibilidad | Cap. |")
            lineas.append("|---|---|---|---|---|---|---|---|")
            for hab in habitaciones:
                cap = hab.get("capacidad_personas") or "-"
                disp = hab.get("disponibilidad") or "-"
                dcto = "Si" if hab.get("tiene_descuento") else "No"
                lineas.append(
                    f"| {hab.get('nombre','-')} "
                    f"| {hab.get('plan_tarifa','-')} "
                    f"| {hab.get('precio_original','-')} "
                    f"| {hab.get('precio_final','-')} "
                    f"| {dcto} "
                    f"| {hab.get('moneda','-')} "
                    f"| {disp} "
                    f"| {cap} |"
                )
            lineas.append("")
        else:
            lineas.append("### Habitaciones\n*Sin datos de habitaciones.*\n")

        if h.get("booking_url"):
            lineas.append(f"**Reservas:** [{h['booking_url']}]({h['booking_url']})  ")

        if h.get("tour_3d"):
            lineas.append(f"### Tour Virtual 3D\n[Ver Tour]({h['tour_3d']})\n")

        if h.get("error"):
            lineas.append(f"> **Error:** {h['error']}\n")

        lineas.append("---\n")

    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"[OK] Markdown guardado en: {ruta}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Hoteles Estelar — Web Scraper Completo")
    print(f"  Inicio : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Precios: {FECHA_ENTRADA} | {HUESPEDES} huespedes")
    print("=" * 60)

    # ── Fase 1: datos estáticos ──────────────────────────────────────────
    print("\n[1/4] Obteniendo lista de hoteles...")
    soup_principal = get_soup(BASE_URL)
    if not soup_principal:
        print("[FATAL] No se pudo acceder a la pagina principal.")
        return

    hoteles = extraer_lista_hoteles(soup_principal)
    print(f"  -> {len(hoteles)} hoteles encontrados")

    print(f"\n[2/4] Extrayendo informacion estatica ({len(hoteles)} hoteles)...")
    for i, hotel in enumerate(hoteles, 1):
        print(f"  [{i:>2}/{len(hoteles)}] {hotel['nombre']} ({hotel['ciudad']})")
        hotel.update(extraer_detalle_hotel(hotel["url"]))
        if i < len(hoteles):
            time.sleep(DELAY_ESTATICO)

    # ── Fase 2: habitaciones y precios ───────────────────────────────────
    print(f"\n[3/4] Extrayendo habitaciones y precios (Playwright)...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="es-CO",
        )
        page = ctx.new_page()

        for i, hotel in enumerate(hoteles, 1):
            print(f"  [{i:>2}/{len(hoteles)}] {hotel['nombre']}")
            slug = hotel.get("booking_slug", "")
            if slug:
                hotel["habitaciones"] = extraer_habitaciones(page, slug)
            else:
                print("    [SKIP] Sin booking_slug")
                hotel["habitaciones"] = []
            if i < len(hoteles):
                time.sleep(DELAY_BOOKING)

        ctx.close()
        browser.close()

    # ── Exportar ─────────────────────────────────────────────────────────
    print("\n[4/4] Exportando resultados...")
    exportar_json(hoteles, str(CARPETA / "hoteles.json"))
    exportar_markdown(hoteles, str(CARPETA / "hoteles.md"))

    con_hab  = sum(1 for h in hoteles if h.get("habitaciones"))
    total_hab = sum(len(h.get("habitaciones", [])) for h in hoteles)
    print(f"\n  Hoteles con habitaciones : {con_hab}/{len(hoteles)}")
    print(f"  Total habitaciones       : {total_hab}")
    print(f"\n{'=' * 60}")
    print(f"  Fin: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Archivos: hoteles.json | hoteles.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
