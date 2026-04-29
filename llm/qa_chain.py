"""
qa_chain.py
-----------
Sistema de preguntas y respuestas (Q&A) sobre el reporte financiero.

Modos disponibles:
  - BM25 (default): divide el texto en ventanas de N palabras, recupera
    las más relevantes con búsqueda léxica y se las pasa al LLM.
  - Contexto completo: pasa todo el texto consolidado al LLM directamente.
"""

import os
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from llm.prompts import PROMPT_QA
from llm.data_loader import cargar_contexto
from llm.factory import crear_llm

load_dotenv()


def _construir_bm25(texto: str, tam_chunk: int = 150, solapamiento: int = 30) -> tuple[BM25Okapi, list[str]]:
    """
    Divide el texto en ventanas de palabras de tamaño fijo con solapamiento.

    - tam_chunk: número de palabras por chunk
    - solapamiento: palabras compartidas entre chunks consecutivos

    Devuelve (índice BM25, lista de chunks).
    """
    palabras = texto.split()
    paso = tam_chunk - solapamiento
    chunks = [
        " ".join(palabras[i : i + tam_chunk])
        for i in range(0, len(palabras), paso)
        if palabras[i : i + tam_chunk]
    ]
    tokenized = [chunk.lower().split() for chunk in chunks]
    return BM25Okapi(tokenized), chunks


def _recuperar_chunks(pregunta: str, bm25: BM25Okapi, chunks: list[str], top_k: int) -> list[str]:
    """Devuelve los top_k chunks más relevantes para la pregunta."""
    tokens = pregunta.lower().split()
    scores = bm25.get_scores(tokens)
    indices_top = scores.argsort()[-top_k:][::-1]
    return [chunks[i] for i in indices_top]


def responder_pregunta(
    pregunta: str,
    top_k: int = 5,
    contexto_completo: bool = False,
    llm: BaseChatModel | None = None,
) -> dict:
    """
    Responde una pregunta sobre el reporte.

    Parámetros:
      - top_k: número de chunks BM25 a recuperar (ignorado si contexto_completo=True)
      - contexto_completo: si True, pasa todo el texto al LLM en lugar de usar BM25
      - llm: instancia del LLM a usar (usa Claude Haiku por defecto)

    Devuelve un dict con:
      - 'respuesta': texto del LLM
      - 'fuentes': chunks usados (vacío si contexto_completo=True)
    """
    if llm is None:
        llm = crear_llm(temperature=0.0, max_tokens=512)
    texto = cargar_contexto()

    if contexto_completo:
        contexto = texto
        fuentes: list[str] = []
    else:
        bm25, chunks = _construir_bm25(texto)
        fuentes = _recuperar_chunks(pregunta, bm25, chunks, top_k)
        contexto = "\n\n---\n\n".join(fuentes)

    cadena = PROMPT_QA | llm | StrOutputParser()
    respuesta = cadena.invoke({"contexto": contexto, "pregunta": pregunta})

    return {
        "respuesta": respuesta,
        "fuentes": fuentes,
    }


if __name__ == "__main__":
    preguntas_demo = [
        "¿Cuáles fueron los ingresos de Hoteles Estelar en 2024?",
        "¿Cuál es el nivel de apalancamiento de la empresa?",
        "¿Qué CIIU tiene asignado?",
        "¿Quién es el CEO de la empresa?",
    ]
    for p in preguntas_demo:
        print(f"P: {p}")
        r = responder_pregunta(p)
        print(f"R: {r['respuesta']}\n")
