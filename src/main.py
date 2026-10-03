"""Cerberus de punta a punta, en un solo comando: responde la muestra (o el examen) y pasa el evaluador oficial.

    python3 src/main.py                 # el mark más reciente sobre las 50 de muestra + evaluador oficial
    python3 src/main.py --mark 42       # otro mark (ver MARKS)
    python3 src/main.py --split test    # las 992 del examen -> submissions.jsonl (sin evaluador)
    python3 src/main.py --split test --reanudar   # si se cortó: sigue desde la última respuesta escrita

Antes de empezar comprueba que estén el índice (`index/`), el corpus procesado (`data/processed/`), el manifiesto
(`corpus_manifest.json`) y el material oficial (`data/oficial/`). Cada corrida reemplaza la anterior del mismo mark
(se aparta como `<salida>.anterior.jsonl`), salvo con `--reanudar`.
"""
import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

# Las opciones de cada mark viven en `legalrag.config` para que la entrega y la interfaz usen las mismas.
from legalrag.config import MARKS  # noqa: E402


def comprobar(config):
    faltan = [str(p.relative_to(RAIZ)) for p in (config.index_dir / "build.json", config.prepared,
                                                 RAIZ / "data/oficial/data/sample_50.jsonl")
              if not p.exists()]
    if config.normalizador_citas and not (RAIZ / "corpus_manifest.json").is_file():
        faltan.append("corpus_manifest.json (lo usa el normalizador de citas)")
    if faltan:
        sys.exit("Faltan datos en esta carpeta: " + ", ".join(faltan) + "\nEnlacen o copien index/, data/ y "
                 "corpus_manifest.json desde la carpeta donde se construyó el índice (la de Mark 42), por ejemplo:\n"
                 "  ln -s /ruta/a/mark42/index index && ln -s /ruta/a/mark42/data data && "
                 "ln -s /ruta/a/mark42/corpus_manifest.json corpus_manifest.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mark", type=int, default=max(MARKS), choices=sorted(MARKS))
    ap.add_argument("--split", choices=("sample", "test"), default="sample")
    ap.add_argument("--ragas", action="store_true", help="evalúa también texto libre (OPENROUTER_API_KEY)")
    ap.add_argument("--reanudar", action="store_true",
                    help="retoma una corrida interrumpida sin repetir lo ya respondido (mismo banco, índice, código y "
                         "mark; si cambió algo, se niega)")
    args = ap.parse_args()

    from legalrag.silencio import silenciar
    silenciar()
    from legalrag.config import CONFIG
    from legalrag.pipeline import run

    config = replace(CONFIG, root=RAIZ, **MARKS[args.mark])
    comprobar(config)
    if args.split == "test":
        preguntas, salida = RAIZ / "data/oficial/data/test_992.jsonl", RAIZ / "submissions.jsonl"
    else:
        preguntas, salida = RAIZ / "data/oficial/data/sample_50.jsonl", RAIZ / f"salidas/mark{args.mark}.jsonl"
    if not preguntas.is_file():
        sys.exit(f"No está {preguntas.relative_to(RAIZ)}")
    if args.reanudar and salida.exists():
        # Un corte en plena escritura puede dejar la última línea a medias: se conserva una copia y se recorta al
        # último registro completo para que la corrida siga desde ahí.
        lineas = salida.read_text(encoding="utf-8").splitlines(keepends=True)
        completas = []
        for linea in lineas:
            try:
                json.loads(linea)
            except ValueError:
                break
            completas.append(linea if linea.endswith("\n") else linea + "\n")
        if len(completas) < len(lineas) or (lineas and not lineas[-1].endswith("\n")):
            shutil.copy(salida, salida.with_name(salida.stem + ".antes_de_reanudar.jsonl"))
            salida.write_text("".join(completas), encoding="utf-8")
        print(f"Reanudando: {len(completas)} respuestas ya están en {salida.relative_to(RAIZ)}")
    elif salida.exists():
        anterior = salida.with_name(salida.stem + ".anterior.jsonl")
        shutil.move(salida, anterior)
        for extra in (".run.json", ".trace.jsonl"):
            viejo = salida.with_suffix(extra)
            if viejo.exists():
                viejo.unlink()
        print(f"La corrida anterior quedó en {anterior.relative_to(RAIZ)}")
    print(f"Cerberus Mark {args.mark} · {preguntas.name} · opciones {MARKS[args.mark]}", flush=True)
    run(config, preguntas, salida, resume=args.reanudar, expected_count=992 if args.split == "test" else None)
    if args.split == "test":
        print(f"Entrega: {salida.relative_to(RAIZ)}")
        return
    reporte = salida.with_name(salida.stem + "_oficial.json")
    subprocess.run([sys.executable, str(RAIZ / "data/oficial/scripts/evaluate.py"), "--submission", str(salida),
                    "--split", "sample", "--out", str(reporte)], check=True, capture_output=True)
    d = json.loads(reporte.read_text(encoding="utf-8"))
    ragas = None
    if args.ragas:
        # El juez real con el evaluador oficial SIN modificar y sin llamadas paralelas: una respuesta por ejecución,
        # con caché de notas (scripts/ragas_oficial.py). Con las 35 juntas RAGAS lanza 16 llamadas simultáneas.
        subprocess.run([sys.executable, str(RAIZ / "scripts/ragas_oficial.py"), str(salida)], check=True)
        ragas = json.loads(salida.with_name(salida.stem + "_ragas_oficial.json").read_text(encoding="utf-8"))
    total = d["total_automatico"]["obtenidos"] + (ragas["puntos"] if ragas else 0)
    print(f"\nMARK {args.mark} (evaluador oficial, muestra de 50)\n"
          f"  total {round(total, 2)} de {80 if ragas else 50} · cerradas "
          f"{d['cerradas']['aciertos']}/{d['cerradas']['n']} ({d['cerradas']['puntos']}) · citas {d['citas']['puntos']} "
          f"(recall {d['citas']['recall_citas_ponderado']}) · abstención {d['abstencion']['puntos']}"
          + (f" · RAGAS {ragas['puntos']} (juez real, {ragas['n_calificadas']}/35 calificadas)" if ragas else "")
          + f"\n  reporte: {reporte.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
