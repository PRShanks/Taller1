"""
qa_chain.py
-----------
Tarea 3 del taller: sistema de preguntas y respuestas (Q&A) sobre
el reporte financiero usando RAG (Retrieval-Augmented Generation).

Arquitectura:
  1. El texto consolidado se divide en chunks.
  2. Cada chunk se convierte en un embedding (sentence-transformers).
  3. Los embeddings se indexan en FAISS (vector store local).
  4. Para cada pregunta del usuario:
     a. Se buscan los chunks más relevantes (top-k).
     b. Se le pasan al LLM como contexto junto con la pregunta.
     c. El LLM responde basándose SOLO en ese contexto.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from llm.prompts import PROMPT_QA
from llm.data_loader import cargar_contexto

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
VECTOR_STORE_DIR = ROOT / "data" / "vector_store"

# Modelo de embeddings multilingüe (bueno con español)
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _crear_llm() -> ChatAnthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Falta ANTHROPIC_API_KEY. Configúrala en el archivo .env"
        )
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.0,   # Cero para máxima fidelidad al contexto
        max_tokens=512,
        api_key=api_key,
    )


def _crear_embeddings() -> HuggingFaceEmbeddings:
    """Modelo de embeddings local (no requiere API)."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def construir_vector_store(forzar_reconstruccion: bool = False) -> FAISS:
    """
    Construye (o carga) el vector store FAISS a partir del texto consolidado.
    """
    embeddings = _crear_embeddings()

    # Si ya existe el índice, lo cargamos.
    if VECTOR_STORE_DIR.exists() and not forzar_reconstruccion:
        return FAISS.load_local(
            str(VECTOR_STORE_DIR),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    # Construir desde cero
    texto = cargar_contexto()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(texto)
    documentos = [Document(page_content=c) for c in chunks]

    vector_store = FAISS.from_documents(documentos, embeddings)
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(VECTOR_STORE_DIR))
    return vector_store


def responder_pregunta(
    pregunta: str,
    top_k: int = 4,
    vector_store: FAISS | None = None,
) -> dict:
    """
    Responde una pregunta usando RAG.

    Devuelve un dict con:
      - 'respuesta': texto de la respuesta del LLM
      - 'fuentes': lista de chunks usados como contexto (para transparencia)
    """
    if vector_store is None:
        vector_store = construir_vector_store()

    # 1. Recuperar chunks relevantes
    docs_relevantes = vector_store.similarity_search(pregunta, k=top_k)
    contexto = "\n\n---\n\n".join(d.page_content for d in docs_relevantes)

    # 2. Pasar al LLM
    llm = _crear_llm()
    cadena = PROMPT_QA | llm | StrOutputParser()
    respuesta = cadena.invoke({"contexto": contexto, "pregunta": pregunta})

    return {
        "respuesta": respuesta,
        "fuentes": [d.page_content for d in docs_relevantes],
    }


if __name__ == "__main__":
    print("Construyendo vector store...")
    vs = construir_vector_store(forzar_reconstruccion=True)
    print("✓ Vector store listo.\n")

    preguntas_demo = [
        "¿Cuáles fueron los ingresos de Hoteles Estelar en 2024?",
        "¿Cuál es el nivel de apalancamiento de la empresa?",
        "¿Qué CIIU tiene asignado?",
        "¿Quién es el CEO de la empresa?",  # No está en el contexto -> debe decir que no sabe
    ]
    for p in preguntas_demo:
        print(f"P: {p}")
        r = responder_pregunta(p, vector_store=vs)
        print(f"R: {r['respuesta']}\n")
