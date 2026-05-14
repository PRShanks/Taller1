"""conftest.py.

Configuración compartida para todos los tests del proyecto.

Agrega el directorio raíz del proyecto al ``sys.path`` para que los tests
puedan importar módulos de ``llm/``, ``app/``, etc. sin necesidad de
configurar ``PYTHONPATH`` manualmente.
"""

import sys
from pathlib import Path

# Raíz del proyecto = parent de tests/
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
