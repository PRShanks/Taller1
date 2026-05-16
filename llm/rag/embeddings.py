"""embeddings.py.

------------------
Crea instancias del modelo de embeddings según el proveedor elegido.

Proveedores soportados:
  - "ollama" → OllamaEmbeddings (modelo local, default: nomic-embed-text)
  - "openai" → OpenAIEmbeddings (requiere OPENAI_API_KEY en .env)
"""

import os

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

load_dotenv()


def crear_embeddings(
    proveedor: str | None = None,
    modelo: str | None = None,
) -> Embeddings:
    """Devuelve un modelo de embeddings de LangChain listo para usar.

    El proveedor se lee de la variable de entorno ``EMBEDDING_PROVIDER``
    (default ``"openai"``). Se puede sobreescribir con el parámetro
    ``proveedor``.

    Parámetros:
        proveedor: Nombre del proveedor. ``"ollama"`` | ``"openai"``.
            Si es ``None``, se lee de ``EMBEDDING_PROVIDER`` (default ``"openai"``).
        modelo: Nombre del modelo a usar. Si es ``None``, se lee de
            ``EMBEDDING_MODEL`` o se usa el default de cada proveedor.

    Devuelve:
        Una instancia de ``Embeddings`` lista para usar.

    Lanza:
        OSError: Si ``proveedor="openai"`` y falta ``OPENAI_API_KEY``.
        ValueError: Si el proveedor no es reconocido.
    """
    proveedor = proveedor or os.getenv("EMBEDDING_PROVIDER", "openai")
    modelo = modelo or os.getenv("EMBEDDING_MODEL")

    if proveedor == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=modelo or "nomic-embed-text")

    if proveedor == "openai":
        from langchain_openai import OpenAIEmbeddings

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise OSError(
                "Falta OPENAI_API_KEY. Configúrala en el archivo .env "
                "o usa EMBEDDING_PROVIDER=ollama para embeddings locales."
            )
        return OpenAIEmbeddings(
            model=modelo or "text-embedding-3-small",
            dimensions=768,
            api_key=api_key,
        )

    raise ValueError(
        f"Proveedor desconocido: '{proveedor}'. Opciones: ollama, openai"
    )
