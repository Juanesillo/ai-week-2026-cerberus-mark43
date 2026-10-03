#!/bin/bash
# Una variante que solo cambia un formato (p. ej. las abiertas): genera ese subconjunto, lo fusiona con una corrida
# completa de base y evalúa las 50 con el evaluador oficial. Cada pregunta se responde de forma independiente, así
# que la fusión equivale a la corrida completa (comprobarlo con una variante sin cambios: debe dar 0 cambios).
#   scripts/variante_parcial.sh NOMBRE BASE.jsonl SUBCONJUNTO.jsonl <flags extra sobre Mark 44>
#   RAIZ=<raíz con index/ y data/> (por defecto, la del repositorio)
set -e
cd "$(dirname "$(readlink -f "$0")")/.."
R=${RAIZ:-$(pwd)}
N=$1; BASE=$2; SUB=$3; shift 3
F="--hybrid --no-hyde --mc-thinking --multi-query --herramientas-v2 --normalizador --mc-rapido --mc-pensar-tokens 1536 --seguridad 90 --reranker-lote 16 --suficiencia --reformulador-iterativo --encabezado-canonico --reservar-nombradas --preferir-jurisprudencia"
rm -f salidas/${N}_parcial.jsonl salidas/${N}_parcial.run.json salidas/${N}_parcial.trace.jsonl
PYTHONPATH=src python3 -m legalrag.cli --root "$R" run --questions "$SUB" --output salidas/${N}_parcial.jsonl $F "$@" \
  > salidas/$N.log 2>&1
python3 scripts/fusionar.py "$BASE" salidas/${N}_parcial.jsonl salidas/$N.jsonl
python3 data/oficial/scripts/evaluate.py --submission salidas/$N.jsonl --split sample --out salidas/${N}_oficial.json > /dev/null
grep -E "Latencia" salidas/$N.log || true
python3 scripts/comparar_salidas.py "$BASE" salidas/$N.jsonl --sin-ragas-local 2>&1 | grep -v "unauth\|Warn"
