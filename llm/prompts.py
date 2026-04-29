"""
prompts.py
----------
Prompt del chat Q&A sobre documentación corporativa de Hoteles Estelar.

El system prompt se carga desde system_prompt.txt en la raíz del proyecto,
lo que permite editarlo sin tocar código.
"""

from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate

ROOT = Path(__file__).resolve().parent.parent

_SYSTEM_PROMPT_PATH = ROOT / "system_prompt.txt"


def _cargar_system_prompt() -> str:
    if not _SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el system prompt en: {_SYSTEM_PROMPT_PATH}"
        )
    return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


PROMPT_QA = ChatPromptTemplate.from_messages([
    ("system", _cargar_system_prompt()),
    ("human",
     "=== DOCUMENTACIÓN CORPORATIVA ===\n"
     "{contexto}\n"
     "=== FIN DE LA DOCUMENTACIÓN ===\n\n"
     "Consulta del colaborador: {pregunta}")
])

