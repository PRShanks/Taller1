"""vector_store.py.

-----------------
Crea una instancia de SupabaseVectorStore a partir de las credenciales
de Supabase configuradas en el archivo .env.

Si no hay ``SUPABASE_URL`` configurada, devuelve ``None`` silenciosamente.
Si hay URL pero falta ``SUPABASE_SERVICE_KEY``, lanza ``OSError``.

Implementación propia compatible con supabase-py v2, sin depender de
``langchain_community.vectorstores.SupabaseVectorStore`` que tiene
incompatibilidades con versiones recientes del cliente de Supabase.
"""

import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from supabase import Client, create_client

from llm.rag.embeddings import crear_embeddings

load_dotenv()


class SupabaseVectorStore:
    """Vector store propio compatible con supabase-py v2.

    Implementa similarity_search() con la misma interfaz que
    langchain_community.vectorstores.SupabaseVectorStore para que
    el resto del código no necesite cambios.
    """

    def __init__(
        self,
        client: Client,
        embeddings: Embeddings,
        table_name: str = "documents",
        query_name: str = "match_documents",
    ) -> None:
        """Inicializa el vector store.

        Parámetros:
            client: Cliente de Supabase autenticado.
            embeddings: Modelo de embeddings para vectorizar textos.
            table_name: Nombre de la tabla en Supabase.
            query_name: Nombre de la función RPC de búsqueda.
        """
        self._client = client
        self._embeddings = embeddings
        self._table_name = table_name
        self._query_name = query_name

    def add_documents(self, documents: list[Document]) -> None:
        """Inserta documentos con sus embeddings en Supabase.

        Parámetros:
            documents: Lista de documentos LangChain a insertar.
        """
        textos = [doc.page_content for doc in documents]
        vectores = self._embeddings.embed_documents(textos)

        filas = [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "embedding": vector,
            }
            for doc, vector in zip(documents, vectores, strict=True)
        ]

        # Insertar en lotes de 50 para no saturar la petición
        for i in range(0, len(filas), 50):
            lote = filas[i : i + 50]
            self._client.table(self._table_name).insert(lote).execute()

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: dict | None = None,
    ) -> list[Document]:
        """Busca los k documentos más similares semánticamente a la query.

        Parámetros:
            query: Texto de la pregunta del usuario.
            k: Número de documentos a devolver.
            filter: Filtro opcional por metadata (no implementado aún).

        Devuelve:
            Lista de documentos LangChain ordenados por similitud descendente.
        """
        vector = self._embeddings.embed_query(query)

        respuesta = self._client.rpc(
            self._query_name,
            {
                "query_embedding": vector,
                "match_count": k,
                "filter": filter or {},
            },
        ).execute()

        documentos = []
        for fila in respuesta.data:
            documentos.append(
                Document(
                    page_content=fila["content"],
                    metadata={
                        **fila.get("metadata", {}),
                        "similarity": fila.get("similarity", 0.0),
                    },
                )
            )
        return documentos


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
        client=client,
        embeddings=embeddings,
        table_name="documents",
        query_name="match_documents",
    )