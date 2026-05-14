"""qa.py.

-------
Sistema de preguntas y respuestas (Q&A) sobre el reporte financiero.

Modos disponibles:
  - Supabase (default): búsqueda semántica via ``SupabaseVectorStore``,
    recupera fragmentos relevantes y se los pasa al LLM.
  - Sin Supabase: mensaje plano informando que RAG no está configurado.
    Sin llamada al LLM ni carga de texto completo.

Soporta historial de conversación para preguntas de seguimiento.

La respuesta del LLM se genera con ``with_structured_output`` usando
el modelo Pydantic ``RespuestaQA``, eliminando el parseo manual de JSON.
"""

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from llm.clients.factory import crear_llm
from llm.models import RespuestaQA
from llm.prompts.qa import PROMPT_QA, PROMPT_QA_CON_MEMORIA
from llm.rag.embeddings import crear_embeddings
from llm.rag.sanitizer import _fuentes_limpias
from llm.rag.vector_store import crear_vector_store

load_dotenv()


def responder_pregunta(
    pregunta: str,
    llm: BaseChatModel | None = None,
    historial: list[BaseMessage] | None = None,
) -> dict:
    """Responde una pregunta sobre el reporte usando búsqueda semántica.

    Si Supabase está configurado (``SUPABASE_URL`` en el entorno), usa
    ``SupabaseVectorStore.similarity_search()`` para recuperar fragmentos
    relevantes y se los pasa al LLM para generar la respuesta.

    Si Supabase NO está configurado, devuelve un mensaje plano informando
    que el sistema RAG no está disponible — sin llamar al LLM ni cargar
    texto completo.

    Parámetros:
        pregunta: La consulta del colaborador.
        llm: Instancia del LLM a usar (por defecto: Claude Haiku via
            ``crear_llm(temperature=0.0, max_tokens=512)``).
            Solo se usa cuando hay Supabase disponible.
        historial: Mensajes previos de la conversación para contexto de
            seguimiento. Si es ``None`` o vacío, se usa el prompt sin
            memoria (``PROMPT_QA``). Si tiene mensajes, se usa
            ``PROMPT_QA_CON_MEMORIA``.

    Devuelve:
        Un dict con las claves:
        - ``respuesta``: texto de la respuesta
        - ``fuentes``: fragmentos usados como contexto
        - ``encontrado``: si se encontró información relevante
        - ``confianza``: nivel de confianza (alta, media, baja)
        - ``nota``: nota adicional
    """
    embeddings = crear_embeddings()
    vector_store = crear_vector_store(embeddings)

    if vector_store is not None:
        # --- Supabase mode: semantic search + LLM con structured output ---
        if llm is None:
            llm = crear_llm(temperature=0.0, max_tokens=512)

        docs = vector_store.similarity_search(pregunta, k=5)
        contexto, fuentes, metadatos_inyeccion = _fuentes_limpias(docs)

        llm_estructurado = llm.with_structured_output(RespuestaQA)

        # Adjuntar metadatos de inyección al trace de LangSmith (si está
        # configurado via LANGSMITH_API_KEY + LANGSMITH_TRACING=true).
        # Si LangSmith no está activo, el config se ignora silenciosamente.
        config_llm = (
            {"metadata": metadatos_inyeccion}
            if metadatos_inyeccion
            else {}
        )

        if historial:
            cadena = PROMPT_QA_CON_MEMORIA | llm_estructurado
            resultado: RespuestaQA = cadena.invoke(
                {
                    "contexto": contexto,
                    "pregunta": pregunta,
                    "historial": historial,
                },
                config=config_llm,
            )
        else:
            cadena = PROMPT_QA | llm_estructurado
            resultado: RespuestaQA = cadena.invoke(
                {
                    "contexto": contexto,
                    "pregunta": pregunta,
                },
                config=config_llm,
            )

        return {
            "respuesta": resultado.respuesta,
            "encontrado": resultado.encontrado,
            "confianza": resultado.confianza,
            "nota": resultado.nota,
            "fuentes": fuentes,
        }

    # --- No Supabase mode: plain message, NO LLM, NO cargar_contexto ---
    return {
        "respuesta": (
            "El sistema de búsqueda semántica (RAG) no está configurado. "
            "Para activarlo, configure SUPABASE_URL y SUPABASE_SERVICE_KEY "
            "en el archivo .env y asegúrese de que el equipo de datos haya "
            "ejecutado la ingesta de documentos en la base de datos vectorial."
        ),
        "encontrado": False,
        "confianza": "baja",
        "nota": "Modo offline: sin conexión a base de datos vectorial.",
        "fuentes": [],
    }


if __name__ == "__main__":
    # Demo: sin Supabase configurado, responde con mensaje plano
    print("--- Modo sin Supabase ---")
    r = responder_pregunta("¿Cuáles fueron los ingresos de Hoteles Estelar en 2024?")
    print(f"Respuesta: {r['respuesta']}")
    print(f"Encontrado: {r['encontrado']}")
    print(f"Confianza: {r['confianza']}")
    print(f"Nota: {r['nota']}")
    print(f"Fuentes: {len(r['fuentes'])} fragmentos")
