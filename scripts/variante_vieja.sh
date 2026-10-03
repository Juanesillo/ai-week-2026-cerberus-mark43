#!/bin/bash
# Una variante de Mark 44 sobre el índice ANTERIOR (raíz alternativa con data/ e index/ del 45,93), comparada con
# salidas/mark44_indice_viejo.jsonl.   uso: scripts/variante_vieja.sh NOMBRE <flags extra de legalrag.cli run>
set -e
cd "$(dirname "$(readlink -f "$0")")/.."
R=${RAIZ_VIEJA:-$HOME/Escritorio/mark/mark43v2/raiz_indice_viejo}
N=$1; shift
F="--hybrid --no-hyde --mc-thinking --multi-query --herramientas-v2 --normalizador --mc-rapido --mc-pensar-tokens 1536 --seguridad 90 --reranker-lote 16 --suficiencia --reformulador-iterativo --encabezado-canonico --reservar-nombradas --preferir-jurisprudencia"
rm -f salidas/$N.jsonl salidas/$N.run.json salidas/$N.trace.jsonl
PYTHONPATH=src python3 -m legalrag.cli --root "$R" run --questions data/oficial/data/sample_50.jsonl --output salidas/$N.jsonl $F "$@" > salidas/$N.log 2>&1
python3 data/oficial/scripts/evaluate.py --submission salidas/$N.jsonl --split sample --out salidas/${N}_oficial.json > /dev/null
grep -E "Latencia" salidas/$N.log
python3 scripts/comparar_salidas.py ${BASE:-salidas/mark44_indice_viejo.jsonl} salidas/$N.jsonl 2>&1 | grep -v "unauth\|Warn\|Loading\|LOAD\|UNEXPECTED\|Key \|---\|Notes\|ignored\|position_ids\|^$"
