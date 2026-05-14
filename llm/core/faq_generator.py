"""faq_generator.py.

----------------
Tarea 2 del taller: responde un set de preguntas frecuentes fijas
sobre el reporte financiero usando LangChain + Claude/Ollama.

Las preguntas son siempre las mismas; el LLM genera las respuestas
basándose en el contexto corporativo cargado.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from llm.clients.factory import crear_llm
from llm.data_loader import cargar_contexto
from llm.prompts.faq import PROMPT_FAQ

# Preguntas fijas — siempre las mismas, el modelo solo genera las respuestas
PREGUNTAS_FAQ: list[str] = [
    "¿Cuál es el nombre completo y el NIT de la empresa?",
    "¿Cuáles fueron los ingresos operacionales del período reportado?",
    "¿Cuál fue la utilidad neta del período y cómo varía respecto al período anterior?",
    "¿Cuántos hoteles opera la cadena y en qué ciudades están ubicados?",
    "¿Cuál es el nivel de endeudamiento o apalancamiento financiero de la empresa?",
    "¿Cuál fue el EBITDA o resultado operacional del período?",
    "¿Qué activos totales registra la empresa en su balance general?",
    "¿Cuál es la actividad económica principal de la empresa según el reporte?",
    "¿En qué consiste el programa 'Huésped Siempre Estelar'?",
    "¿Los hoteles Estelar permiten mascotas? ¿Qué requisitos hay?",
    "¿Qué acciones de sostenibilidad ha implementado Hoteles Estelar?",
    "¿Qué beneficios tiene la alianza entre Compensar y Hoteles Estelar?",
    "¿Qué caracteriza al Hotel Estelar Cartagena de Indias?",
    "¿Cuántos años de experiencia tiene Hoteles Estelar en el sector hotelero?",
    "¿Qué servicios ofrece Hoteles Estelar además del hospedaje?",
    "¿Qué importancia tienen los eventos empresariales dentro de la oferta de Hoteles Estelar?",
    "¿Qué tipo de viajeros hacen parte del segmento corporativo de Hoteles Estelar?",
    "¿Cuáles fueron los ingresos operacionales en 2024 y cuál fue su crecimiento respecto a 2023?",
    (
        "¿Cuál fue la utilidad neta en 2024 y cuánto representó como porcentaje"
        " de los ingresos (margen neto)?"
    ),
    "¿Cuál fue el EBITDA en 2024 y cuál fue su margen sobre ingresos?",
    (
        "¿Cuál fue el total de activos, pasivos y patrimonio registrado"
        " en el balance general de 2024?"
    ),
    "¿Cuánto sumó la deuda financiera en 2024 y cuál fue la razón Deuda/EBITDA?",
    (
        "¿Qué tendencia muestra la evolución de ingresos entre 2019 y 2024,"
        " y qué evento explica la caída de 2020?"
    ),
    (
        "Comparando el margen EBITDA de 2024 (14,0 %) con el de 2019 (10,2 %),"
        " ¿qué conclusión se puede extraer sobre la eficiencia operativa de la empresa?"
    ),
    (
        "El capital de trabajo neto ha sido negativo en todos los años del reporte."
        " ¿Qué implica esto para la liquidez de corto plazo y cómo lo mitiga la empresa?"
    ),
    (
        "Dado que los costos financieros en 2024 fueron COP 50.197 millones y el EBITDA fue"
        " COP 70.147 millones (cobertura 1,4x), ¿qué riesgo financiero representa esta situación"
        " y cómo ha evolucionado desde 2019?"
    ),
    (
        "¿Quién es el dueño o beneficiario final de Hoteles Estelar S.A."
        " y cómo está estructurada la cadena de control accionario?"
    ),
    (
        "¿Cuáles son las ubicaciones exactas (direcciones)"
        " de todos los hoteles Estelar en Medellín y Bogotá?"
    ),
    (
        "¿Qué alianzas o franquicias internacionales tiene Hoteles Estelar"
        " y bajo qué modalidad opera cada una?"
    ),
    (
        "¿Cuáles fueron los resultados financieros de Hoteles Estelar en 2024"
        " y cómo se comparan con el promedio del sector hotelero colombiano?"
    ),
    "¿Qué empresas del Grupo Aval están relacionadas con Hoteles Estelar y en qué sectores operan?",
]


def generar_faq(
    contexto: str | None = None,
    llm: BaseChatModel | None = None,
) -> str:
    """Genera respuestas para las preguntas fijas de PREGUNTAS_FAQ.

    Si no se pasa contexto, lo carga desde el archivo consolidado.
    Si no se pasa llm, usa Claude Haiku.
    """
    if contexto is None:
        contexto = cargar_contexto()
    if llm is None:
        llm = crear_llm(temperature=0.3, max_tokens=3072)

    preguntas_formateadas = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(PREGUNTAS_FAQ))

    cadena = PROMPT_FAQ | llm | StrOutputParser()
    return cadena.invoke(
        {
            "contexto": contexto,
            "preguntas": preguntas_formateadas,
        }
    )


if __name__ == "__main__":
    print("Generando FAQ...\n")
    print(generar_faq())
