# GitHub Copilot Instructions — Hoteles Estelar Chat Assistant

## Project Context

This is a Python 3.12 chatbot project for Hoteles Estelar S.A. using LangChain, uv package manager, and Streamlit. The project follows clean architecture with high cohesion and low coupling as core principles.

## Mandatory Rules

### Docstrings

Every module, class, and public function MUST have a docstring:

```python
"""module_name.py
-----------------
One-line description of what this module does."""


def process_data(input_path: str, format: str = "json") -> dict:
    """Short description of what the function does.

    Args:
        input_path: Path to the input file.
        format: Output format, either 'json' or 'text'.

    Returns:
        Dictionary with processed data.
    """
```

### Type Hints

Always add type hints to function signatures. Use modern Python syntax:

```python
# CORRECT
def responder(pregunta: str, top_k: int = 5) -> dict:

# INCORRECT
def responder(pregunta, top_k=5):
```

- Use `str | None` instead of `Optional[str]`.
- Use `list[str]` instead of `List[str]`.
- Use `dict[str, Any]` instead of `Dict[str, Any]`.

### Architecture Rules

- **Dependency direction**: `app/` imports from `llm/`, never the reverse.
- **Never import from `app/` inside `llm/`**.
- Each module in `llm/` has a single responsibility.
- Use dependency injection: functions accept `llm: BaseChatModel | None = None` rather than creating LLMs inline.
- Prompts live in `llm/prompts.py` or `system_prompt.txt`, never hardcoded in chain logic.

### Import Order

```python
# 1. Standard library
import os
import re

# 2. Third-party
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

# 3. Local imports
from llm.factory import crear_llm
from llm.prompts import PROMPT_QA
```

### Package Management

- This project uses **uv** as package manager, not pip or poetry.
- To add a dependency: `uv add <package>` (this updates `pyproject.toml` AND `uv.lock`).
- Never suggest `pip install` commands.
- After any dependency change, always run `uv lock`.

### LangChain Patterns

- Chains use the pipe operator: `PROMPT | llm | StrOutputParser()`.
- Never call `llm.invoke()` when a chain is more appropriate.
- Always use `StrOutputParser()` as the final step in a chain.
- Create LLM instances via `crear_llm()` from `llm/factory.py`.

### Streamlit Patterns

- Use `@st.cache_data` for expensive data loading operations.
- Use `st.session_state` for maintaining chat history.
- Never put business logic in Streamlit callbacks. Call domain functions from `llm/`.

## Code Generation Preferences

- When suggesting new features, create a new focused module in `llm/` rather than extending an existing one.
- When adding a new prompt, add it to `llm/prompts.py` as a `ChatPromptTemplate`.
- Environment variables are loaded via `python-dotenv` — never hardcode API keys or secrets.
- Use `pathlib.Path` for file paths, not `os.path`.
- Use f-strings for string formatting, not `%` or `.format()`.
- Prefer `Path.read_text(encoding="utf-8")` over `open()` for simple file reads.
- Error handling: use specific exceptions, never bare `except:`.

## File Naming

- Module names: `snake_case.py`.
- Test files: `test_<module_name>.py` in `tests/`.
- Data files: `descriptive_name.ext` in `data/`.
- Scripts: `snake_case.py` in `scripts/`.

## Testing

- Use `pytest` for all tests.
- Mock LLM calls in unit tests — never call real APIs in test suites.
- Test files go in `tests/` and mirror the `llm/` structure.
- Each new module should have at least a basic integration test.
