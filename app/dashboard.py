"""
dashboard.py
------------
Chat Q&A sobre el reporte financiero de Hoteles Estelar S.A.

Cómo ejecutar:
    streamlit run app/dashboard.py
"""

import sys
from pathlib import Path

# Permitir importar desde la raíz del proyecto cuando se corre con streamlit
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from llm.qa_chain import responder_pregunta
from llm.data_loader import cargar_contexto
from llm.factory import crear_llm, MODELOS_CLAUDE, MODELOS_OLLAMA_SUGERIDOS


# -------------------- Configuración de la página --------------------
st.set_page_config(
    page_title="Chat · Hoteles Estelar",
    page_icon="🏨",
    layout="wide",
)

st.title("🏨 Hoteles Estelar S.A. — Chat con el reporte")
st.caption("Taller 1 · Aplicación de Técnicas Avanzadas de IA Generativa")


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
    st.header("⚙️ Opciones de búsqueda")
    usar_completo = st.toggle("Contexto completo", value=False)
    top_k = st.number_input(
        "Chunks a recuperar (k)",
        min_value=1,
        max_value=15,
        value=5,
        disabled=usar_completo,
    )

    st.divider()
    if st.button("📂 Ver contexto crudo"):
        st.session_state["mostrar_contexto"] = True


# -------------------- Chat --------------------
if "mensajes" not in st.session_state:
    st.session_state["mensajes"] = []

for msg in st.session_state["mensajes"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if pregunta := st.chat_input("Haz una pregunta sobre el reporte..."):
    st.session_state["mensajes"].append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        with st.spinner("Buscando respuesta..."):
            try:
                resultado = responder_pregunta(
                    pregunta,
                    top_k=top_k,
                    contexto_completo=usar_completo,
                    llm=crear_llm(proveedor, modelo, temperature=0.0, max_tokens=512),
                )
                respuesta = resultado["respuesta"]
                st.markdown(respuesta)

                if not usar_completo and resultado["fuentes"]:
                    with st.expander("📄 Fragmentos usados como fuente"):
                        for i, fuente in enumerate(resultado["fuentes"], 1):
                            st.markdown(f"**Fragmento {i}:**")
                            st.code(fuente, language="text")
            except Exception as e:
                respuesta = f"❌ Error: {e}"
                st.error(respuesta)

    st.session_state["mensajes"].append({"role": "assistant", "content": respuesta})


# -------------------- Modal de contexto crudo --------------------
if st.session_state.get("mostrar_contexto"):
    with st.expander("📂 Contexto consolidado completo", expanded=True):
        st.code(cargar_contexto(), language="text")
        if st.button("Cerrar"):
            st.session_state["mostrar_contexto"] = False
            st.rerun()

