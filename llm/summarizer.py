"""summarizer.py.

-------------
Tarea 1 del taller: generación de un resumen ejecutivo del reporte
financiero usando LangChain + Claude/Ollama.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from llm.data_loader import cargar_contexto
from llm.factory import crear_llm
from llm.prompts import PROMPT_RESUMEN


def generar_resumen(
    contexto: str | None = None,
    llm: BaseChatModel | None = None,
) -> str:
    """Genera el resumen ejecutivo.

    Si no se pasa contexto, lo carga desde el archivo consolidado.
    Si no se pasa llm, usa Claude Haiku.
    """
    if contexto is None:
        contexto = cargar_contexto()
    if llm is None:
        llm = crear_llm(temperature=0.3, max_tokens=1024)

    cadena = PROMPT_RESUMEN | llm | StrOutputParser()
    return cadena.invoke({"contexto": contexto})


if __name__ == "__main__":
    print("Generando resumen ejecutivo...\n")
    print(generar_resumen())
