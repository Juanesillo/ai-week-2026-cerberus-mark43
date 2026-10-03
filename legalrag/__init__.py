"""Acceso al paquete src/legalrag desde la raíz del repositorio.

El código del sistema vive entero en `src/legalrag/`. Esta carpeta solo redirige: al
reemplazar `__path__`, `import legalrag.X` desde la raíz resuelve a `src/legalrag/X` sin
pedir `PYTHONPATH=src`. Es lo que hace funcionar `python -m legalrag.cli ...` (los
comandos de corpus e índice) y `scripts/techo_citas.py`. `src/main.py` no lo necesita:
inserta `src/` en `sys.path` por su cuenta.

No poner módulos en esta carpeta: quedarían inalcanzables, porque `__path__` ya no apunta
aquí.
"""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "legalrag")]
