"""factory.py.

----------
Crea instancias del LLM según el proveedor elegido.

Proveedores soportados:
  - "claude"  → Anthropic (requiere ANTHROPIC_API_KEY en .env)
  - "ollama"  → modelo local vía Ollama (requiere Ollama corriendo en localhost)
"""

import os

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

MODELOS_CLAUDE = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20251001",
    "claude-opus-4-5-20251001",
]

MODELOS_OLLAMA_SUGERIDOS = [
    "llama3.2",
    "llama3.1",
    "mistral",
    "gemma3",
    "phi4",
    "qwen2.5",
]


def crear_llm(
    proveedor: str = "claude",
    modelo: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> BaseChatModel:
    """Devuelve un LLM de LangChain listo para usar en una cadena.

    Parámetros:
      - proveedor:   "claude" | "ollama"
      - modelo:      nombre del modelo (usa el default de cada proveedor si es None)
      - temperature: temperatura de generación
      - max_tokens:  tokens máximos en la respuesta
    """
    if proveedor == "claude":
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise OSError("Falta ANTHROPIC_API_KEY. Configúrala en el archivo .env")
        return ChatAnthropic(
            model=modelo or MODELOS_CLAUDE[0],
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )

    if proveedor == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=modelo or MODELOS_OLLAMA_SUGERIDOS[0],
            temperature=temperature,
        )

    raise ValueError(f"Proveedor desconocido: '{proveedor}'. Usa 'claude' u 'ollama'.")
