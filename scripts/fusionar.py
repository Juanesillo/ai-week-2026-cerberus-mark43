"""Fusiona una corrida parcial (subconjunto de preguntas) sobre una corrida completa de la muestra.
    python3 scripts/fusionar.py base.jsonl parcial.jsonl salida.jsonl
Sirve para medir cambios que solo tocan un formato sin regenerar las 50 (cada pregunta es independiente)."""
import json, sys
base, parcial, salida = sys.argv[1:4]
nuevas = {json.loads(l)["id"]: l for l in open(parcial, encoding="utf-8") if l.strip()}
with open(salida, "w", encoding="utf-8") as f:
    for l in open(base, encoding="utf-8"):
        if l.strip():
            f.write(nuevas.get(json.loads(l)["id"], l.rstrip("\n")).rstrip("\n") + "\n")
print(f"{len(nuevas)} reemplazadas -> {salida}")
