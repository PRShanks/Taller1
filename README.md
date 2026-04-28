# Hoteles Estelar — Análisis con LLM (Taller 1)

Sistema que extrae información financiera de **Hoteles Estelar S.A.** mediante
scraping y la procesa con técnicas de IA generativa: **resumen automático**,
**generación de FAQ** y **Q&A con RAG**, todo accesible desde un dashboard
de Streamlit.

> Stack: **LangChain · Claude (Anthropic) · FAISS · Streamlit**

---

## 📁 Estructura del proyecto

```
scraper-main/
├── data/
│   ├── estelar_reportes/       # salida del scraper (.md)
│   ├── processed/              # texto consolidado para el LLM
│   └── vector_store/           # índice FAISS (se crea solo)
├── scripts/                    # scraper preexistente
│   ├── capture_analisis_individual.py
│   └── extract_estelar_report.py
├── llm/                        # módulos de IA
│   ├── data_loader.py
│   ├── prompts.py
│   ├── summarizer.py
│   ├── faq_generator.py
│   └── qa_chain.py
├── app/
│   └── dashboard.py            # interfaz Streamlit
├── docs/
│   ├── informe.md
│   └── prompts_experimentacion.md
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py
└── README.md
```

---

## 🚀 Instalación

### 1. Clonar y entrar al proyecto
```bash
git clone <tu-repo-url>
cd scraper-main
```

### 2. Crear entorno virtual
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / Mac
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar la API key de Anthropic
1. Consigue una API key en https://console.anthropic.com/settings/keys
2. Copia el archivo de ejemplo:
```bash
# Windows
copy .env.example .env
# Linux / Mac
cp .env.example .env
```
3. Abre `.env` y reemplaza `sk-ant-api03-xxxxx` por tu key real.

---

## ▶️ Uso

### Opción A — Dashboard interactivo (recomendado)
```bash
streamlit run app/dashboard.py
```
Se abre automáticamente en `http://localhost:8501`. Tiene 3 tabs:

| Tab | Funcionalidad |
|---|---|
| 📋 Resumen | Genera un resumen ejecutivo del reporte |
| ❓ FAQ | Crea N preguntas frecuentes con respuesta |
| 💬 Q&A | Conversa con el reporte (RAG con FAISS) |

### Opción B — Scripts individuales
```bash
# Generar el contexto consolidado a partir del .md del scraper
python -m llm.data_loader

# Probar el resumen
python -m llm.summarizer

# Probar el FAQ
python -m llm.faq_generator

# Probar el Q&A (incluye preguntas de demo)
python -m llm.qa_chain
```

---

## 🧪 Cómo funciona el RAG (Q&A)

1. El texto consolidado se divide en chunks de 400 caracteres con overlap de 80.
2. Cada chunk se convierte en un vector (embedding) usando `sentence-transformers`.
3. Los vectores se indexan localmente con FAISS.
4. Cuando haces una pregunta:
   - Se buscan los 4 chunks más similares semánticamente.
   - Se le pasan a Claude como contexto.
   - Claude responde **únicamente** con esa información.
   - Si la respuesta no está, responde literal: *"No tengo esa información en los datos disponibles."*

---

## 📚 Documentación adicional

- **Informe técnico completo:** [`docs/informe.md`](docs/informe.md)
- **Documentación de prompt engineering:** [`docs/prompts_experimentacion.md`](docs/prompts_experimentacion.md)

---

## 🔒 Notas de seguridad

- El archivo `.env` está en `.gitignore` y **nunca debe subirse a GitHub**.
- El `vector_store/` también está ignorado — se regenera automáticamente.

---

## 📝 Licencia

Proyecto académico — Taller 1, Aplicación de Técnicas Avanzadas de IA Generativa.
