"""RAGAS del evaluador oficial con Qwen3-8B local como juez: gratis y mucho más fiel que el RAGAS≈ con NLI.

    python3 scripts/ragas_qwen.py salidas/mark45.jsonl [otra.jsonl ...]

Corre data/oficial/scripts/evaluate.py SIN modificarlo: mismos prompts de RAGAS (descomposición en enunciados y
clasificación TP/FP/FN), mismo parseo, misma fórmula (0,75 · F1 + 0,25 · similitud) y mismo encoder
(intfloat/multilingual-e5-large). Lo único que cambia es el modelo juez: en vez de z-ai/glm-5.3-flash en OpenRouter,
Qwen3-8B (sin thinking, decodificación voraz) en la GPU. No hace ninguna llamada a la red ni usa la llave.

Sirve para comparar variantes entre sí; la cifra oficial la da el juez real (scripts/ragas_oficial.py).
Caché por (pregunta, respuesta, esperada) en salidas/ragas_qwen_cache.json. Reporte: salidas/<nombre>_ragasqwen.json.
"""
import hashlib
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
OFICIAL = RAIZ / "data/oficial/scripts"
CACHE = RAIZ / "salidas/ragas_qwen_cache.json"
sys.path.insert(0, str(RAIZ / "src"))


def clave(pregunta, respuesta, esperada):
    return hashlib.sha256(json.dumps([pregunta, respuesta, esperada], ensure_ascii=False).encode()).hexdigest()


def juez_local():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from legalrag.config import CONFIG

    tok = AutoTokenizer.from_pretrained(CONFIG.llm_model, revision=CONFIG.llm_revision)
    modelo = AutoModelForCausalLM.from_pretrained(CONFIG.llm_model, revision=CONFIG.llm_revision,
                                                  dtype=torch.bfloat16, device_map="cuda").eval()
    candado = threading.Lock()
    roles = {"human": "user", "ai": "assistant", "system": "system"}

    class QwenJuez(BaseChatModel):
        temperature: float = 0.0
        n: int = 1

        @property
        def _llm_type(self):
            return "qwen3-juez-local"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            chat = [{"role": roles.get(m.type, "user"), "content": m.content} for m in messages]
            entrada = tok.apply_chat_template(chat, add_generation_prompt=True, enable_thinking=False,
                                              return_dict=True, return_tensors="pt").to("cuda")
            with candado, torch.inference_mode():
                salida = modelo.generate(**entrada, max_new_tokens=2048, do_sample=False,
                                         pad_token_id=tok.eos_token_id)
            texto = tok.decode(salida[0, entrada["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=texto))])

    return QwenJuez()


def main():
    salidas = [Path(a).resolve() for a in sys.argv[1:]]
    if not salidas:
        sys.exit(__doc__)
    import pandas as pd
    import ragas
    import langchain_openai
    from datasets import Dataset
    from ragas.run_config import RunConfig

    juez = juez_local()
    langchain_openai.ChatOpenAI = lambda **kw: juez  # el evaluador lo importa dentro de la función
    os.environ["OPENROUTER_API_KEY"] = "juez-local-sin-red"  # solo para pasar api_key_juez; no se usa
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    original = ragas.evaluate

    class Resultado:
        def __init__(self, valores):
            self.valores = valores

        def to_pandas(self):
            return pd.DataFrame({"answer_correctness": self.valores})

    def evaluar(dataset, metrics, llm, embeddings, **kwargs):
        filas = dataset.to_dict()
        claves = [clave(q, a, g) for q, a, g in zip(filas["question"], filas["answer"], filas["ground_truth"])]
        faltan = [i for i, k in enumerate(claves) if k not in cache]
        print(f"  juez local: {len(claves) - len(faltan)} desde caché, {len(faltan)} a calificar", flush=True)
        for n, i in enumerate(faltan, 1):  # una a una: cada calificación queda en caché al terminar
            sub = Dataset.from_dict({c: [filas[c][i]] for c in ("question", "answer", "ground_truth")})
            res = original(sub, metrics=metrics, llm=llm, embeddings=embeddings, raise_exceptions=False,
                           show_progress=False, run_config=RunConfig(max_workers=1, timeout=900, max_retries=2))
            valor = res.to_pandas()["answer_correctness"].tolist()[0]
            if valor == valor:
                cache[claves[i]] = float(valor)
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
            print(f"    {n}/{len(faltan)}: {valor:.3f}", flush=True)
        return Resultado([cache.get(k, float("nan")) for k in claves])

    ragas.evaluate = evaluar
    sys.path.insert(0, str(OFICIAL))
    spec = importlib.util.spec_from_file_location("evaluador_oficial", OFICIAL / "evaluate.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    for salida in salidas:
        reporte = salida.with_name(salida.stem + "_ragasqwen.json")
        sys.argv = ["evaluate.py", "--submission", str(salida), "--split", "sample", "--ragas", "--out", str(reporte)]
        ev.main()
        r = json.loads(reporte.read_text(encoding="utf-8"))["correccion_ragas"]
        print(f"{salida.name}: RAGAS-Qwen {r.get('puntos')} de 30 (correctness {r.get('correctness')}, "
              f"fallidos {r.get('n_fallidos', 0)} de {r.get('n_respondidos')})", flush=True)


if __name__ == "__main__":
    main()
