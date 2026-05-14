import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client, Client

from llm.rag.embeddings import crear_embeddings
from data_loader import load_documents

load_dotenv()

# Inicializar
embeddings = crear_embeddings()
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Cargar documentos
docs = load_documents("data/estelar_reportes")
print(f"Documentos encontrados: {len(docs)}")

for doc in docs:
    print(f"  - {doc.metadata.get('source', 'desconocido')}")

# Subir
docs_a_subir = docs[:3] 

for doc in docs_a_subir:
    embedding = embeddings.embed_query(doc.content)
    supabase.table("document_chunks").insert({
        "content": doc.content,
        "metadata": doc.metadata,
        "embedding": embedding
    }).execute()
    print(f"Subido: {doc.metadata.get('source', '')}")

print("Listo!")