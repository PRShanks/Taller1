"""sanitizer.py.

--------------
Defensa contra Indirect Prompt Injection en el pipeline RAG.

Proporciona dos funciones:
  - ``_sanitizar_contexto``: limpia un fragmento de texto eliminando
    bloques fenced y redactando patrones de inyección conocidos.
  - ``_fuentes_limpias``: aplica sanitización a una lista de documentos
    y devuelve el contexto concatenado junto con metadatos de detección
    para adjuntar a traces de LangSmith.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Patrones de inyección a eliminar del contenido recuperado
_PATRONES_INYECCION = [
    r"ignora\s*(?:todas\s+)?(?:las\s+)?instrucciones\s+(?:previas|anteriores)",
    r"ignore\s*(?:all\s+)?(?:previous\s+)?instructions",
    r"\[system\s*override\]",
    r"\[nuevas?\s*instrucciones\]",
    r"inicio\s*de\s*(?:nuevas?\s*)?instrucciones",
]


def _sanitizar_contexto(texto: str) -> str:
    """Limpia el contenido recuperado para mitigar prompt injection.

    Elimina patrones conocidos de inyección y bloques de código que
    podrían contener instrucciones maliciosas. El contenido corporativo
    legítimo NO contiene este tipo de patrones.

    Parámetros:
        texto: Fragmento de texto recuperado del vector store.

    Devuelve:
        Texto limpio, seguro para inyectar en el prompt.
    """
    # Eliminar bloques de código fenced (``` ... ```) — vector de inyección común
    limpio = re.sub(
        r"```(?:\w+)?\n.*?```",
        "",
        texto,
        count=0,
        flags=re.DOTALL,
    )

    # Eliminar patrones de instrucción maliciosa (case-insensitive)
    for patron in _PATRONES_INYECCION:
        limpio = re.sub(patron, "[redactado por seguridad]", limpio, flags=re.IGNORECASE)

    return limpio.strip()


def _fuentes_limpias(docs: list) -> tuple:
    """Aplica sanitización a los documentos recuperados.

    Devuelve el contexto concatenado, las fuentes individuales y metadatos
    sobre detecciones, ambas sanitizadas. Si detecta patrones de inyección,
    registra una advertencia en el log.

    Los metadatos están diseñados para adjuntarse como metadata en los traces
    de LangSmith, permitiendo filtrar y auditar ejecuciones con inyección
    detectada. Incluyen el source del documento original (``doc.metadata``)
    para poder rastrear qué documento en Supabase contenía la inyección.

    Parámetros:
        docs: Lista de documentos (con atributo ``page_content`` y
            ``metadata`` con clave ``source``).

    Devuelve:
        Tupla (contexto_sanitizado, fuentes_sanitizadas, metadatos_inyeccion).
        ``metadatos_inyeccion`` es un dict vacío si no se detectó nada, o
        contiene las claves:
        - ``inyeccion_detectada`` (bool)
        - ``indices_afectados`` (list[int])
        - ``docs_afectados`` (list[dict]) con ``indice`` y ``source`` de cada
          documento que contenía contenido sospechoso.
    """
    fuentes = []
    indices_afectados = []
    docs_info = []
    for i, doc in enumerate(docs):
        contenido = doc.page_content
        sanitizado = _sanitizar_contexto(contenido)
        # Comparar ambos versiones con strip() para no confundir
        # espacios/blancos con detección de inyección
        if sanitizado != contenido.strip():
            indices_afectados.append(i)
            docs_info.append({
                "indice": i,
                "source": doc.metadata.get("source", "unknown"),
            })
        fuentes.append(sanitizado)

    if indices_afectados:
        logger.warning(
            "Se detectaron y redactaron patrones de posible inyección "
            "en el contenido recuperado de la base de datos vectorial. "
            f"Documentos afectados: {docs_info}"
        )

    contexto = "\n\n---\n\n".join(fuentes)
    metadatos = (
        {
            "inyeccion_detectada": True,
            "indices_afectados": indices_afectados,
            "docs_afectados": docs_info,
        }
        if indices_afectados
        else {}
    )
    return contexto, fuentes, metadatos
