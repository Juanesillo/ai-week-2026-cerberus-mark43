"""Techo de citas por configuración (sin generar): fracción de normas de referencia presentes en los 10 pasajes
entregados. Uso, desde la raíz: python3 scripts/techo_citas.py "" "consulta_con_tema=1"  (cada argumento = opciones sobre Mark 44)"""
import sys, json, time; sys.path.insert(0, "src"); sys.path.insert(0, "data/oficial/scripts")
from legalrag.silencio import silenciar; silenciar()
from dataclasses import replace
from legalrag.config import CONFIG
from main import MARKS
from legalrag.pipeline import Pipeline
from legalrag.generation.generator import public_passage
import citations
qs = [json.loads(l) for l in open("data/oficial/data/sample_50.jsonl")]
class Corte(Exception): pass
pl = None
for arg in sys.argv[1:]:
    extra = dict(kv.split("=") for kv in arg.split(",")) if arg else {}
    conv = {k: (v == "1") if isinstance(getattr(CONFIG, k), bool) else type(getattr(CONFIG, k))(v) for k, v in extra.items()}
    cfg = replace(CONFIG, **{**MARKS[44], **conv})
    if pl is None: pl = Pipeline(cfg)
    pl.config = cfg; pl.retriever.config = cfg; pl.generator.config = cfg
    if pl.reranker: pl.reranker.config = cfg
    from legalrag.citations import official; official.ENCABEZADO_CANONICO = cfg.encabezado_canonico
    def capturar(question, selected, *a, **k): raise Corte(selected)
    pl.generator.answer = capturar
    tot = hit = 0; por = {}; t0 = time.time()
    for q in qs:
        ref = citations.bodies(citations.extract(q.get("legal_basis") or ""))
        try: pl.answer(q); sel = []
        except Corte as c: sel = c.args[0]
        got = set()
        for p in sel[:10]: got |= citations.bodies(citations.extract(public_passage(p)["texto"]))
        h = len(ref & got); tot += len(ref); hit += h
        if ref: por[q["id"]] = f"{h}/{len(ref)}"
    print(f"[{arg or 'mark43'}] techo citas {hit}/{tot} = {hit/tot:.3f}  ({time.time()-t0:.0f}s)")
    print("   fallas:", {i: v for i, v in por.items() if v.split('/')[0] != v.split('/')[1]}, flush=True)
