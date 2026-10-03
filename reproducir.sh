#!/usr/bin/env bash
# Comando único de reproducción (§6.2 y §9.2 n.º 2 del enunciado).
#
#   ./reproducir.sh
#
# Desde un árbol recién clonado: crea el entorno, instala las dependencias, comprueba que
# estén el corpus y el índice, responde las 50 preguntas de muestra y pasa el evaluador
# oficial. No descarga el corpus: pesa ~15 GB y se publica aparte (§9.3), con el enlace en
# la sección «Corpus e índice» del README.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

PYTHON="${PYTHON:-python3.10}"

echo "==> 1/4  Intérprete"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "No se encontró $PYTHON." >&2
  echo "El proyecto exige Python 3.10 (pyproject.toml: requires-python >=3.10,<3.11)." >&2
  echo "Si su intérprete 3.10 se llama de otro modo: PYTHON=/ruta/a/python3.10 ./reproducir.sh" >&2
  exit 1
fi
"$PYTHON" - <<'PY'
import sys
if sys.version_info[:2] != (3, 10):
    sys.exit(f"Python 3.10 requerido; este es {sys.version.split()[0]}")
PY

echo "==> 2/4  Entorno y dependencias"
[ -d .venv ] || "$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

echo "==> 3/4  Corpus e índice"
faltan=()
[ -f index/build.json ]        || faltan+=("index/")
[ -d data/processed ]          || faltan+=("data/processed/")
[ -f corpus_manifest.json ]    || faltan+=("corpus_manifest.json")
[ -f data/oficial/data/sample_50.jsonl ] || faltan+=("data/oficial/data/sample_50.jsonl")
if [ ${#faltan[@]} -gt 0 ]; then
  echo "Faltan, y no se descargan solos: ${faltan[*]}" >&2
  echo "Descargue el comprimido de la sección «Corpus e índice» del README y descomprímalo" >&2
  echo "en la raíz del repositorio, de modo que queden index/ y data/processed/." >&2
  exit 1
fi

echo "==> 4/4  Ejecución sobre las 50 preguntas de muestra"
python src/main.py --split sample

echo
echo "Listo. Respuestas en salidas/ y el reporte del evaluador oficial arriba."
echo "Para las 992 del examen:  python src/main.py --split test   ->  submissions.jsonl"
