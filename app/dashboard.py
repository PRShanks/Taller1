"""dashboard.py.

------------
Chat Q&A sobre el reporte financiero de Hoteles Estelar S.A.

Incluye memoria de conversación por sesión usando InMemoryStore de LangGraph.
El agente recuerda preguntas y respuestas previas dentro de la sesión,
lo que permite hacer preguntas de seguimiento sobre lo ya consultado.

Cómo ejecutar:
    make dev
    streamlit run app/dashboard.py
"""

import sys
import uuid
from pathlib import Path

# Permitir importar desde la raíz del proyecto cuando se corre con streamlit
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from llm.clients.factory import MODELOS_CLAUDE, MODELOS_OLLAMA_SUGERIDOS, crear_llm  # noqa: E402
from llm.clients.memory import SessionMemory  # noqa: E402
from llm.core.faq_generator import generar_faq  # noqa: E402
from llm.core.qa import responder_pregunta  # noqa: E402
from llm.core.summarizer import generar_resumen  # noqa: E402
from llm.data_loader import cargar_contexto  # noqa: E402

# -------------------- Configuración de la página --------------------
st.set_page_config(
    page_title="Chat · Hoteles Estelar",
    page_icon="🏨",
    layout="wide",
)

st.title("🏨 Hoteles Estelar S.A. — Chat con el reporte")
st.caption("Taller 1 · Aplicación de Técnicas Avanzadas de IA Generativa")


# Caché del contexto completo — se lee del disco una sola vez por sesión
@st.cache_data
def _contexto_completo() -> str:
    return cargar_contexto()


# -------------------- Memoria de sesión --------------------
# InMemoryStore se crea una vez como recurso global (persiste entre reruns).
# Cada sesión de Streamlit usa su propio session_id para namespacear los datos.
@st.cache_resource
def _crear_memoria() -> SessionMemory:
    """Crea una única instancia de SessionMemory compartida entre sesiones."""
    return SessionMemory()


memoria = _crear_memoria()

if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

session_id = st.session_state["session_id"]


# -------------------- Sidebar --------------------
with st.sidebar:
    st.header("🤖 Modelo")

    proveedor = st.radio(
        "Proveedor",
        options=["claude", "ollama"],
        format_func=lambda x: "☁️ Anthropic Claude" if x == "claude" else "🖥️ Ollama (local)",
    )

    if proveedor == "claude":
        modelo = st.selectbox("Modelo Claude", options=MODELOS_CLAUDE)
    else:
        modelo = st.text_input(
            "Modelo Ollama",
            value=MODELOS_OLLAMA_SUGERIDOS[0],
            help="Nombre exacto del modelo instalado en Ollama (ej: llama3.2, mistral)",
        )
        st.caption("Sugeridos: " + ", ".join(MODELOS_OLLAMA_SUGERIDOS))

    st.divider()
    st.header("💾 Memoria de sesión")
    mensajes_en_memoria = len(memoria.get_history(session_id))
    st.caption(f"Mensajes en historial: {mensajes_en_memoria}")

    if st.button("🗑️ Limpiar historial"):
        memoria.clear_session(session_id)
        st.session_state["mensajes"] = []
        st.rerun()

    st.divider()
    if st.button("📂 Ver contexto crudo"):
        st.session_state["mostrar_contexto"] = True


# -------------------- Chat --------------------
if "mensajes" not in st.session_state:
    st.session_state["mensajes"] = []

