"""prompts.py.

----------
Prompts para el chat de Hoteles Estelar S.A.:
  - PROMPT_QA:               Chat Q&A sin historial (usa system_prompt.txt)
  - PROMPT_QA_CON_MEMORIA:   Chat Q&A con historial de conversación
  - PROMPT_RESUMEN:          Generación de resumen ejecutivo (/resumen)
  - PROMPT_FAQ:              Generación de preguntas frecuentes (/faq)
"""

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Q&A — system prompt externo para facilitar edición sin tocar código
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT_PATH = ROOT / "system_prompt.txt"


def _cargar_system_prompt() -> str:
    if not _SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"No se encontró el system prompt en: {_SYSTEM_PROMPT_PATH}")
    contenido = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    # Escapar llaves para que LangChain no las interprete como variables de plantilla
    return contenido.replace("{", "{{").replace("}", "}}")


PROMPT_QA = ChatPromptTemplate.from_messages(
    [
        ("system", _cargar_system_prompt()),
        (
            "human",
            "=== DOCUMENTACIÓN CORPORATIVA ===\n"
            "{contexto}\n"
            "=== FIN DE LA DOCUMENTACIÓN ===\n\n"
            "Consulta del colaborador: {pregunta}",
        ),
    ]
)

# ---------------------------------------------------------------------------
# Q&A con memoria — incluye historial de conversación previa
# ---------------------------------------------------------------------------
# El MessagesPlaceholder permite pasar mensajes anteriores para que el LLM
# pueda responder preguntas de seguimiento. Si el historial está vacío,
# el placeholder se omite y el prompt es idéntico a PROMPT_QA.
PROMPT_QA_CON_MEMORIA = ChatPromptTemplate.from_messages(
    [
        ("system", _cargar_system_prompt()),
        MessagesPlaceholder(variable_name="historial", optional=True),
        (
            "human",
            "=== DOCUMENTACIÓN CORPORATIVA ===\n"
            "{contexto}\n"
            "=== FIN DE LA DOCUMENTACIÓN ===\n\n"
            "Consulta del colaborador: {pregunta}",
        ),
    ]
)

# ---------------------------------------------------------------------------
# RESUMEN EJECUTIVO
# ---------------------------------------------------------------------------
PROMPT_RESUMEN = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres el Asistente de Soporte Operativo Interno de Hoteles Estelar, "
            "especializado en el sector hotelero colombiano. Tu tarea es producir "
            "resúmenes ejecutivos claros, precisos "
            "y útiles para la toma de decisiones.\n\n"
            "REGLAS ESTRICTAS:\n"
            "- Basa tu resumen ÚNICAMENTE en la información del contexto provisto.\n"
            "- NO inventes cifras, fechas ni hechos que no estén en el contexto.\n"
            "- Si un dato no está disponible, indícalo en lugar de adivinar.\n"
            "- Usa terminología financiera correcta y cita las cifras con sus unidades.\n"
            "- Escribe en español, en tono profesional y conciso.\n",
        ),
        (
            "human",
            "Genera un resumen ejecutivo estructurado con las siguientes secciones:\n\n"
            "1. **Identificación de la empresa** (1-2 líneas).\n"
            "2. **Productos clave** (1-2 líneas).\n"
            "3. **Clientes** (1-2 líneas).\n"
            "4. **Desempeño financiero** (3-5 cifras más relevantes con interpretación).\n"
            "5. **Conclusión** (1-2 frases con la situación general).\n\n"
            "El resumen completo no debe exceder las 300 palabras.\n\n"
            "=== CONTEXTO ===\n{contexto}\n=== FIN DEL CONTEXTO ===",
        ),
    ]
)

# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------
PROMPT_FAQ = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres el Asistente de Soporte Operativo Interno de Hoteles Estelar. Tu trabajo es "
            "responder con precisión un conjunto de preguntas sobre un reporte empresarial, "
            "basándote ÚNICAMENTE en el contexto provisto.\n\n"
            "REGLAS ESTRICTAS:\n"
            "- Responde SOLO con la información que está en el contexto.\n"
            "- Si una pregunta no puede responderse con el contexto, indica: "
            "'Información no disponible en el reporte.'\n"
            "- Las respuestas deben ser concretas y citar cifras exactas cuando aplique.\n"
            "- NO inventes datos. Responde en español.\n",
        ),
        (
            "human",
            "A continuación tienes las preguntas que debes responder y el contexto del reporte.\n\n"
            "=== PREGUNTAS ===\n"
            "{preguntas}\n"
            "=== FIN DE LAS PREGUNTAS ===\n\n"
            "Para cada pregunta genera la respuesta en este formato Markdown:\n"
            "**P1: <pregunta exacta>**\n"
            "R1: <respuesta concreta con cifras si aplica>\n\n"
            "**P2: <pregunta exacta>**\n"
            "R2: <respuesta>\n\n"
            "...y así sucesivamente.\n\n"
            "=== CONTEXTO ===\n{contexto}\n=== FIN DEL CONTEXTO ===",
        ),
    ]
)
