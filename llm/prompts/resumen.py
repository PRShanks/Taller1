"""resumen.py.

Prompt para el resumen ejecutivo de Hoteles Estelar.

Exporta:
  - PROMPT_RESUMEN: generación de resumen estructurado
"""

from langchain_core.prompts import ChatPromptTemplate

PROMPT_RESUMEN = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres el Asistente de Soporte Operativo Interno de Hoteles Estelar, "
            "especializado en el sector hotelero colombiano. Tu tarea es producir "
            "resúmenes ejecutivos claros, precisos "
            "y útiles para la toma de decisiones.\n\n"
            "REGLAS ESTRICTAS:\n"
            "- Basa tu resumen ÚNICAMENTE en la información del contexto provisto.\n"
            "- NO inventes cifras, fechas ni hechos que no estén en el contexto.\n"
            "- Si un dato no está disponible, indícalo en lugar de adivinar.\n"
            "- Usa terminología financiera correcta y cita las cifras con sus unidades.\n"
            "- Escribe en español, en tono profesional y conciso.\n",
        ),
        (
            "human",
            "Genera un resumen ejecutivo estructurado con las siguientes secciones:\n\n"
            "1. **Identificación de la empresa** (1-2 líneas).\n"
            "2. **Productos clave** (1-2 líneas).\n"
            "3. **Clientes** (1-2 líneas).\n"
            "4. **Desempeño financiero** (3-5 cifras más relevantes con interpretación).\n"
            "5. **Conclusión** (1-2 frases con la situación general).\n\n"
            "El resumen completo no debe exceder las 300 palabras.\n\n"
            "=== CONTEXTO ===\n{contexto}\n=== FIN DEL CONTEXTO ===",
        ),
    ]
)
