"""
faq_generator.py
----------------
Tarea 2 del taller: responde un set de preguntas frecuentes fijas
sobre el reporte financiero usando LangChain + Claude/Ollama.

Las preguntas son siempre las mismas; el LLM genera las respuestas
basándose en el contexto corporativo cargado.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from llm.prompts import PROMPT_FAQ
from llm.data_loader import cargar_contexto
from llm.factory import crear_llm

# Preguntas fijas — siempre las mismas, el modelo solo genera las respuestas
PREGUNTAS_FAQ: list[str] = [
    "¿Cuál es el nombre completo y el NIT de la empresa?",
    "¿Cuáles fueron los ingresos operacionales del período reportado?",
    "¿Cuál fue la utilidad neta del período y cómo varía respecto al período anterior?",
    "¿Cuántos hoteles opera la cadena y en qué ciudades están ubicados?",
    "¿Cuál es el nivel de endeudamiento o apalancamiento financiero de la empresa?",
    "¿Cuál fue el EBITDA o resultado operacional del período?",
    "¿Qué activos totales registra la empresa en su balance general?",
    "¿Cuál es la actividad económica principal de la empresa según el reporte?",
]


def generar_faq(
    contexto: str | None = None,
    llm: BaseChatModel | None = None,
) -> str:
    """
    Genera respuestas para las preguntas fijas de PREGUNTAS_FAQ.
    Si no se pasa contexto, lo carga desde el archivo consolidado.
    Si no se pasa llm, usa Claude Haiku.
    """
    if contexto is None:
        contexto = cargar_contexto()
    if llm is None:
        llm = crear_llm(temperature=0.3, max_tokens=2048)

    preguntas_formateadas = "\n".join(
        f"{i + 1}. {q}" for i, q in enumerate(PREGUNTAS_FAQ)
    )

    cadena = PROMPT_FAQ | llm | StrOutputParser()
    return cadena.invoke({
        "contexto": contexto,
        "preguntas": preguntas_formateadas,
    })


if __name__ == "__main__":
    print("Generando FAQ...\n")
    print(generar_faq())
