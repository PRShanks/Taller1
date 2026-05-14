"""vector_store.py.

-----------------
Crea una instancia de SupabaseVectorStore a partir de las credenciales
de Supabase configuradas en el archivo .env.

Si no hay ``SUPABASE_URL`` configurada, devuelve ``None`` silenciosamente.
Si hay URL pero falta ``SUPABASE_SERVICE_KEY``, lanza ``OSError``.
"""

import os

from dotenv import load_dotenv
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.embeddings import Embeddings
from supabase import create_client

from llm.rag.embeddings import crear_embeddings

load_dotenv()


def crear_vector_store(
    embeddings: Embeddings | None = None,
) -> SupabaseVectorStore | None:
    """Crea y devuelve un SupabaseVectorStore si hay credenciales configuradas.

    Lee ``SUPABASE_URL`` y ``SUPABASE_SERVICE_KEY`` del entorno.
    Si no hay ``SUPABASE_URL``, devuelve ``None`` (no se considera error).
    Si hay URL pero no hay key, lanza ``OSError`` con mensaje claro.

    Parámetros:
        embeddings: Instancia de ``Embeddings`` de LangChain. Si es ``None``,
            se crea una por defecto via ``crear_embeddings()``.

    Devuelve:
        Una instancia de ``SupabaseVectorStore`` lista para consultas de
        similitud, o ``None`` si Supabase no está configurado.

    Lanza:
        OSError: Si ``SUPABASE_URL`` está configurada pero
            ``SUPABASE_SERVICE_KEY`` no.
    """
    if embeddings is None:
        embeddings = crear_embeddings()

    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        return None

    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_key:
        raise OSError(
            "Falta SUPABASE_SERVICE_KEY. Configúrala en el archivo .env "
            "junto con SUPABASE_URL para habilitar la búsqueda semántica."
        )

    client = create_client(supabase_url, supabase_key)

    return SupabaseVectorStore(
        embedding=embeddings,
        client=client,
        table_name="documents",
        query_name="match_documents",
    )
