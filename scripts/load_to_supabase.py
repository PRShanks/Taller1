import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client, Client

from llm.rag.embeddings import crear_embeddings

DOCUMENTOS_A_SUBIR = [
    "hoteles_estelar_agente_clientes.md",
    "informacion general.md", 
    "inteligencia empresarial.md",
]


def load_documents(directory: str):
    """Carga archivos Markdown desde un directorio y devuelve una lista de documentos."""
    from types import SimpleNamespace

    folder = Path(directory)
    if not folder.exists():
        raise FileNotFoundError(f"No existe el directorio: {directory}")

    documents = []
    for file_path in sorted(folder.glob("*.md")):
        content = file_path.read_text(encoding="utf-8")
        metadata = {"source": str(file_path)}
        documents.append(SimpleNamespace(content=content, metadata=metadata))

    return documents


def get_embeddings(text: str) -> list[float]:
    """Genera embeddings para un texto usando la fábrica de embeddings."""
    embeddings = crear_embeddings()
    return embeddings.embed_query(text)


def get_supabase_key() -> str:
    """Devuelve la clave de Supabase que debe usarse para operaciones de servicio."""
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not key:
        raise OSError(
            "Falta SUPABASE_SERVICE_KEY o SUPABASE_KEY en el archivo .env. "
            "Usa la clave de servicio de Supabase (service_role) para insertar "
            "en tablas con RLS habilitada."
        )
    return key


def load_specific_documents():
    load_dotenv()
    
    # supabase
    supabase: Client = create_client(
        os.getenv("SUPABASE_URL"),
        get_supabase_key(),
    )
    
    # cargar
    todos_los_docs = load_documents("data/estelar_reportes")
    
    docs_a_subir = []
    for doc in todos_los_docs:
        nombre_archivo = Path(doc.metadata.get('source', '')).name
        if nombre_archivo in DOCUMENTOS_A_SUBIR:
            docs_a_subir.append(doc)
            print(f"Seleccionado: {nombre_archivo}")
    
    print(f"\nSubiendo {len(docs_a_subir)} documentos a Supabase...")
    
    for doc in docs_a_subir:
        embedding = get_embeddings(doc.content)

        try:
            supabase.table("documents").insert({
                "content": doc.content,
                "metadata": doc.metadata,
                "embedding": embedding,
            }).execute()
        except APIError as error:
            raise RuntimeError(
                "Error al insertar en Supabase. Verifica que SUPABASE_SERVICE_KEY sea "
                "la clave de servicio de Supabase (service_role) y que la tabla "
                "'documents' permita inserciones. Si la tabla tiene RLS habilitada, "
                "debes usar la key de servicio o ajustar la política. "
                f"Detalle técnico: {error}"
            ) from error

        print(f"Subido: {Path(doc.metadata.get('source', '')).name}")
    
    print(f"\nCompletado! {len(docs_a_subir)} documentos subidos")

if __name__ == "__main__":
    load_specific_documents()