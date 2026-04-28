"""
summarizer.py
-------------
Tarea 1 del taller: generación de un resumen ejecutivo del reporte
financiero usando LangChain + Claude.
"""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser

from llm.prompts import PROMPT_RESUMEN
from llm.data_loader import cargar_contexto

load_dotenv()


def _crear_llm() -> ChatAnthropic:
    """Inicializa el modelo de Claude."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Falta ANTHROPIC_API_KEY. Configúrala en el archivo .env"
        )
    # Modelo económico y suficientemente capaz para esta tarea.
    # Puedes cambiarlo por "claude-opus-4-5" si quieres más calidad.
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.3,   # Bajo para que las cifras no varíen
        max_tokens=1024,
        api_key=api_key,
    )


def generar_resumen(contexto: str | None = None) -> str:
    """
    Genera el resumen ejecutivo. Si no se pasa contexto, lo carga
    desde el archivo consolidado.
    """
    if contexto is None:
        contexto = cargar_contexto()

    llm = _crear_llm()
    cadena = PROMPT_RESUMEN | llm | StrOutputParser()
    return cadena.invoke({"contexto": contexto})


if __name__ == "__main__":
    print("Generando resumen ejecutivo...\n")
    print(generar_resumen())
