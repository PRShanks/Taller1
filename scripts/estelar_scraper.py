"""
=============================================================================
HOTELES ESTELAR S.A. — WEB SCRAPER
=============================================================================
Descripción:
    Extrae información orientada a clientes (habitaciones, precios, teléfonos,
    gastronomía, políticas, servicios) de los principales hoteles Estelar
    a partir de fuentes públicas: sitios oficiales de cada hotel,
    Booking.com, Expedia, KAYAK, Momondo, Hotels.com y TripAdvisor.

Salida:
    - estelar_hoteles_raw.json   → datos crudos por hotel
    - estelar_hoteles_reporte.md → reporte en Markdown listo para el agente

"""

import json
import time
import random
import logging
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ─── Intentar importar librerías opcionales ───────────────────────────────────
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    print("⚠️  cloudscraper no instalado. Algunos sitios pueden bloquear el scraper.")
    print("   Instalar con: pip install cloudscraper")

try:
    from fake_useragent import UserAgent
    UA = UserAgent()
    HAS_FAKE_UA = True
except ImportError:
    HAS_FAKE_UA = False

# ─── Configuración ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("estelar_scraper")

OUTPUT_DIR = Path(".")
OUTPUT_JSON = OUTPUT_DIR / "estelar_hoteles_raw.json"
OUTPUT_MD   = OUTPUT_DIR / "estelar_hoteles_reporte.md"

DELAY_MIN = 2.0   # segundos mínimos entre requests
DELAY_MAX = 5.0   # segundos máximos entre requests

# User-Agents de rotación (respaldo si fake-useragent no está disponible)
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


# ─── Modelos de datos ─────────────────────────────────────────────────────────
@dataclass
class TipoHabitacion:
    nombre: str
    descripcion: str = ""
    tamano_m2: str = ""
    camas: str = ""
    precio_cop_desde: str = ""
    amenidades: list = field(default_factory=list)


@dataclass
class Restaurante:
    nombre: str
    tipo_cocina: str = ""
    servicios: str = ""          # desayuno / almuerzo / cena / 24h
    descripcion: str = ""


@dataclass
class HotelData:
    nombre: str
    ciudad: str
    pais: str = "Colombia"
    direccion: str = ""
    estrellas: str = ""
    calificacion: str = ""
    total_reseñas: str = ""
    numero_habitaciones: str = ""
    numero_pisos: str = ""
    telefono: str = ""
    email: str = ""
    web_oficial: str = ""
    checkin: str = ""
    checkout: str = ""
    precio_desde_cop: str = ""
    precio_desde_usd: str = ""
    tipos_habitacion: list = field(default_factory=list)
    restaurantes: list = field(default_factory=list)
    servicios: list = field(default_factory=list)
    politica_mascotas: str = ""
    politica_menores: str = ""
    politica_cancelacion: str = ""
    permite_fumar: bool = False
    distancia_aeropuerto: str = ""
    observaciones: list = field(default_factory=list)
    fuentes_scrapeadas: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ─── URLs objetivo por hotel ──────────────────────────────────────────────────
