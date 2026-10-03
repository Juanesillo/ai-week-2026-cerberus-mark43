"""Nota real de RAGAS por pregunta, cruzada con el diagnóstico de la generación.

    python3 scripts/analizar_ragas.py salidas/mark46.jsonl              # una corrida
    python3 scripts/analizar_ragas.py salidas/mark46.jsonl salidas/n9_irac_kelsenorden.jsonl   # comparar dos

Lee las notas guardadas por scripts/ragas_oficial.py (salidas/ragas_oficial_cache.json, juez real) y, para cada
pregunta de texto libre, muestra la nota y tres señales del diagnóstico:
  ref_pasajes  la norma de referencia está en los 10 pasajes recuperados
  ref_texto    la respuesta (el texto que juzga RAGAS) usa esa norma
  palabras     longitud del texto juzgado frente a la respuesta de referencia
Al final agrega las notas por grupo (usa / no usa la evidencia correcta) para ver dónde se pierden los puntos.
No llama al juez ni gasta nada.
"""
import hashlib
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EVALUADOR = RAIZ / "data/oficial/scripts/evaluate.py"
CACHE = RAIZ / "salidas/ragas_oficial_cache.json"
sys.path.insert(0, str(EVALUADOR.parent))
spec = importlib.util.spec_from_file_location("evaluador_oficial", EVALUADOR)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
import citations  # noqa: E402


def notas(ruta, cache):
    filas = {r["id"]: r for r in (json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip())}
    out = {}
    for qid, r in filas.items():
        if r.get("formato") == "multiple_choice":
            continue
        k = hashlib.sha256(json.dumps([qid, ev.ragas_text(r)], ensure_ascii=False).encode()).hexdigest()
        out[qid] = (cache.get(k, {}).get("nota"), r)
    return out


def main():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    muestra = {r["id"]: r for r in ev.read_jsonl(ev.DATA / "sample_50.jsonl")}
    corridas = [(Path(a).name, notas(a, cache)) for a in sys.argv[1:]]
    nombre, base = corridas[0]
    grupos = {"usa la norma de referencia": [], "la tiene en los pasajes pero no la usa": [],
              "no la tiene en los pasajes": [], "sin norma de referencia": []}
    print(f"{'id':>5} {'formato':8} " + " ".join(f"{n[:18]:>18}" for n, _ in corridas) + "  ref_pasajes ref_texto palabras(nuestra/ref)")
    for qid in sorted(base):
        nota, r = base[qid]
        k = muestra[qid]
        ref = citations.bodies(citations.extract(k.get("legal_basis") or ""))
        pas = set()
        for p in (r.get("pasajes_recuperados") or [])[:10]:
            pas |= citations.bodies(citations.extract(p.get("texto") or ""))
        texto = ev.ragas_text(r)
        usa = bool(ref & pas & citations.bodies(citations.extract(texto)))
        en_pasajes = bool(ref & pas)
        grupo = ("sin norma de referencia" if not ref else "usa la norma de referencia" if usa
                 else "la tiene en los pasajes pero no la usa" if en_pasajes else "no la tiene en los pasajes")
        if nota is not None:
            grupos[grupo].append(nota)
        celdas = " ".join(f"{(c[1].get(qid, (None,))[0]) if c[1].get(qid, (None,))[0] is not None else float('nan'):18.3f}"
                          for c in corridas)
        print(f"{qid:>5} {k['formato'][:8]:8} {celdas}  {'sí' if en_pasajes else 'no':>11} {'sí' if usa else 'no':>9} "
              f"{len(texto.split()):>4}/{len((k.get('respuesta_esperada') or '').split())}")
    print(f"\nNotas de {nombre} por grupo:")
    for g, v in grupos.items():
        if v:
            print(f"  {g:40s} n={len(v):2d}  media {st.mean(v):.3f}")
    for n, c in corridas:
        v = [x[0] for x in c.values() if x[0] is not None]
        if v:
            print(f"{n}: {len(v)}/35 calificadas · RAGAS ≈ {30 * sum(v) / 35:.2f} de 30 (las no calificadas cuentan 0)")


if __name__ == "__main__":
    main()
