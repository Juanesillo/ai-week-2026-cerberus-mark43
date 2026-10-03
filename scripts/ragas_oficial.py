"""RAGAS con el juez real, usando data/oficial/scripts/evaluate.py SIN modificarlo y SIN llamadas paralelas.

    export OPENROUTER_API_KEY="..."
    python3 scripts/ragas_oficial.py salidas/mark46.jsonl --max 1     # prueba: 1 respuesta, muestra el costo
    python3 scripts/ragas_oficial.py salidas/mark46.jsonl             # las 35 de texto libre

Cómo respeta las reglas del equipo:
- El evaluador oficial se ejecuta tal cual (mismo archivo, mismos argumentos que indica su docstring:
  --submission, --split sample, --ragas, --out). No se importa ni se parchea nada de RAGAS.
- Sin paralelismo: a cada ejecución se le pasa un archivo con UNA sola respuesta de texto libre, así que el
  evaluador hace una sola calificación por vez (con 35 a la vez, RAGAS lanza 16 llamadas simultáneas; la corrida
  del 1-oct falló en las 35 y cobró 0,89 USD).
- Sin gastar dos veces: cada nota se guarda en salidas/ragas_oficial_cache.json por (id, texto calificado). Al
  medir otra versión solo se pagan las respuestas que cambiaron. Las fallidas no se guardan.
- Corte de seguridad: se detiene tras 2 fallas seguidas del juez, para no seguir pagando reintentos.

Equivalencia con la corrida de las 35 juntas: el evaluador divide siempre por las 35 juzgadas (las ausentes cuentan
cero), así que la nota de una respuesta es correctness × 35 y el total es 30 × Σ notas / 35. El reporte redondea
correctness a 4 decimales: el error acumulado en el total es de ±0,05 puntos como máximo.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EVALUADOR = RAIZ / "data/oficial/scripts/evaluate.py"
CACHE = RAIZ / "salidas/ragas_oficial_cache.json"


def evaluador():
    """Solo para leer ragas_text (qué texto se califica); no se modifica nada."""
    sys.path.insert(0, str(EVALUADOR.parent))
    spec = importlib.util.spec_from_file_location("evaluador_oficial", EVALUADOR)
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    return ev


def uso_usd():
    """Consumo acumulado de la llave (GET /api/v1/key, gratis). None si no se puede consultar."""
    import requests
    llave = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not llave:
        return None
    try:
        r = requests.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {llave}"}, timeout=30)
        return float(r.json()["data"]["usage"]) if r.ok else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--max", type=int, default=0, help="califica como mucho N respuestas nuevas (0 = todas)")
    args = ap.parse_args()
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        sys.exit('Falta la llave en esta terminal: export OPENROUTER_API_KEY="..."')

    ev = evaluador()
    muestra = {r["id"]: r for r in ev.read_jsonl(ev.DATA / "sample_50.jsonl")}
    juzgadas = [q for q, r in muestra.items() if r["formato"] != "multiple_choice"]
    lineas = {json.loads(l)["id"]: l.rstrip("\n") for l in open(args.salida, encoding="utf-8") if l.strip()}
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}

    def clave(qid):
        texto = ev.ragas_text(json.loads(lineas[qid]))
        return hashlib.sha256(json.dumps([qid, texto], ensure_ascii=False).encode()).hexdigest()

    pendientes = [q for q in juzgadas if q in lineas and not json.loads(lineas[q]).get("abstencion")
                  and clave(q) not in cache]
    if args.max:
        pendientes = pendientes[:args.max]
    print(f"{len(juzgadas)} juzgadas · {len(juzgadas) - len(pendientes)} ya calificadas o sin respuesta · "
          f"{len(pendientes)} al juez, una por vez", flush=True)
    antes = uso_usd()
    seguidas = 0
    with tempfile.TemporaryDirectory() as tmp:
        for n, qid in enumerate(pendientes, 1):
            sub, out = Path(tmp) / "una.jsonl", Path(tmp) / "reporte.json"
            sub.write_text(lineas[qid] + "\n", encoding="utf-8")
            t0 = time.time()
            # El encoder de similitud del juez (e5-large) corre en CPU: así no compite por la GPU con el pipeline. El
            # evaluador no cambia (mismo archivo, mismo modelo); solo se oculta la GPU a ese proceso.
            proc = subprocess.run([sys.executable, str(EVALUADOR), "--submission", str(sub), "--split", "sample",
                                   "--ragas", "--out", str(out)], capture_output=True, text=True,
                                  env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
            r = json.loads(out.read_text(encoding="utf-8")).get("correccion_ragas", {}) if out.is_file() else {}
            if proc.returncode or r.get("n_respondidos") != 1 or r.get("n_fallidos"):
                seguidas += 1
                print(f"  {n}/{len(pendientes)} id {qid}: FALLÓ ({time.time() - t0:.0f}s) "
                      f"{(proc.stderr or '').strip()[-300:]}", flush=True)
                if seguidas >= 2:
                    print("Dos fallas seguidas: me detengo para no pagar más reintentos.", flush=True)
                    break
                continue
            seguidas = 0
            nota = round(r["correctness"] * len(juzgadas), 4)
            cache[clave(qid)] = {"id": qid, "nota": nota, "fecha": time.strftime("%Y-%m-%d %H:%M")}
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            print(f"  {n}/{len(pendientes)} id {qid}: {nota:.3f} ({time.time() - t0:.0f}s)", flush=True)
    despues = uso_usd()

    notas = {q: (cache.get(clave(q), {}).get("nota") if q in lineas and not json.loads(lineas[q]).get("abstencion")
                 else 0.0) for q in juzgadas}
    faltan = [q for q, v in notas.items() if v is None]
    total = sum(v or 0.0 for v in notas.values())
    reporte = {"salida": args.salida.name, "juez": ev.JUEZ_MODELO, "n_juzgados": len(juzgadas),
               "n_calificadas": len(juzgadas) - len(faltan), "sin_calificar": faltan,
               "correctness": round(total / len(juzgadas), 4), "puntos": round(30 * total / len(juzgadas), 2),
               "notas": notas}
    destino = args.salida.with_name(args.salida.stem + "_ragas_oficial.json")
    destino.write_text(json.dumps(reporte, ensure_ascii=False, indent=1), encoding="utf-8")
    costo = f"{despues - antes:.4f} USD" if antes is not None and despues is not None else "no disponible"
    print(f"\nRAGAS (juez real, evaluador oficial sin cambios): {reporte['puntos']} de 30 · correctness "
          f"{reporte['correctness']} · calificadas {reporte['n_calificadas']}/{len(juzgadas)}"
          + (f" (faltan {len(faltan)}: vuelva a correr; solo se pagan esas)" if faltan else "")
          + f"\nCosto de esta corrida: {costo} · reporte: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
