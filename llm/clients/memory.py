"""memory.py.

---------
Gestión de memoria del agente: historial de conversación y datos del usuario.

Implementación actual: InMemoryStore de LangGraph (volátil, por sesión).
Objetivo futuro: reemplazar por un store persistente (Postgres, Redis, etc.)
sin cambios en la interfaz pública.

Arquitectura de namespaces:
    - Historial: ("sessions", session_id, "messages")
    - Datos de usuario: ("users", user_id, "profile")

Ejemplo de uso::

    from llm.memory import SessionMemory

    memory = SessionMemory()
    memory.save_message("sesion-001", "human", "¿Cuáles fueron los ingresos?")
    memory.save_message("sesion-001", "ai", "Los ingresos fueron COP 120.000M")
    historial = memory.get_history("sesion-001")
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.store.memory import InMemoryStore

# ---------------------------------------------------------------------------
# Constantes de namespaces
# ---------------------------------------------------------------------------
SESSIONS_NS = "sessions"
USERS_NS = "users"
MESSAGES_NS = "messages"
PROFILE_NS = "profile"

# Límite por defecto de mensajes en el historial
DEFAULT_HISTORY_LIMIT = 20


class SessionMemory:
    """Gestiona la memoria de conversación y datos del usuario por sesión.

    Por ahora usa InMemoryStore (volátil). Para hacer persistente,
    reemplazar el store por uno implementado sobre una base de datos
    (Postgres, Redis, etc.) que cumpla la interfaz BaseStore de LangGraph.

    Parámetros:
        store: Instancia del store (crea una nueva si es None).
               Compartir la misma instancia entre llamadas permite
               persistir datos durante la sesión de Streamlit.
    """

    def __init__(self, store: InMemoryStore | None = None) -> None:
        """Inicializa el store; crea uno nuevo si no se proporciona."""
        self._store = store if store is not None else InMemoryStore()

    @property
    def store(self) -> InMemoryStore:
        """Acceso al store subyacente para operaciones avanzadas."""
        return self._store

    # -----------------------------------------------------------------------
    # Historial de conversación
    # -----------------------------------------------------------------------

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Guarda un mensaje en el historial de la sesión.

        Parámetros:
            session_id: Identificador único de la sesión.
            role: Rol del mensaje ('human' o 'ai').
            content: Contenido del mensaje.
        """
        namespace = (SESSIONS_NS, session_id, MESSAGES_NS)
        key = f"{role}-{uuid.uuid4().hex[:8]}"
        self._store.put(
            namespace,
            key,
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def get_history(
        self,
        session_id: str,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[BaseMessage]:
        """Recupera el historial reciente de la sesión como mensajes de LangChain.

        Los mensajes se ordenan cronológicamente (más antiguo primero)
        y se limitan a los últimos ``limit`` mensajes.

        Parámetros:
            session_id: Identificador único de la sesión.
            limit: Número máximo de mensajes a recuperar.

        Devuelve:
            Lista de BaseMessage (HumanMessage o AIMessage).
        """
        namespace = (SESSIONS_NS, session_id, MESSAGES_NS)
        items = self._store.search(namespace, limit=200)

        # Ordenar por timestamp (más antiguo primero)
        sorted_items = sorted(
            items,
            key=lambda item: item.value.get("timestamp", ""),
        )

        # Tomar solo los últimos ``limit`` mensajes
        recent = sorted_items[-limit:] if len(sorted_items) > limit else sorted_items

        messages: list[BaseMessage] = []
        for item in recent:
            role = item.value.get("role", "human")
            content = item.value.get("content", "")
            if role == "ai":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))

        return messages

    def clear_session(self, session_id: str) -> None:
        """Elimina todo el historial de una sesión.

        Parámetros:
            session_id: Identificador de la sesión a limpiar.
        """
        namespace = (SESSIONS_NS, session_id, MESSAGES_NS)
        items = self._store.search(namespace, limit=1000)
        for item in items:
            self._store.delete(namespace, item.key)

    def session_exists(self, session_id: str) -> bool:
        """Verifica si una sesión tiene historial guardado.

        Parámetros:
            session_id: Identificador de la sesión.

        Devuelve:
            True si la sesión tiene al menos un mensaje.
        """
        namespace = (SESSIONS_NS, session_id, MESSAGES_NS)
        items = self._store.search(namespace, limit=1)
        return len(items) > 0

    # -----------------------------------------------------------------------
    # Datos personalizados del usuario
    # -----------------------------------------------------------------------

    def save_user_data(
        self,
        user_id: str,
        key: str,
        value: dict,
    ) -> None:
        """Guarda datos personalizados del usuario.

        Parámetros:
            user_id: Identificador del usuario.
            key: Clave del dato (ej: 'preferences', 'context').
            value: Diccionario con los datos a guardar.
        """
        namespace = (USERS_NS, user_id, PROFILE_NS)
        self._store.put(namespace, key, value)

    def get_user_data(
        self,
        user_id: str,
        key: str,
    ) -> dict | None:
        """Recupera datos personalizados del usuario.

        Parámetros:
            user_id: Identificador del usuario.
            key: Clave del dato a recuperar.

        Devuelve:
            Diccionario con los datos, o None si no existe.
        """
        namespace = (USERS_NS, user_id, PROFILE_NS)
        item = self._store.get(namespace, key)
        return item.value if item else None

    def delete_user_data(
        self,
        user_id: str,
        key: str,
    ) -> None:
        """Elimina un dato personalizado del usuario.

        Parámetros:
            user_id: Identificador del usuario.
            key: Clave del dato a eliminar.
        """
        namespace = (USERS_NS, user_id, PROFILE_NS)
        self._store.delete(namespace, key)


if __name__ == "__main__":
    # Demo rápida de la memoria
    mem = SessionMemory()
    sid = "demo-session"

    print("Guardando mensajes de demo...")
    mem.save_message(sid, "human", "¿Cuáles fueron los ingresos de 2024?")
    mem.save_message(sid, "ai", "Los ingresos operacionales fueron COP 120.000M.")
    mem.save_message(sid, "human", "¿Y el EBITDA?")
    mem.save_message(sid, "ai", "El EBITDA fue COP 70.147M con un margen del 14.0%.")

    print("Historial recuperado:")
    for msg in mem.get_history(sid):
        role = "👤" if msg.type == "human" else "🤖"
        print(f"  {role} {msg.content}")

    print(f"\nSesión existe: {mem.session_exists(sid)}")
    print(f"Total mensajes: {len(mem.get_history(sid))}")

    # Demo de datos de usuario
    mem.save_user_data("usuario-1", "preferences", {"idioma": "es", "formato": "breve"})
    prefs = mem.get_user_data("usuario-1", "preferences")
    print(f"\nPreferencias del usuario: {prefs}")

    # Limpiar
    mem.clear_session(sid)
    print(f"\nSesión limpiada. Historial vacío: {len(mem.get_history(sid)) == 0}")
