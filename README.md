# Hoteles Estelar — Análisis con LLM (Taller 1)

Sistema de análisis empresarial que combina **web scraping**, **procesamiento con LLM** y **generación aumentada por recuperación (RAG)** sobre datos públicos de **Hoteles Estelar S.A.** (NIT 890304099).

> **Stack:** Python 3.12 · uv · LangChain · Claude (Anthropic) · FAISS · Streamlit

---

## 📁 Estructura del proyecto

```
scraper-main/
├── data/
│   ├── estelar_reportes/
│   │   ├── HOTELES_ESTELAR_890304099.md   # datos financieros (scraper)
│   │   └── hoteles_estelar.md              # info corporativa
│   ├── processed/                          # texto consolidado (auto)
│   └── vector_store/                       # índice FAISS (auto)
├── scripts/
│   ├── capture_analisis_individual.py
│   └── extract_estelar_report.py
├── llm/
│   ├── data_loader.py        # carga y consolida los 2 .md
│   ├── prompts.py            # prompts de las 3 tareas
│   ├── summarizer.py         # tarea 1: Resumen
│   ├── faq_generator.py      # tarea 2: FAQ
│   └── qa_chain.py           # tarea 3: Q&A con RAG
├── app/
│   └── dashboard.py          # interfaz Streamlit
├── docs/
│   ├── informe.md
│   └── prompts_experimentacion.md
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── requirements.txt
├── main.py
└── README.md
```

---

## 🚀 Instalación

Este proyecto usa **[uv](https://github.com/astral-sh/uv)** como gestor de paquetes y entornos.

### 1. Clonar el repositorio
```bash
git clone https://github.com/PRShanks/Taller1.git
cd Taller1
```

### 2. Crear entorno virtual con Python 3.12
```bash
uv venv --python 3.12
```

> ⚠️ Es importante usar Python 3.12. La librería `faiss-cpu` no tiene soporte aún para Python 3.13/3.14.

### 3. Activar el entorno
```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```
```bash
# Mac/Linux
source .venv/bin/activate
```

### 4. Instalar dependencias
```bash
uv pip install -r requirements.txt
```

### 5. Configurar la API key de Anthropic
```powershell
# Windows
copy .env.example .env
```
```bash
# Mac/Linux
cp .env.example .env
```

Edita el archivo `.env` y reemplaza el valor placeholder por tu API key real:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

> Consigue tu key gratis en: https://console.anthropic.com/settings/keys

---

## ▶️ Uso

### Lanzar el dashboard interactivo (recomendado)
```bash
streamlit run app/dashboard.py
```
Se abre automáticamente en `http://localhost:8501`. El dashboard tiene 3 pestañas:

| Pestaña | Funcionalidad |
|---|---|
| 📋 **Resumen** | Resumen ejecutivo del reporte financiero |
| ❓ **FAQ** | Genera N preguntas frecuentes con respuesta |
| 💬 **Q&A** | Conversa con el reporte usando RAG |

### Ejecutar scripts individuales
```bash
# Generar el contexto consolidado a partir de los 2 archivos .md
python -m llm.data_loader

# Probar el resumen
python -m llm.summarizer

# Probar el FAQ
python -m llm.faq_generator

# Probar el Q&A (incluye preguntas demo)
python -m llm.qa_chain
```

---

## 🧪 Cómo funciona el RAG (Q&A)

1. Los dos archivos `.md` (financiero + corporativo) se consolidan en un solo `.txt`.
2. El texto se divide en chunks de 400 caracteres con overlap de 80.
3. Cada chunk se transforma en un vector con `sentence-transformers` (modelo multilingüe).
4. Los vectores se indexan localmente con FAISS.
5. Cuando se hace una pregunta:
   - Se buscan los 4 chunks más similares semánticamente.
   - Se le pasan a Claude como contexto.
   - Claude responde **únicamente** con esa información.
   - Si la respuesta no está, responde literal: *"No tengo esa información en los datos disponibles."*

---

## 📚 Documentación

- **Informe técnico:** [`docs/informe.md`](docs/informe.md)
- **Prompt engineering:** [`docs/prompts_experimentacion.md`](docs/prompts_experimentacion.md)

---

## 🔒 Seguridad

- El archivo `.env` está en `.gitignore` y **nunca se sube a GitHub**.
- El `vector_store/` también está ignorado — se regenera automáticamente.
- La API key debe ser personal de cada usuario.

---

## 📝 Licencia

Proyecto académico — Taller 1, Aplicación de Técnicas Avanzadas de IA Generativa.