HOTELES_URLS = {
    "InterContinental Cali": {
        "ciudad": "Cali",
        "fuentes": [
            "https://www.ihg.com/intercontinental/hotels/es/es/cali/cloha/hoteldetail",
            "https://www.ihg.com/intercontinental/hotels/es/es/cali/cloha/hoteldetail/rooms",
            "https://www.ihg.com/intercontinental/hotels/es/es/cali/cloha/hoteldetail/amenities",
            "https://www.booking.com/hotel/co/intercontinental-cali.es.html",
        ],
    },
    "ESTELAR Parque de la 93": {
        "ciudad": "Bogotá",
        "fuentes": [
            "https://www.estelarparquedela93.com/es/",
            "https://www.estelarparquedela93.com/es/habitaciones/",
            "https://www.booking.com/hotel/co/estelar-parque-de-la-93.es.html",
        ],
    },
    "ESTELAR La Fontana": {
        "ciudad": "Bogotá",
        "fuentes": [
            "https://www.estelarlafontana.com/es/",
            "https://www.estelarlafontana.com/es/habitaciones/",
            "https://www.booking.com/hotel/co/la-fontana.es.html",
        ],
    },
    "ESTELAR Calle 100": {
        "ciudad": "Bogotá",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/bogota/estelar-calle-100/",
        ],
    },
    "ESTELAR Suites Jones": {
        "ciudad": "Bogotá",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/bogota/suites-jones/",
        ],
    },
    "ESTELAR Cartagena de Indias": {
        "ciudad": "Cartagena",
        "fuentes": [
            "https://www.estelarcartagenadeindias.com/es/",
            "https://www.estelarcartagenadeindias.com/es/habitaciones/",
            "https://www.booking.com/hotel/co/estelar-cartagena-de-indias-y-centro-de-convenciones.es.html",
        ],
    },
    "ESTELAR Santamar Santa Marta": {
        "ciudad": "Santa Marta",
        "fuentes": [
            "https://www.estelarsantamar.com/es/",
            "https://www.estelarsantamar.com/es/habitaciones/",
            "https://www.estelarsantamar.com/es/servicios/",
            "https://www.booking.com/hotel/co/santamar-centro-de-convenciones.es.html",
        ],
    },
    "ESTELAR Milla de Oro": {
        "ciudad": "Medellín",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/medellin/milla-de-oro/",
            "https://www.booking.com/hotel/co/milla-de-oro-medellin.es.html",
        ],
    },
    "ESTELAR Square": {
        "ciudad": "Medellín",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/medellin/estelar-square/",
        ],
    },
    "ESTELAR Blue": {
        "ciudad": "Medellín",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/medellin/estelar-blue/",
        ],
    },
    "ESTELAR La Torre Suites": {
        "ciudad": "Medellín",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/medellin/la-torre-suites/",
        ],
    },
    "ESTELAR Alto Prado Barranquilla": {
        "ciudad": "Barranquilla",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/barranquilla/estelar-alto-prado/",
            "https://www.booking.com/hotel/co/estelar-alto-prado-barranquilla.es.html",
        ],
    },
    "ESTELAR Paipa": {
        "ciudad": "Paipa",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/paipa/",
        ],
    },
    "ESTELAR Recinto del Pensamiento": {
        "ciudad": "Manizales",
        "fuentes": [
            "https://www.hotelesestelar.com/destinos-estelar/colombia/manizales/recinto-del-pensamiento/",
        ],
    },
}


