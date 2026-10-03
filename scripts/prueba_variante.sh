#!/bin/bash
# Prueba una variante sobre la muestra de 50: genera salidas/NOMBRE.jsonl, evaluador oficial, latencias y
# comparación pregunta por pregunta + RAGAS≈ local frente a Mark 44.
#   scripts/prueba_variante.sh NOMBRE <flags de legalrag.cli run>
# uso: prueba.sh NOMBRE [flags extra de run]  -> salidas/NOMBRE.jsonl + salidas/NOMBRE_oficial.json
# La raíz sale de la ubicación del script y el intérprete del entorno activo (PY=... para forzar otro).
set -e
cd "$(dirname "$(readlink -f "$0")")/.."
PY=${PY:-$(command -v python3)}
N=$1; shift
rm -f salidas/$N.jsonl salidas/$N.run.json salidas/$N.trace.jsonl
PYTHONPATH=src $PY -m legalrag.cli run --questions data/oficial/data/sample_50.jsonl --output salidas/$N.jsonl "$@"
$PY data/oficial/scripts/evaluate.py --submission salidas/$N.jsonl --split sample --out salidas/${N}_oficial.json >/dev/null
$PY -c "
import json;d=json.load(open('salidas/${N}_oficial.json'))
print('$N', 'total',d['total_automatico']['obtenidos'],'cerradas',d['cerradas']['aciertos'],'/',d['cerradas']['n'],'citas',d['citas']['puntos'],'abst',d['abstencion']['puntos'])"
$PY -c "
import json
rows=[json.loads(l) for l in open('salidas/$N.jsonl')]
lat=sorted(r['latencia_ms']/1000 for r in rows)
print('latencia media %.1fs  p95 %.1fs  max %.1fs  >22s: %d' % (sum(lat)/len(lat), lat[int(.95*len(lat))-1], lat[-1], sum(x>22 for x in lat)))"
$PY scripts/comparar_salidas.py salidas/mark44.jsonl salidas/$N.jsonl 2>&1 | grep -v "unauth\|Warn"
