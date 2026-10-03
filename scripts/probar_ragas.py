"""Reproduce el juez RAGAS del evaluador oficial sobre UNA respuesta, mostrando el error real (el evaluador los
silencia y deja el ítem en cero) y lo que devolvió el modelo juez.

    export OPENROUTER_API_KEY=...
    python3 scripts/probar_ragas.py [salidas/mark44.jsonl] [id]
    python3 scripts/probar_ragas.py --n 5        # 5 respuestas en paralelo, como el evaluador (concurrencia)

Usa las mismas constantes de data/oficial/scripts/evaluate.py (modelo, endpoint, max_tokens, reasoning). Hace
unas pocas llamadas al juez (centavos).
"""
import importlib.util
import json
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "data/oficial/scripts"))
spec = importlib.util.spec_from_file_location("ev", RAIZ / "data/oficial/scripts/evaluate.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

args = sys.argv[1:]
n = 1
if "--n" in args:
    n = int(args[args.index("--n") + 1])
    del args[args.index("--n"):args.index("--n") + 2]
salida = Path(args[0]) if args else RAIZ / "salidas/mark44.jsonl"
subs = {r["id"]: r for r in ev.read_jsonl(salida)}
muestra = {r["id"]: r for r in ev.read_jsonl(ev.DATA / "sample_50.jsonl")}
libres = [i for i, r in muestra.items() if r["formato"] != "multiple_choice"]
ids = [int(args[1])] if len(args) > 1 else libres[:n]
qid = ids[0]
print(f"Preguntas {ids} · juez {ev.JUEZ_MODELO} · max_tokens {ev.JUEZ_MAX_TOKENS} · reasoning {ev.JUEZ_REASONING}\n")

from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler

llave = ev.api_key_juez(ev.JUEZ_BASE_URL)
crudas = []


class Registro(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        for generaciones in response.generations:
            for g in generaciones:
                mensaje = getattr(g, "message", None)
                crudas.append({"texto": g.text,
                               "metadatos": getattr(mensaje, "response_metadata", None),
                               "extra": getattr(mensaje, "additional_kwargs", None)})


chat = ChatOpenAI(model=ev.JUEZ_MODELO, base_url=ev.JUEZ_BASE_URL, api_key=llave, temperature=0,
                  max_tokens=ev.JUEZ_MAX_TOKENS, extra_body={"reasoning": ev.JUEZ_REASONING},
                  callbacks=[Registro()])

print("[1] Llamada directa por LangChain (como la hace RAGAS):")
r = chat.invoke("Devuelve solo este JSON, sin texto adicional: {\"ok\": true}")
print("    content:", repr(r.content)[:400])
print("    finish_reason:", (r.response_metadata or {}).get("finish_reason"))

print("\n[2] RAGAS answer_correctness con raise_exceptions=True:")
from datasets import Dataset
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate as ragas_evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_correctness

ds = Dataset.from_dict({"question": [muestra[i]["pregunta"] for i in ids],
                        "answer": [ev.ragas_text(subs[i]) for i in ids],
                        "ground_truth": [muestra[i]["respuesta_esperada"] for i in ids]})
import time
inicio = time.time()
try:
    res = ragas_evaluate(ds, metrics=[answer_correctness], llm=LangchainLLMWrapper(chat),
                         embeddings=LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=ev.JUEZ_ENCODER)),
                         raise_exceptions=True, show_progress=False)
    print("    answer_correctness:", res.to_pandas()["answer_correctness"].tolist())
    print(f"    tiempo: {time.time() - inicio:.0f} s")
except Exception:
    print(f"    ERROR (a los {time.time() - inicio:.0f} s):")
    print("    " + traceback.format_exc()[-2500:].replace("\n", "\n    "))

print(f"\n[3] Lo que devolvió el juez en cada llamada ({len(crudas)}):")
for i, c in enumerate(crudas, 1):
    meta = c["metadatos"] or {}
    print(f"  --- llamada {i} · finish_reason={meta.get('finish_reason')} · "
          f"tokens={(meta.get('token_usage') or {}).get('completion_tokens')}")
    print("  " + json.dumps(c["texto"], ensure_ascii=False)[:300 if n > 1 else 700])
    if c["extra"]:
        print("  additional_kwargs:", json.dumps(c["extra"], ensure_ascii=False, default=str)[:300])
