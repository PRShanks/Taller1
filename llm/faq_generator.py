"""
faq_generator.py
----------------
Tarea 2 del taller: generación automática de preguntas frecuentes (FAQ)
sobre el reporte financiero usando LangChain + Claude.
"""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser

from llm.prompts import PROMPT_FAQ
from llm.data_loader import cargar_contexto

load_dotenv()


def _crear_llm() -> ChatAnthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Falta ANTHROPIC_API_KEY. Configúrala en el archivo .env"
        )
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.5,   # Algo más alto para variedad en las preguntas
        max_tokens=2048,
        api_key=api_key,
    )


def generar_faq(num_preguntas: int = 8, contexto: str | None = None) -> str:
    """
    Genera un bloque de FAQ con N preguntas y respuestas.
    """
    if contexto is None:
        contexto = cargar_contexto()

    llm = _crear_llm()
    cadena = PROMPT_FAQ | llm | StrOutputParser()
    return cadena.invoke({
        "contexto": contexto,
        "num_preguntas": num_preguntas,
    })


if __name__ == "__main__":
    print("Generando FAQ...\n")
    print(generar_faq(num_preguntas=8))
