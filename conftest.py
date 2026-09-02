"""Make the repository root importable so tests can `import src...`.

The project is not pip-installed in CI (it runs straight from a checkout), so
without this the `src` package would only be importable by accident, depending
on how pytest happens to set up sys.path.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
