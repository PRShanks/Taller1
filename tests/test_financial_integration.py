"""test_financial_integration.py.

Tests de integración para el tool-calling loop financiero en el Q&A.

Verifica que ``responder_pregunta`` maneje correctamente:
  - LLM que invoca ``query_financiero`` → ``uso_tool_financiera=True``
  - LLM que no invoca la tool → ``uso_tool_financiera=False``
  - LLM sin soporte de ``bind_tools`` (fallback) → False, sin error
  - Offline (sin vector store) → mensaje sin tool
"""

from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from llm.core.qa import responder_pregunta
from llm.models import RespuestaQA

# ruff: noqa: D102, D107


# =============================================================================
# Mocks
# =============================================================================


class MockVectorStore:
    """Vector store simulado que devuelve documentos de prueba."""

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        return [
            Document(
                page_content="Texto de prueba sobre ingresos y EBITDA de Hoteles Estelar.",
                metadata={"source": "test.md"},
            ),
        ]


class MockLLMConTools:
    """Mock de LLM que simula tool calling.

    Atributos:
        debe_usar_tool: Si ``True``, la primera invocación devuelve
            ``tool_calls``. Si ``False``, devuelve solo texto.
        call_count: Contador de invocaciones para distinguir primera
            llamada (bind_tools) de segunda (structured output).
    """

    def __init__(self, debe_usar_tool: bool = False) -> None:
        self.debe_usar_tool = debe_usar_tool
        self.call_count = 0

    def bind_tools(self, tools: list) -> "MockLLMConTools":
        """Simula bind_tools — retorna self para que invoke funcione."""
        return self

    def with_structured_output(self, model: type, **kwargs) -> "MockLLMConTools":
        """Simula with_structured_output — retorna self."""
        return self

    def __call__(self, mensajes: list, **kwargs) -> AIMessage | RespuestaQA:
        """Permite usar el mock como callable en chains (``PROMPT_QA | mock``)."""
        return self.invoke(mensajes, **kwargs)

    def invoke(self, mensajes: list, **kwargs) -> AIMessage | RespuestaQA:
        """Devuelve AIMessage en primera llamada, RespuestaQA en la segunda."""
        self.call_count += 1

        if self.call_count == 1:
            # Primera invocación → respuesta bind_tools
            if self.debe_usar_tool:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "query_financiero",
                            "args": {"concepto": "EBITDA", "anio": 2024},
                            "id": "call_123",
                        },
                    ],
                )
            return AIMessage(content="Respuesta normal del asistente basada en RAG.")

        # Segunda invocación → structured output (RespuestaQA)
        return RespuestaQA(
            respuesta=(
                "EBITDA 2024: 81,204 millones COP."
                if self.debe_usar_tool
                else "Respuesta normal del asistente."
            ),
            encontrado=True,
            confianza="alta" if self.debe_usar_tool else "media",
            nota=(
                "Dato financiero obtenido via tool."
                if self.debe_usar_tool
                else "Respuesta basada en contexto RAG."
            ),
            uso_tool_financiera=self.debe_usar_tool,
        )


class MockLLMSinBindTools:
    """Mock de LLM que NO soporta bind_tools (simula Ollama).

    ``bind_tools`` lanza ``TypeError``, lo que debe disparar el fallback
    a RAG-only.
    """

    def bind_tools(self, tools: list) -> None:
        raise TypeError("Mock: este LLM no soporta bind_tools.")

    def with_structured_output(self, model: type, **kwargs) -> "MockLLMSinBindTools":
        return self

    def __call__(self, mensajes: list, **kwargs) -> RespuestaQA:
        """Permite usar el mock como callable en chains (``PROMPT_QA | mock``)."""
        return self.invoke(mensajes, **kwargs)

    def invoke(self, mensajes: list, **kwargs) -> RespuestaQA:
        return RespuestaQA(
            respuesta="Respuesta desde RAG-only (fallback por bind_tools no soportado).",
            encontrado=True,
            confianza="media",
            nota="Modo RAG-only por limitaciones del proveedor.",
            uso_tool_financiera=False,
        )


# =============================================================================
# Tests
# =============================================================================