for msg in st.session_state["mensajes"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Botones de comandos rápidos (autocompletar visual)
st.markdown("**⚡ Comandos rápidos:**")
_bcol1, _bcol2, _bcol3 = st.columns([1, 1, 4])
with _bcol1:
    if st.button("📋 /resumen", use_container_width=True):
        st.session_state["ejecutar_cmd"] = "/resumen"
with _bcol2:
    if st.button("❓ /faq", use_container_width=True):
        st.session_state["ejecutar_cmd"] = "/faq"

# Recuperar comando disparado por botón (si existe)
_cmd_btn = st.session_state.pop("ejecutar_cmd", None)

# chat_input SIEMPRE se llama para que el widget esté siempre visible
_input_usuario = st.chat_input("Escribe tu pregunta o un comando /...")

pregunta = _cmd_btn or _input_usuario

if pregunta:
    st.session_state["mensajes"].append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    # Guardar mensaje del usuario en memoria
    memoria.save_message(session_id, "human", pregunta)

    cmd = pregunta.strip().lower()

    # ---- Comando /resumen ----
    if cmd == "/resumen":
        with (
            st.chat_message("assistant"),
            st.spinner("Generando resumen ejecutivo con el contexto completo..."),
        ):
            try:
                llm = crear_llm(proveedor, modelo, temperature=0.3, max_tokens=1024)
                # Contexto completo explícito — no BM25
                respuesta = generar_resumen(contexto=_contexto_completo(), llm=llm)
                st.markdown(respuesta)
            except Exception as e:
                respuesta = f"❌ Error al generar resumen: {e}"
                st.error(respuesta)
        st.session_state["mensajes"].append({"role": "assistant", "content": respuesta})
        memoria.save_message(session_id, "ai", respuesta)

    # ---- Comando /faq ----
    elif cmd.startswith("/faq"):
        with st.chat_message("assistant"), st.spinner("Generando FAQ con el contexto completo..."):
            try:
                llm = crear_llm(proveedor, modelo, temperature=0.3, max_tokens=2048)
                # Contexto completo explícito — no BM25
                respuesta = generar_faq(contexto=_contexto_completo(), llm=llm)
                st.markdown(respuesta)
            except Exception as e:
                respuesta = f"❌ Error al generar FAQ: {e}"
                st.error(respuesta)
        st.session_state["mensajes"].append({"role": "assistant", "content": respuesta})
        memoria.save_message(session_id, "ai", respuesta)

    # ---- Comando desconocido que empieza con / ----
    elif cmd.startswith("/"):
        ayuda = (
            "Comandos disponibles:\n\n"
            "- `/resumen` — Genera un resumen ejecutivo del reporte completo.\n"
            "- `/faq` — Responde las preguntas frecuentes sobre el reporte.\n\n"
            "O simplemente escribe tu pregunta en lenguaje natural."
        )
        with st.chat_message("assistant"):
            st.info(ayuda)
        st.session_state["mensajes"].append({"role": "assistant", "content": ayuda})
        memoria.save_message(session_id, "ai", ayuda)

    # ---- Pregunta libre (con memoria de conversación) ----
    else:
        with st.chat_message("assistant"), st.spinner("Buscando respuesta..."):
            try:
                # Recuperar historial de la sesión para contexto de seguimiento
                historial = memoria.get_history(session_id)

                resultado = responder_pregunta(
                    pregunta,
                    llm=crear_llm(proveedor, modelo, temperature=0.0, max_tokens=512),
                    historial=historial,
                )

                # Badge de confianza
                badge = {"alta": "🟢 Alta", "media": "🟡 Media", "baja": "🔴 Baja"}.get(
                    resultado.get("confianza", "media"), "🟡 Media"
                )

                if resultado.get("encontrado", True):
                    st.markdown(resultado["respuesta"])
                else:
                    st.warning(resultado["respuesta"])

                col1, col2 = st.columns([1, 5])
                with col1:
                    st.caption(f"Confianza: {badge}")
                if resultado.get("nota"):
                    with col2:
                        st.caption(f"💡 {resultado['nota']}")

                if resultado.get("fuentes"):
                    with st.expander("📄 Fragmentos usados como fuente"):
                        for i, fuente in enumerate(resultado["fuentes"], 1):
                            st.markdown(f"**Fragmento {i}:**")
                            st.code(fuente, language="text")

                respuesta = resultado["respuesta"]

            except Exception as e:
                respuesta = f"❌ Error: {e}"
                st.error(respuesta)

        st.session_state["mensajes"].append({"role": "assistant", "content": respuesta})
        # Guardar respuesta en memoria (solo el texto legible, no el JSON crudo)
        memoria.save_message(session_id, "ai", respuesta)


# -------------------- Modal de contexto crudo --------------------
if st.session_state.get("mostrar_contexto"):
    with st.expander("📂 Contexto consolidado completo", expanded=True):
        st.code(cargar_contexto(), language="text")
        if st.button("Cerrar"):
            st.session_state["mostrar_contexto"] = False
            st.rerun()