# ─── Clase principal: HTTP Session con rotación de headers ───────────────────
class EstelarScraper:
    """
    Scraper con:
    - Rotación de User-Agent
    - Headers realistas (Accept, Accept-Language, Referer)
    - Delays aleatorios entre requests
    - Reintentos automáticos con backoff exponencial
    - Soporte opcional para cloudscraper (para sitios con Cloudflare)
    """

    def __init__(self, use_cloudscraper: bool = True):
        self.session = requests.Session()
        self.use_cs = use_cloudscraper and HAS_CLOUDSCRAPER
        if self.use_cs:
            self.cs = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            log.info("cloudscraper activado para sitios con Cloudflare")

    def _get_ua(self) -> str:
        if HAS_FAKE_UA:
            try:
                return UA.random
            except Exception:
                pass
        return random.choice(FALLBACK_USER_AGENTS)

    def _headers(self, referer: str = "https://www.google.com") -> dict:
        return {
            "User-Agent": self._get_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": referer,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
        }

    def get(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """
        GET con reintentos y backoff exponencial.
        Devuelve un objeto BeautifulSoup o None si falla.
        """
        for attempt in range(1, retries + 1):
            try:
                delay = random.uniform(DELAY_MIN, DELAY_MAX)
                log.info(f"[{attempt}/{retries}] GET {url[:80]}... (espera {delay:.1f}s)")
                time.sleep(delay)

                if self.use_cs:
                    resp = self.cs.get(url, headers=self._headers(url), timeout=20)
                else:
                    resp = self.session.get(
                        url, headers=self._headers(url), timeout=20
                    )

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    return soup
                elif resp.status_code == 403:
                    log.warning(f"403 Forbidden — {url}")
                    return None
                elif resp.status_code == 429:
                    wait = 2 ** attempt * 5
                    log.warning(f"429 Rate limit — esperando {wait}s")
                    time.sleep(wait)
                else:
                    log.warning(f"HTTP {resp.status_code} — {url}")

            except requests.exceptions.Timeout:
                log.warning(f"Timeout en intento {attempt} — {url}")
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                log.warning(f"ConnectionError: {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                log.error(f"Error inesperado: {e}")
                break

        log.error(f"❌ Falló después de {retries} intentos: {url}")
        return None


# ─── Extractores específicos ──────────────────────────────────────────────────

def extraer_texto_limpio(soup: BeautifulSoup, selector: str) -> str:
    """Extrae texto de un selector CSS, devuelve string limpio."""
    el = soup.select_one(selector)
    return el.get_text(separator=" ", strip=True) if el else ""


def extraer_precio_cop(texto: str) -> str:
    """Extrae el primer valor en COP o USD del texto."""
    # Buscar patrones como "COP 310,000", "$310.000", "desde 310000"
    patrones = [
        r"COP\s*[\$]?\s*([\d.,]+)",
        r"\$\s*([\d.,]+)\s*COP",
        r"desde\s*COP\s*([\d.,]+)",
        r"desde\s*\$\s*([\d.,]+)",
        r"([\d]{3}[\.,][\d]{3})",  # formato 310.000 o 310,000
    ]
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            return m.group(1).replace(",", ".").strip()
    return ""


def parsear_estelar_oficial(soup: BeautifulSoup, hotel: HotelData) -> HotelData:
    """
    Extrae datos de las páginas oficiales de hotelesestelar.com
    o de los micrositios individuales (estelarlafontana.com, etc.)
    """
    if not soup:
        return hotel

    texto = soup.get_text(separator=" ", strip=True)

    # ── Teléfono ─────────────────────────────────────────────────────────────
    tel_match = re.search(
        r"(?:Tel[eé]fono|Tel\.|Phone|Recepci[oó]n)[:\s]*([+\d\s\(\)\-]{7,20})",
        texto, re.IGNORECASE
    )
    if tel_match and not hotel.telefono:
        hotel.telefono = tel_match.group(1).strip()

    # ── Email ─────────────────────────────────────────────────────────────────
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", texto)
    if email_match and not hotel.email:
        hotel.email = email_match.group(0)

    # ── Número de habitaciones ────────────────────────────────────────────────
    hab_match = re.search(
        r"(\d{2,4})\s*habitaci[oó]nes?", texto, re.IGNORECASE
    )
    if hab_match and not hotel.numero_habitaciones:
        hotel.numero_habitaciones = hab_match.group(1)

    # ── Número de pisos ───────────────────────────────────────────────────────
    pisos_match = re.search(
        r"(\d{1,3})\s*pisos?", texto, re.IGNORECASE
    )
    if pisos_match and not hotel.numero_pisos:
        hotel.numero_pisos = pisos_match.group(1)

    # ── Check-in / Check-out ─────────────────────────────────────────────────
    checkin_match = re.search(
        r"(?:check.?in|entrada|Registro de entrada)[:\s]*(\d{1,2}[:\s]?\d{0,2}\s*(?:PM|AM|pm|am|h)?)",
        texto, re.IGNORECASE
    )
    if checkin_match and not hotel.checkin:
        hotel.checkin = checkin_match.group(1).strip()

    checkout_match = re.search(
        r"(?:check.?out|salida|Registro de salida)[:\s]*(\d{1,2}[:\s]?\d{0,2}\s*(?:PM|AM|pm|am|h)?)",
        texto, re.IGNORECASE
    )
    if checkout_match and not hotel.checkout:
        hotel.checkout = checkout_match.group(1).strip()

    # ── Precio desde ─────────────────────────────────────────────────────────
    precio_match = re.search(
        r"[Dd]esde\s*(?:COP\s*)?([\d.,]{5,})\s*(?:COP|imp)",
        texto
    )
    if precio_match and not hotel.precio_desde_cop:
        hotel.precio_desde_cop = precio_match.group(1).replace(",", ".")

    # ── Política mascotas ─────────────────────────────────────────────────────
    if re.search(r"pet\s*friendly|mascotas?\s*bienvenid", texto, re.IGNORECASE):
        costo_match = re.search(
            r"([\d.,]+)\s*COP.*?(?:mascota|noche)", texto, re.IGNORECASE
        )
        costo = f"COP {costo_match.group(1)}/noche" if costo_match else "Con costo adicional"
        hotel.politica_mascotas = f"✅ Pet Friendly — {costo}"

    # ── Servicios ─────────────────────────────────────────────────────────────
    servicios_keywords = {
        "piscina": "Piscina",
        "gimnasio": "Gimnasio",
        "spa": "Spa",
        "jacuzzi|hidromasaje": "Jacuzzi / Hidromasaje",
        "sauna": "Sauna",
        "estacionamiento|parqueadero": "Estacionamiento",
        "wifi|wi-fi": "WiFi gratuito",
        "restaurante": "Restaurante",
        "bar": "Bar",
        "transfer|traslado al aeropuerto": "Transfer aeropuerto",
        "lavandería|tintorería": "Lavandería",
        "salón de eventos|centro de convenciones": "Centro de convenciones / Eventos",
        "business center|centro de negocios": "Centro de negocios",
        "concierge|conserje": "Conserjería",
        "room service|servicio de habitaciones": "Room service 24h",
    }
    for pattern, label in servicios_keywords.items():
        if re.search(pattern, texto, re.IGNORECASE):
            if label not in hotel.servicios:
                hotel.servicios.append(label)

    return hotel


def parsear_booking(soup: BeautifulSoup, hotel: HotelData) -> HotelData:
    """Extrae datos específicos del HTML de Booking.com."""
    if not soup:
        return hotel

    texto = soup.get_text(separator=" ", strip=True)

    # Habitaciones totales
    hab_match = re.search(r"(\d{2,4})\s*habitaci[oó]nes?", texto, re.IGNORECASE)
    if hab_match and not hotel.numero_habitaciones:
        hotel.numero_habitaciones = hab_match.group(1)

    # Precio
    precio = extraer_precio_cop(texto)
    if precio and not hotel.precio_desde_cop:
        hotel.precio_desde_cop = precio

    # Calificación
    score_match = re.search(r"(\d[,\.]\d)\s*/\s*10", texto)
    if score_match and not hotel.calificacion:
        hotel.calificacion = f"{score_match.group(1)}/10 (Booking)"

    # Reseñas
    rev_match = re.search(r"([\d.,]+)\s*(?:comentarios|opiniones|reseñas)", texto, re.IGNORECASE)
    if rev_match and not hotel.total_reseñas:
        hotel.total_reseñas = rev_match.group(1)

    # Distancia aeropuerto
    aero_match = re.search(
        r"(\d+[,.]?\d*\s*km).*?aeropuerto", texto, re.IGNORECASE
    )
    if aero_match and not hotel.distancia_aeropuerto:
        hotel.distancia_aeropuerto = aero_match.group(1)

    # Tipos de habitación desde tablas Booking
    filas = soup.select("tr.js-rt-block-row, [data-block-id], .hprt-table tr")
    for fila in filas[:10]:  # máx 10 tipos
        nombre_el = fila.select_one(".hprt-roomtype-icon-link, .room_link, [class*='room-type']")
        precio_el = fila.select_one(".bui-price-display__value, .prco-valign--middle")
        if nombre_el:
            tipo = TipoHabitacion(
                nombre=nombre_el.get_text(strip=True),
                precio_cop_desde=precio_el.get_text(strip=True) if precio_el else "",
            )
            hotel.tipos_habitacion.append(asdict(tipo))

    return hotel


def scrape_hotel(nombre: str, config: dict, scraper: EstelarScraper) -> HotelData:
    """
    Orquesta el scraping de todas las fuentes de un hotel.
    Combina resultados de múltiples páginas en un único objeto HotelData.
    """
    hotel = HotelData(
        nombre=nombre,
        ciudad=config["ciudad"],
    )

    fuentes = config.get("fuentes", [])
    log.info(f"\n{'='*60}")
    log.info(f"  🏨 Scrapeando: {nombre} ({len(fuentes)} fuentes)")
    log.info(f"{'='*60}")

    for url in fuentes:
        soup = scraper.get(url)
        if not soup:
            log.warning(f"   ↳ Sin datos de: {url}")
            continue

        hotel.fuentes_scrapeadas.append(url)

        # Elegir parser según dominio
        if "booking.com" in url:
            hotel = parsear_booking(soup, hotel)
        elif "expedia" in url or "hotels.com" in url or "kayak" in url:
            hotel = parsear_estelar_oficial(soup, hotel)
        else:
            # Sitio oficial Estelar o IHG
            hotel = parsear_estelar_oficial(soup, hotel)

        log.info(f"   ✅ OK: {url[:70]}")

    # Resumen de lo extraído
    log.info(f"   → Habitaciones: {hotel.numero_habitaciones or '?'} | "
             f"Pisos: {hotel.numero_pisos or '?'} | "
             f"Tel: {hotel.telefono or '?'} | "
             f"Precio desde: {hotel.precio_desde_cop or '?'} COP")

    return hotel


# ─── Generador de Markdown ────────────────────────────────────────────────────

def generar_markdown(hoteles: list[HotelData]) -> str:
    """Convierte la lista de objetos HotelData a un .md estructurado."""
    lineas = [
        "# 🏨 HOTELES ESTELAR S.A. — BASE DE CONOCIMIENTO PARA AGENTE",
        f"\n> Generado automáticamente el {datetime.now().strftime('%d/%m/%Y %H:%M')} mediante web scraping\n",
        "---\n",
    ]

    for hotel in hoteles:
        lineas.append(f"\n## 🏨 {hotel.nombre} — {hotel.ciudad}\n")

        # Ficha básica
        lineas.append("### Ficha Básica\n")
        lineas.append("| Campo | Detalle |")
        lineas.append("|---|---|")
        campos = [
            ("Dirección", hotel.direccion),
            ("Ciudad / País", f"{hotel.ciudad}, {hotel.pais}"),
            ("Estrellas", hotel.estrellas),
            ("Calificación", hotel.calificacion),
            ("Reseñas", hotel.total_reseñas),
            ("Habitaciones", hotel.numero_habitaciones),
            ("Pisos", hotel.numero_pisos),
            ("Teléfono", hotel.telefono),
            ("Email", hotel.email),
            ("Web oficial", hotel.web_oficial),
            ("Check-in", hotel.checkin),
            ("Check-out", hotel.checkout),
            ("Precio desde (COP)", hotel.precio_desde_cop),
            ("Distancia aeropuerto", hotel.distancia_aeropuerto),
        ]
        for k, v in campos:
            if v:
                lineas.append(f"| **{k}** | {v} |")

        # Tipos de habitación
        if hotel.tipos_habitacion:
            lineas.append("\n### Tipos de Habitación\n")
            lineas.append("| Tipo | Tamaño | Camas | Precio COP |")
            lineas.append("|---|---|---|---|")
            for t in hotel.tipos_habitacion:
                lineas.append(
                    f"| {t.get('nombre','')} | {t.get('tamano_m2','')} | "
                    f"{t.get('camas','')} | {t.get('precio_cop_desde','')} |"
                )

        # Restaurantes
        if hotel.restaurantes:
            lineas.append("\n### Gastronomía\n")
            lineas.append("| Restaurante | Cocina | Servicios |")
            lineas.append("|---|---|---|")
            for r in hotel.restaurantes:
                lineas.append(
                    f"| {r.get('nombre','')} | {r.get('tipo_cocina','')} | "
                    f"{r.get('servicios','')} |"
                )

        # Servicios
        if hotel.servicios:
            lineas.append("\n### Servicios e Instalaciones\n")
            for s in hotel.servicios:
                lineas.append(f"- ✅ {s}")

        # Políticas
        if any([hotel.politica_mascotas, hotel.politica_menores,
                hotel.politica_cancelacion]):
            lineas.append("\n### Políticas\n")
            if hotel.politica_mascotas:
                lineas.append(f"**Mascotas:** {hotel.politica_mascotas}\n")
            if hotel.politica_menores:
                lineas.append(f"**Menores:** {hotel.politica_menores}\n")
            if hotel.politica_cancelacion:
                lineas.append(f"**Cancelación:** {hotel.politica_cancelacion}\n")
            if not hotel.permite_fumar:
                lineas.append("**Fumadores:** ❌ Hotel libre de humo\n")

        # Fuentes scrapeadas
        lineas.append("\n<details><summary>🔗 Fuentes scrapeadas</summary>\n")
        for f in hotel.fuentes_scrapeadas:
            lineas.append(f"- {f}")
        lineas.append("\n</details>\n")

        lineas.append("\n---\n")

    lineas.append(
        "\n*Reporte generado con `estelar_scraper.py` — "
        "Hoteles Estelar S.A. Web Scraper — Mayo 2026*\n"
    )
    return "\n".join(lineas)


# ─── Pipeline principal ───────────────────────────────────────────────────────

def main():
    log.info("🚀 Iniciando scraper de Hoteles Estelar S.A.")
    log.info(f"   Hoteles objetivo: {len(HOTELES_URLS)}")
    log.info(f"   Salida JSON: {OUTPUT_JSON}")
    log.info(f"   Salida Markdown: {OUTPUT_MD}")
    log.info(f"   Delay entre requests: {DELAY_MIN}–{DELAY_MAX}s\n")

    scraper = EstelarScraper(use_cloudscraper=True)
    resultados: list[HotelData] = []

    for nombre, config in HOTELES_URLS.items():
        try:
            hotel_data = scrape_hotel(nombre, config, scraper)
            resultados.append(hotel_data)
        except KeyboardInterrupt:
            log.warning("⚠️ Scraping interrumpido por el usuario")
            break
        except Exception as e:
            log.error(f"Error scrapeando {nombre}: {e}")
            # Continuar con el siguiente hotel
            resultados.append(HotelData(nombre=nombre, ciudad=config["ciudad"]))

    # ── Guardar JSON ──────────────────────────────────────────────────────────
    log.info(f"\n💾 Guardando JSON en {OUTPUT_JSON}")
    datos_json = [asdict(h) for h in resultados]
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(datos_json, f, ensure_ascii=False, indent=2)
    log.info(f"   ✅ {len(datos_json)} hoteles guardados en JSON")

    # ── Guardar Markdown ──────────────────────────────────────────────────────
    log.info(f"📝 Generando Markdown en {OUTPUT_MD}")
    md_content = generar_markdown(resultados)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)
    log.info(f"   ✅ Markdown generado ({len(md_content):,} caracteres)")

    # ── Resumen ───────────────────────────────────────────────────────────────
    log.info("\n" + "="*60)
    log.info("📊 RESUMEN DEL SCRAPING")
    log.info("="*60)
    for h in resultados:
        status = "✅" if h.fuentes_scrapeadas else "❌"
        log.info(
            f"{status} {h.nombre:35} | "
            f"Hab: {h.numero_habitaciones or '?':5} | "
            f"Tel: {h.telefono or 'N/A':20} | "
            f"COP: {h.precio_desde_cop or '?'}"
        )
    log.info("="*60)
    log.info(f"Total scrapeados: {sum(1 for h in resultados if h.fuentes_scrapeadas)}/{len(resultados)}")
    log.info("\n✅ Scraping completado.\n")


# ─── Utilidad: Cargar datos ya guardados ──────────────────────────────────────

def cargar_json(ruta: str = str(OUTPUT_JSON)) -> list[dict]:
    """Carga los datos JSON previamente guardados."""
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def buscar_hotel(nombre_parcial: str, datos: list[dict]) -> Optional[dict]:
    """Busca un hotel por nombre parcial (case-insensitive)."""
    for h in datos:
        if nombre_parcial.lower() in h["nombre"].lower():
            return h
    return None


# ─── Notas sobre limitaciones del scraping ───────────────────────────────────
"""
LIMITACIONES CONOCIDAS:
─────────────────────────────────────────────────────────────
1. CLOUDFLARE / BOT PROTECTION
   Booking.com, Expedia y Kayak tienen protecciones anti-bot.
   Se recomienda usar cloudscraper + proxies rotativos para
   producción. En entornos de investigación/personal funciona
   con delays generosos.

2. SITIOS QUE REQUIEREN JavaScript (SPA/React)
   Algunos micrositios oficiales de Estelar renderizan el
   contenido con JavaScript. Para estos casos, usar Selenium
   o Playwright:

       from playwright.sync_api import sync_playwright
       with sync_playwright() as p:
           browser = p.chromium.launch(headless=True)
           page = browser.new_page()
           page.goto(url)
           page.wait_for_load_state("networkidle")
           html = page.content()
           browser.close()

3. PRECIOS EN TIEMPO REAL
   Los precios varían diariamente. Para obtener precios exactos
   y actualizados se recomienda usar las APIs oficiales de:
   - IHG (para InterContinental Cali): developers.ihg.com
   - Booking.com Affiliate Partner Program
   - Expedia Rapid API

4. DATOS QUE REQUIEREN INTERVENCIÓN MANUAL
   - Menú completo de room service
   - Número exacto de baños por tipo de habitación
   - Horarios detallados de restaurantes
   - Tarifas corporativas / grupos
   Estos deben completarse manualmente en el .md final.

5. TÉRMINOS DE USO
   Este script es para uso académico y documentación interna.
   Respetar los robots.txt y términos de uso de cada sitio.
   No usar para scraping masivo o comercial sin autorización.
─────────────────────────────────────────────────────────────
"""

if __name__ == "__main__":
    main()
