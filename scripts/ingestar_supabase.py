"""ingestar_supabase.py.

-------------------
Carga los documentos corporativos de Hoteles Estelar en la base de datos
vectorial de Supabase, usando el modelo de embeddings configurado en el
entorno (``EMBEDDING_PROVIDER``).

Este script implementa los targets ``make ingest`` y ``make reindex``
del Makefile, marcados como «equipo de datos» por el equipo de desarrollo.

Qué se sube (información corporativa / atención al cliente):
    - hoteles_estelar_agente_clientes.md
    - informacion general.md
    - inteligencia empresarial.md

Qué NO se sube (reportes financieros estructurados):
    - reporte-financiero-completo.md
    - informes financieros/*.md

Razón de la exclusión:
    Los datos financieros son cifras exactas que se consultan mejor con
    una herramienta estructurada determinista (Módulo 2 del taller).
    Mezclarlos en búsqueda semántica produciría respuestas imprecisas
    para preguntas numéricas (preguntar «¿cuánto ganaron?» podría mezclar
    cifras de distintos años o categorías).

Uso:
    python -m scripts.ingestar_supabase           # primera carga
    python -m scripts.ingestar_supabase --force   # reindexar (borra y recarga)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm.rag.embeddings import crear_embeddings  # noqa: E402
from llm.rag.vector_store import crear_vector_store  # noqa: E402

# ---------------------------------------------------------------------------
# Configuración de archivos
# ---------------------------------------------------------------------------
DIR_REPORTES = ROOT / "data" / "estelar_reportes"

# Archivos que SÍ se cargan al vector store (información corporativa)
ARCHIVOS_PERMITIDOS: list[str] = [
    "hoteles_estelar_agente_clientes.md",
    "informacion general.md",
    "inteligencia empresarial.md",
]

# Carpeta excluida completa (reportes financieros estructurados)
CARPETA_EXCLUIDA = "informes financieros"

# Configuración del splitter
# chunk_size=1000 y chunk_overlap=200 siguen la especificación del compañero
# (openspec/changes/rag-migration/proposal.md: "chunk=1000, overlap=200")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cargar_documentos() -> list[Document]:
    """Lee los archivos permitidos y los convierte en documentos LangChain.

    Devuelve:
        Lista de ``Document`` con ``page_content`` y ``metadata.source``.

    Lanza:
        FileNotFoundError: si alguno de los archivos permitidos no existe.
    """
    documentos: list[Document] = []

    for nombre in ARCHIVOS_PERMITIDOS:
        ruta = DIR_REPORTES / nombre

        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo requerido: {ruta}\n"
                f"Asegúrate de que esté en {DIR_REPORTES}"
            )

        contenido = ruta.read_text(encoding="utf-8")
        documentos.append(
            Document(
                page_content=contenido,
                metadata={"source": nombre},
            )
        )
        print(f"   ✓ Cargado: {nombre} ({len(contenido):,} caracteres)")

    return documentos


def _trocear_documentos(documentos: list[Document]) -> list[Document]:
    """Divide los documentos en fragmentos con solapamiento.

    Usa ``RecursiveCharacterTextSplitter`` con los parámetros definidos
    en la especificación de migración RAG del proyecto (chunk=1000,
    overlap=200), propagando el metadata de origen a cada fragmento.

    Parámetros:
        documentos: Lista de documentos completos a fragmentar.

    Devuelve:
        Lista de fragmentos (chunks) con metadata conservada.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documentos)

    # Inyectar índice de chunk en metadata para trazabilidad
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    return chunks


def _vaciar_tabla(vector_store: SupabaseVectorStore) -> None:
    """Elimina todos los documentos de la tabla 'documents' en Supabase.

    Parámetros:
        vector_store: Instancia conectada al vector store.
    """
    cliente = vector_store._client  # acceso al cliente supabase-py subyacente
    cliente.table("documents").delete().gte("id", 0).execute()
    print("   ✓ Tabla vaciada")


