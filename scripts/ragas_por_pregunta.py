"""RAGAS≈ local pregunta por pregunta (mismo cálculo que comparar_salidas.py), para ver dónde se pierde.
    python3 scripts/ragas_por_pregunta.py salidas/mark45.jsonl [otra.jsonl]"""
import json, sys
sys.path.insert(0, "scripts")
import comparar_salidas as cs
ev = cs.evaluador()
muestra = [p for p in ev.read_jsonl(cs.OFICIAL / "data/sample_50.jsonl") if p["formato"] != "multiple_choice"]
juez = cs.RagasLocal()
corridas = [{s["id"]: s for s in ev.read_jsonl(cs.Path(a))} for a in sys.argv[1:]]
tot = [0.0] * len(corridas)
for p in muestra:
    vals = []
    for i, c in enumerate(corridas):
        s = c.get(p["id"])
        v = 0.0 if not s or s.get("abstencion") else juez.puntuar(ev.ragas_text(s), p.get("respuesta_esperada") or "")
        tot[i] += v; vals.append(f"{v:.2f}")
    print(p["id"], p["formato"][:4], " ".join(vals), "|", (p.get("respuesta_esperada") or "")[:90].replace("\n", " "))
print("RAGAS≈ (de 30):", [round(30 * t / len(muestra), 2) for t in tot])