class TestToolCallingLoop:
    """Tests del tool-calling loop en ``responder_pregunta``.

    Todos los tests mockean ``crear_vector_store`` y ``crear_embeddings``
    para no depender de Supabase real.
    """

    @patch("llm.core.qa.crear_vector_store")
    @patch("llm.core.qa.crear_embeddings")
    def test_con_tool_call(
        self,
        mock_crear_embeddings: MagicMock,
        mock_crear_vector_store: MagicMock,
    ) -> None:
        """Cuando el LLM invoca la tool, ``uso_tool_financiera`` debe ser ``True``."""
        mock_crear_vector_store.return_value = MockVectorStore()

        llm = MockLLMConTools(debe_usar_tool=True)

        resultado = responder_pregunta(
            pregunta="¿Cuál fue el EBITDA en 2024?",
            llm=llm,
        )

        assert resultado["uso_tool_financiera"] is True
        assert resultado["encontrado"] is True
        assert "EBITDA" in resultado["respuesta"]
        assert "fuentes" in resultado
        assert len(resultado["fuentes"]) == 1

    @patch("llm.core.qa.crear_vector_store")
    @patch("llm.core.qa.crear_embeddings")
    def test_sin_tool_call(
        self,
        mock_crear_embeddings: MagicMock,
        mock_crear_vector_store: MagicMock,
    ) -> None:
        """Cuando el LLM no invoca la tool, ``uso_tool_financiera`` debe ser ``False``."""
        mock_crear_vector_store.return_value = MockVectorStore()

        llm = MockLLMConTools(debe_usar_tool=False)

        resultado = responder_pregunta(
            pregunta="¿Qué servicios ofrece el hotel?",
            llm=llm,
        )

        assert resultado["uso_tool_financiera"] is False
        assert resultado["encontrado"] is True
        assert "RAG" in resultado["respuesta"] or "normal" in resultado["respuesta"]

    @patch("llm.core.qa.crear_vector_store")
    @patch("llm.core.qa.crear_embeddings")
    def test_fallback_sin_bind_tools(
        self,
        mock_crear_embeddings: MagicMock,
        mock_crear_vector_store: MagicMock,
    ) -> None:
        """LLM sin ``bind_tools`` debe caer a RAG-only sin error."""
        mock_crear_vector_store.return_value = MockVectorStore()

        llm = MockLLMSinBindTools()

        resultado = responder_pregunta(
            pregunta="¿Cuál fue el EBITDA en 2024?",
            llm=llm,
        )

        assert resultado["uso_tool_financiera"] is False
        assert resultado["encontrado"] is True
        assert "RAG-only" in resultado["respuesta"]

    @patch("llm.core.qa.crear_vector_store")
    @patch("llm.core.qa.crear_embeddings")
    def test_offline_sin_vector_store(
        self,
        mock_crear_embeddings: MagicMock,
        mock_crear_vector_store: MagicMock,
    ) -> None:
        """Sin Supabase (vector_store=None), debe devolver mensaje offline."""
        mock_crear_vector_store.return_value = None

        resultado = responder_pregunta(pregunta="¿Cuál fue el EBITDA?")

        assert resultado["uso_tool_financiera"] is False
        assert resultado["encontrado"] is False
        assert "no está configurado" in resultado["respuesta"]
        assert resultado["fuentes"] == []

    @patch("llm.core.qa.crear_vector_store")
    @patch("llm.core.qa.crear_embeddings")
    def test_dict_contiene_todos_los_campos(
        self,
        mock_crear_embeddings: MagicMock,
        mock_crear_vector_store: MagicMock,
    ) -> None:
        """El dict retornado debe tener todos los campos esperados."""
        mock_crear_vector_store.return_value = MockVectorStore()

        llm = MockLLMConTools(debe_usar_tool=True)
        resultado = responder_pregunta(
            pregunta="¿Cuál fue el EBITDA en 2024?",
            llm=llm,
        )

        campos_esperados = {
            "respuesta",
            "encontrado",
            "confianza",
            "nota",
            "fuentes",
            "uso_tool_financiera",
        }
        assert set(resultado.keys()) == campos_esperados, (
            f"Campos incorrectos: faltan {campos_esperados - set(resultado.keys())}"
        )
