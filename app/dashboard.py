"""
dashboard.py
------------
Aplicación Streamlit que expone las tres funcionalidades del taller:
  1. Resumen ejecutivo
  2. FAQ generadas
  3. Q&A interactivo (con RAG)

Cómo ejecutar:
    streamlit run app/dashboard.py
"""

import sys
from pathlib import Path

# Permitir importar desde la raíz del proyecto cuando se corre con streamlit
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from llm.summarizer import generar_resumen
from llm.faq_generator import generar_faq
from llm.qa_chain import construir_vector_store, responder_pregunta
from llm.data_loader import cargar_contexto


# -------------------- Configuración de la página --------------------
st.set_page_config(
    page_title="Análisis Hoteles Estelar - LLM Dashboard",
    page_icon="🏨",
    layout="wide",
)

st.title("🏨 Hoteles Estelar S.A. — Dashboard de Análisis con LLM")
st.caption("Taller 1 · Aplicación de Técnicas Avanzadas de IA Generativa")


# -------------------- Recursos cacheados --------------------
@st.cache_resource(show_spinner="Cargando vector store...")
def cargar_vector_store():
    """Construye o carga el índice FAISS una sola vez por sesión."""
    return construir_vector_store()


@st.cache_data(show_spinner="Generando resumen ejecutivo...")
def get_resumen():
    return generar_resumen()


@st.cache_data(show_spinner="Generando FAQ...")
def get_faq(num_preguntas: int):
    return generar_faq(num_preguntas=num_preguntas)


# -------------------- Sidebar --------------------
with st.sidebar:
    st.header("ℹ️ Acerca del proyecto")
    st.markdown(
        "Este dashboard procesa el reporte financiero de **Hoteles Estelar S.A.** "
        "(extraído mediante scraping de Estrategia en Acción) y aplica tres "
        "técnicas de LLM con LangChain + Claude:\n\n"
        "- **Resumen** ejecutivo automático\n"
        "- **FAQ** generadas a partir del contenido\n"
        "- **Q&A** con recuperación de contexto (RAG)"
    )
    st.divider()
    if st.button("📂 Ver contexto crudo"):
        st.session_state["mostrar_contexto"] = True


# -------------------- Tabs principales --------------------
tab1, tab2, tab3 = st.tabs(["📋 Resumen", "❓ FAQ", "💬 Q&A"])

# === TAB 1: RESUMEN ===
with tab1:
    st.subheader("Resumen ejecutivo")
    st.markdown(
        "Genera un resumen estructurado del reporte financiero, "
        "destacando las cifras y conclusiones clave."
    )

    if st.button("✨ Generar resumen", key="btn_resumen"):
        try:
            resumen = get_resumen()
            st.markdown(resumen)
        except Exception as e:
            st.error(f"Error generando el resumen: {e}")


# === TAB 2: FAQ ===
with tab2:
    st.subheader("Preguntas frecuentes (FAQ)")
    st.markdown(
        "El modelo identifica las preguntas que un analista o inversionista "
        "haría sobre este reporte y las responde."
    )

    num = st.slider("Número de preguntas", 5, 15, 8)

    if st.button("✨ Generar FAQ", key="btn_faq"):
        try:
            faq = get_faq(num)
            st.markdown(faq)
        except Exception as e:
            st.error(f"Error generando el FAQ: {e}")


# === TAB 3: Q&A ===
with tab3:
    st.subheader("Pregúntale al reporte")
    st.markdown(
        "Haz una pregunta libre. El sistema buscará los fragmentos más "
        "relevantes del reporte y responderá basándose únicamente en ellos."
    )

    # Inicializar vector store al entrar al tab
    vs = cargar_vector_store()

    pregunta = st.text_input(
        "Tu pregunta:",
        placeholder="Ej. ¿Cuál fue el EBITDA de Hoteles Estelar en 2024?",
    )

    col_a, col_b = st.columns([1, 4])
    with col_a:
        top_k = st.number_input("Chunks a recuperar (k)", 1, 10, 4)

    if st.button("🔍 Responder", key="btn_qa") and pregunta:
        try:
            resultado = responder_pregunta(pregunta, top_k=top_k, vector_store=vs)
            st.markdown("**Respuesta:**")
            st.success(resultado["respuesta"])

            with st.expander("📄 Fragmentos del contexto usados como fuente"):
                for i, fuente in enumerate(resultado["fuentes"], 1):
                    st.markdown(f"**Fragmento {i}:**")
                    st.code(fuente, language="text")
        except Exception as e:
            st.error(f"Error procesando la pregunta: {e}")


# -------------------- Modal de contexto crudo --------------------
if st.session_state.get("mostrar_contexto"):
    with st.expander("📂 Contexto consolidado completo", expanded=True):
        st.code(cargar_contexto(), language="text")
        if st.button("Cerrar"):
            st.session_state["mostrar_contexto"] = False
            st.rerun()