def _contar_documentos(vector_store: SupabaseVectorStore) -> int:
    """Cuenta los documentos actualmente en la tabla.

    Parámetros:
        vector_store: Instancia conectada al vector store.

    Devuelve:
        Número de filas en la tabla 'documents'.
    """
    cliente = vector_store._client
    respuesta = cliente.table("documents").select("id", count="exact").execute()
    return respuesta.count or 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(force: bool = False) -> None:
    """Ejecuta la ingesta completa de documentos a Supabase.

    Parámetros:
        force: Si True, borra y recarga todos los documentos (reindex).
               Si False, omite la carga si ya existen documentos.
    """
    print("=" * 60)
    print("INGESTA DE DOCUMENTOS → SUPABASE")
    print(f"Configuración: chunk={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
    print("=" * 60)

    # 1. Crear embeddings y vector store usando los módulos del proyecto
    print("\n🔌 Paso 1: Conectando a Supabase...")
    embeddings = crear_embeddings()
    vector_store = crear_vector_store(embeddings)

    if vector_store is None:
        print(
            "\n❌ SUPABASE_URL no está configurada en el .env.\n"
            "   Agrega SUPABASE_URL y SUPABASE_SERVICE_KEY y vuelve a intentar."
        )
        sys.exit(1)
    print("   ✓ Conexión exitosa")

    # 2. Verificar si ya hay datos y si se debe reindexar
    total_existentes = _contar_documentos(vector_store)
    print(f"\n📊 Paso 2: Estado actual: {total_existentes} documentos en Supabase")

    if total_existentes > 0 and not force:
        print(
            "\n⚠️  Ya existen documentos en la base de datos.\n"
            "   Para reindexar (borrar y recargar), usa: make reindex\n"
            "   o ejecuta: python -m scripts.ingestar_supabase --force"
        )
        sys.exit(0)

    if force and total_existentes > 0:
        print("\n🗑️  Paso 2b: Vaciando tabla (--force)...")
        _vaciar_tabla(vector_store)

    # 3. Cargar documentos
    print("\n📄 Paso 3: Cargando archivos...")
    documentos = _cargar_documentos()
    print(f"   Total: {len(documentos)} archivos cargados")

    # 4. Trocear en chunks
    print("\n✂️  Paso 4: Troceando en chunks...")
    chunks = _trocear_documentos(documentos)
    print(f"   Total: {len(chunks)} chunks generados")

    # Resumen de chunks por archivo
    conteo: dict[str, int] = {}
    for chunk in chunks:
        fuente = chunk.metadata.get("source", "desconocido")
        conteo[fuente] = conteo.get(fuente, 0) + 1
    for fuente, cantidad in conteo.items():
        print(f"   - {fuente}: {cantidad} chunks")

    # 5. Subir a Supabase (add_documents genera embeddings internamente)
    print(f"\n☁️  Paso 5: Subiendo a Supabase (esto puede tardar ~{len(chunks)//10}s)...")
    vector_store.add_documents(chunks)
    print(f"   ✓ {len(chunks)} chunks subidos correctamente")

    # 6. Verificación final
    total_final = _contar_documentos(vector_store)
    print(f"\n✅ Ingesta completada: {total_final} documentos en Supabase")

    # 7. Prueba de búsqueda rápida
    print("\n🔍 Verificación — búsqueda de prueba:")
    resultados = vector_store.similarity_search(
        "¿En qué ciudades opera Hoteles Estelar?", k=2
    )
    for i, doc in enumerate(resultados, 1):
        fuente = doc.metadata.get("source", "?")
        print(f"   [{i}] {fuente}: {doc.page_content[:100]}...")

    print("\n🎉 Todo listo. El Q&A ya puede usar búsqueda semántica.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingesta de documentos corporativos de Hoteles Estelar a Supabase."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Borrar documentos existentes y recargar desde cero.",
    )
    args = parser.parse_args()
    main(force=args.force)
