"""models.py.

----------
Modelos Pydantic para entrada y salida estructurada del LLM.

Usados con ``with_structured_output`` para eliminar el parseo manual
de JSON y garantizar que el LLM devuelva datos consistentes.
"""

from pydantic import BaseModel, Field


class RespuestaQA(BaseModel):
    """Respuesta estructurada del asistente para preguntas sobre el reporte.

    La respuesta se genera con ``with_structured_output``, reemplazando
    el parseo manual de JSON que se hacía anteriormente.
    """

    respuesta: str = Field(
        description=(
            "Texto limpio y profesional para el colaborador. "
            "Debe responder directamente la consulta."
        )
    )
    encontrado: bool = Field(
        description="Si se encontró información relevante en el contexto provisto"
    )
    confianza: str = Field(
        description="Nivel de confianza de la respuesta: 'alta', 'media' o 'baja'"
    )
    nota: str = Field(
        default="",
        description=(
            "Instrucción adicional o aclaración sobre la vigencia, "
            "fuente o limitaciones de la información"
        ),
    )
    uso_tool_financiera: bool = Field(
        default=False,
        description="Si se usó la herramienta de consulta financiera (SQLite)",
    )
