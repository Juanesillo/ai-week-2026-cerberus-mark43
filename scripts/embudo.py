"""Dónde se pierde la norma de referencia en la recuperación, pregunta por pregunta (sin generar).

    python3 scripts/embudo.py                      # índice de la raíz (LEGALRAG_ROOT para otro)
    python3 scripts/embudo.py "top_k_retrieval=100"

Para cada pregunta con legal_basis mide qué normas de referencia aparecen:
  cand  en algún conjunto de candidatos que llega al reranker (BM25 + vectores, todos los rescates)
  rank  en los primeros 10 del ranking del reranker
  final en los 10 pasajes que recibe el generador
Si la norma no está en «cand», el problema es la primera etapa; si está en cand pero no en final, el reranker o la
selección. Cada argumento es un conjunto de opciones sobre Mark 44 (como scripts/techo_citas.py).
"""
import json
import sys
import time
sys.path.insert(0, "src")
sys.path.insert(0, "data/oficial/scripts")
from legalrag.silencio import silenciar
silenciar()
from dataclasses import replace
from legalrag.config import CONFIG, MARKS
from legalrag.pipeline import Pipeline
from legalrag.generation.generator import public_passage
import citations

qs = [json.loads(l) for l in open("data/oficial/data/sample_50.jsonl", encoding="utf-8-sig") if l.strip()]


class Corte(Exception):
    pass


def cuerpos(pasajes):
    out = set()
    for p in pasajes:
        out |= citations.bodies(citations.extract(public_passage(p)["texto"]))
    return out


pl = None
for arg in sys.argv[1:] or [""]:
    extra = dict(kv.split("=") for kv in arg.split(",")) if arg else {}
    conv = {k: (v == "1") if isinstance(getattr(CONFIG, k), bool) else type(getattr(CONFIG, k))(v)
            for k, v in extra.items()}
    cfg = replace(CONFIG, **{**MARKS[44], **conv})
    if pl is None:
        pl = Pipeline(cfg)
        rank_original = pl._rank
    pl.config = cfg; pl.retriever.config = cfg; pl.generator.config = cfg
    if pl.reranker:
        pl.reranker.config = cfg
    from legalrag.citations import official
    official.ENCABEZADO_CANONICO = cfg.encabezado_canonico
    visto = {}

    def rank(question, candidates):
        ranked = rank_original(question, candidates)
        visto["cand"] |= cuerpos(candidates)
        visto["rank"] |= cuerpos(ranked[:10])
        return ranked

    def capturar(question, selected, *a, **k):
        raise Corte(selected)

    pl._rank = rank
    pl.generator.answer = capturar
    tot = {"ref": 0, "cand": 0, "rank": 0, "final": 0}
    filas = []
    t0 = time.time()
    for q in qs:
        ref = citations.bodies(citations.extract(q.get("legal_basis") or ""))
        if not ref:
            continue
        visto.update(cand=set(), rank=set())
        try:
            pl.answer(q)
            sel = []
        except Corte as c:
            sel = c.args[0]
        final = cuerpos(sel[:10])
        n = {"cand": len(ref & visto["cand"]), "rank": len(ref & visto["rank"]), "final": len(ref & final)}
        tot["ref"] += len(ref)
        for k in n:
            tot[k] += n[k]
        if n["final"] < len(ref):
            faltan = sorted(ref - final)
            filas.append(f"   {q['id']:>5} ref {len(ref)} · cand {n['cand']} · rank {n['rank']} · final {n['final']} "
                         f"| faltan: {'; '.join(map(str, faltan))[:110]}")
    r = tot["ref"]
    print(f"[{arg or 'mark44'}] normas de referencia {r} · en candidatos {tot['cand']} ({tot['cand']/r:.3f}) · "
          f"en top-10 del reranker {tot['rank']} ({tot['rank']/r:.3f}) · en los 10 finales {tot['final']} "
          f"({tot['final']/r:.3f})  ({time.time()-t0:.0f}s)", flush=True)
    print("\n".join(filas), flush=True)
