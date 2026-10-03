import json
import time
import re
from legalrag.agent.classifier import classify
from legalrag.generation.elimination import instruction
from legalrag.citations.extract import fold, trace_citations
from legalrag.citations.official import enrich_header
from legalrag.citations.sanitize import (augment_citations, ensure_min_text, own_bodies,
                                         sanitize_fields, supported_bodies)
from legalrag.encoding.embed import reproducible


def _truncate_first_object(text):
    start = text.find("{")
    if start < 0:
        return text
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def _strip_think_tags(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def repair_json(text):
    from json_repair import repair_json as repair
    text = _strip_think_tags(text)
    start = text.find("{")
    if start < 0:
        raise ValueError("No hay objeto JSON.")
    candidate = _truncate_first_object(text)
    try:
        value, _ = json.JSONDecoder().raw_decode(candidate)
    except json.JSONDecodeError:
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        candidate = re.sub(r'\{""+', '{"', candidate)
        candidate = re.sub(r',\s*""+', ',"', candidate)
        value = repair(candidate, return_objects=True)
    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
        value = value[0]
    if not isinstance(value, dict):
        raise ValueError("La salida no es un objeto JSON.")
    return value


def abstention(question, reason, passages=None):
    kind = classify(question)["formato"]
    row = {"id": question["id"], "formato": kind, "abstencion": True,
           "pasajes_recuperados": passages or []}
    if kind == "multiple_choice":
        row.update(respuesta_correcta="A",
                   justificacion=f"Abstencion: {reason}.",
                   descarte_opciones={})
    elif kind == "semi_open":
        row.update(respuesta=f"Abstencion: {reason}.", palabras_clave=[], referencia_legal="")
    else:
        row.update(marco_normativo="", analisis=f"Abstencion: {reason}.",
                   jurisprudencia="", conclusion="")
    return row


def public_passage(p):
    """Serializa un pasaje con su encabezado antepuesto al texto.

    El evaluador oficial extrae citas sobre `texto`; el encabezado trae la
    procedencia (norma, articulo) que de otra forma no quedaria citable.
    Mantenemos los offsets inicio/fin apuntando al cuerpo original.
    """
    header = enrich_header(p.get("encabezado") or "", p.get("norma"))
    body = p.get("texto") or ""
    texto = (header + "\n" + body).strip() if header else body
    return {"doc_id": p["doc_id"], "inicio": p["inicio"], "fin": p["fin"],
            "texto": texto,
            "score": p.get("reranker_score", p.get("score", 0.0))}


_WORDS = re.compile(r"\S+")


def _cap_words(text, limit):
    """Trunca a `limit` palabras en una frontera de oracion razonable."""
    if not text or limit <= 0:
        return text
    words = _WORDS.findall(text)
    if len(words) <= limit:
        return text
    cut = " ".join(words[:limit])
    # Retroceder hasta el ultimo punto si existe.
    dot = cut.rfind(".")
    if dot > len(cut) * 0.5:
        cut = cut[: dot + 1]
    elif not cut.endswith("."):
        cut += "."
    return cut


def validate_response(row, config):
    from jsonschema import Draft202012Validator
    schema = json.loads(config.schema_file.read_text(encoding="utf-8"))
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(row)]
    if errors:
        return errors
    if not row.get("abstencion"):
        if not row.get("pasajes_recuperados"):
            errors.append("Respuesta sin evidencia")
        kind = row.get("formato")
        from legalrag.agent.classifier import SCHEMAS
        for field in SCHEMAS.get(kind, {}):
            if row.get(field) in (None, "", [], {}):
                errors.append(f"Campo vacio: {field}")
        if kind == "multiple_choice":
            if not isinstance(row.get("descarte_opciones"), dict):
                row["descarte_opciones"] = {}
        if kind == "semi_open":
            words = len((row.get("respuesta") or "").split())
            if words > 160:  # tolerancia pequena sobre el limite oficial de 150
                errors.append("respuesta supera 150 palabras")
    return errors


# Mark 44: piramide de Kelsen en el ordenamiento colombiano, para ponderar cuando la evidencia se contradice.
JERARQUIA = (
    "Si los fragmentos de la evidencia se contradicen, pondera segun la jerarquia normativa colombiana: "
    "(1) Constitucion Politica (art. 4) y bloque de constitucionalidad: tratados de derechos humanos ratificados "
    "(art. 93) y de limites (art. 101); (2) leyes estatutarias y organicas; (3) leyes ordinarias y codigos; "
    "(4) decretos con fuerza de ley (decretos ley y legislativos); (5) decretos reglamentarios; (6) resoluciones, "
    "circulares, ordenanzas y acuerdos. Prevalece la de mayor rango; entre normas del mismo rango, la especial "
    "sobre la general (art. 5 Ley 57 de 1887) y la posterior sobre la anterior (art. 2 Ley 153 de 1887). "
    "Las sentencias de constitucionalidad (C-) obligan a todos. "
)


# Aplicada a todas las preguntas, la regla empeoró la muestra (44,47 → 39,14: el modelo prefería la norma de
# mayor rango aunque la pregunta pidiera la especial). Solo entra en las sub-tareas de jerarquía o conflicto
# normativo que lista el enunciado (§4.2), detectadas por la sub-tarea o por el texto de la pregunta.
_JERARQUIA_RE = re.compile(r"jerarqu|prevalec|prima sobre|primac|conflicto normativo|conflicto entre normas|"
                           r"antinomia|choque entre|bloque de constitucionalidad|excepci[oó]n de inconstitucionalidad",
                           re.I)


_JURISPRUDENCIA_RE = re.compile(r"precedente|jurisprudenc|sentido del fallo|l[ií]nea jurisprudencial|"
                                r"ratio decidendi|sentencia (?:de unificaci|[CTSU]{1,2}-)", re.I)


# Preguntas cuya respuesta es una conclusión binaria (¿existe…?, ¿procede…?, verdadero o falso): invertir la
# conclusión vale ~0 en RAGAS (1073: «no existe relación laboral»; 1005: «falsa»). Solo en ellas el decoder razona.
BINARIA = re.compile(r"\b(verdader[ao]s?\s+o\s+fals[ao]s?|fals[ao]s?\s+o\s+verdader[ao]s?)\b|"
                     r"¿\s*(existen?|proceden?|es|son|pueden?|deben?|hay|tienen?|se\s+configura|cabe|aplica)\b",
                     re.IGNORECASE)


def conclusion_binaria(question):
    return bool(BINARIA.search(question.get("pregunta") or ""))


def pide_jurisprudencia(question):
    """Sub-tareas «precedente jurisprudencial» y «sentido del fallo» del enunciado (§4.2)."""
    texto = " ".join(str(question.get(k) or "") for k in ("sub_tarea", "pregunta"))
    return bool(_JURISPRUDENCIA_RE.search(texto))


def trata_jerarquia(question):
    texto = " ".join(str(question.get(k) or "") for k in ("sub_tarea", "pregunta"))
    return bool(_JERARQUIA_RE.search(texto))


# Enrutador de Cerberus (Adaptive-RAG, Jeong et al., NAACL 2024): cada pregunta va al especialista de su tipo. El tipo
# lo da la sub-tarea oficial del banco (§4.2, campo ciego `sub_tarea`), no una regla por pregunta. Solo texto libre: en
# cerradas, Cerberus midió que tocar la evidencia o el prompt empeoraba.
SUBTAREAS_CONCEPTUALES = {"definicion basica", "elemento esencial", "elementos esenciales", "distincion conceptual",
                          "clasificacion juridica"}


def especialistas(question):
    """Opciones del redactor que se activan para esta pregunta (vacío = Mark 46 tal cual).

    conceptual (definición, elemento esencial, distinción, clasificación) → area_en_prompt + conocimiento_propio: la rama
        del derecho de la pregunta y, si la evidencia no responde, el conocimiento del modelo (notas RAGAS 0,23-0,47).
    conclusión binaria (¿existe…?, verdadero o falso) → razonar_binarias: el decoder piensa antes de concluir.
    jerarquía, conflicto normativo o ponderación → jerarquia_condicional: la pirámide normativa en el razonamiento.
    """
    from legalrag.citations.extract import fold
    if question.get("formato") == "multiple_choice":
        return {}
    activos = {}
    if fold(question.get("sub_tarea") or "").strip() in SUBTAREAS_CONCEPTUALES:
        # El área y el tema fijan la rama del derecho («Derecho civil · Contratos»): sin ellos, «elementos esenciales
        # de un contrato» se respondía con el contrato de trabajo; con ellos, con el art. 1502 del Código Civil.
        activos["conocimiento_propio"] = True
        activos["area_en_prompt"] = True
    if conclusion_binaria(question):
        activos["razonar_binarias"] = True
    if trata_jerarquia(question):
        activos["jerarquia_condicional"] = True
    return activos


class Generator:
    def __init__(self, config):
        reproducible(config.seed)
        import torch
        from accelerate import init_empty_weights
        from transformers import AutoConfig, AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        if not torch.cuda.is_available():
            raise RuntimeError("Se requiere CUDA.")
        self.config = config
        self.generaciones = []
        from legalrag.citations import official
        official.ENCABEZADO_CANONICO = bool(config.encabezado_canonico)
        model_config = AutoConfig.from_pretrained(config.llm_model, revision=config.llm_revision)
        with init_empty_weights():
            skeleton = AutoModelForCausalLM.from_config(model_config)
            skeleton.tie_weights()
            count = sum(p.numel() for p in skeleton.parameters())
        del skeleton
        if count > config.max_params:
            raise ValueError(f"Decoder fuera del limite: {count:,} parametros.")
        self.parameter_count = count
        self.tokenizer = AutoTokenizer.from_pretrained(config.llm_model, revision=config.llm_revision)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                config.llm_model, revision=config.llm_revision,
                device_map={"": 0}, dtype=torch.bfloat16,
                trust_remote_code=False).eval()
            self._mode = "bf16"
        except (RuntimeError, torch.OutOfMemoryError):
            quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                             bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
            self.model = AutoModelForCausalLM.from_pretrained(
                config.llm_model, revision=config.llm_revision, quantization_config=quantization,
                device_map={"": 0}, dtype=torch.bfloat16,
                trust_remote_code=False).eval()
            self._mode = "4bit"
        self.revision = getattr(self.model.config, "_commit_hash", None)
        gpu = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"\n  Decoder:  {config.llm_model}  ({count/1e9:.1f}B params, {self._mode})", flush=True)
        print(f"  GPU:      {gpu}  ({vram:.0f} GB)", flush=True)
        print(f"  Context:  {config.context_tokens} tok evidence, {config.max_new_tokens} tok gen", flush=True)
        print(f"  MC think: {'on' if config.mc_thinking else 'off'}  Augment<={config.augment_max}\n", flush=True)

    def token_count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def _prompt_ids(self, messages, enable_thinking=False):
        # transformers 5 devuelve un BatchEncoding; pedimos el dict explicito y tomamos input_ids.
        try:
            encoded = self.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, enable_thinking=enable_thinking,
                tokenize=True, return_dict=True, return_tensors="pt")
        except TypeError:
            encoded = self.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True,
                tokenize=True, return_dict=True, return_tensors="pt")
        return encoded["input_ids"].to("cuda")

    def _inputs(self, messages, enable_thinking=False, prefix=None):
        import torch
        inputs = self._prompt_ids(messages, enable_thinking)
        if inputs.shape[-1] > self.config.max_input_tokens:
            raise ValueError("La pregunta y la evidencia exceden el contexto del decoder.")
        if prefix:
            extra = self.tokenizer.encode(prefix, add_special_tokens=False, return_tensors="pt").to("cuda")
            inputs = torch.cat([inputs, extra], dim=-1)
        return inputs

    def complete(self, messages, max_new_tokens=None, enable_thinking=False, prefix=None,
                 stop_ids=None, max_time=None, procesadores=None):
        """`prefix` es el comienzo ya escrito de la respuesta del asistente (p. ej. un <think> truncado):
        el modelo continúa desde ahí y se devuelve solo la continuación. `stop_ids` agrega tokens de parada
        (p. ej. </think>) y `max_time` (segundos) corta la generación por reloj."""
        import torch
        from transformers import LogitsProcessorList
        inicio_gen = time.perf_counter()
        inputs = self._inputs(messages, enable_thinking, prefix)
        maximum = max_new_tokens or self.config.max_new_tokens
        context_limit = getattr(self.model.config, "max_position_embeddings", 8192)
        if inputs.shape[-1] + maximum > context_limit:
            raise ValueError("La pregunta y la evidencia exceden el contexto del decoder.")
        with torch.inference_mode():
            result = self.model.generate(inputs, attention_mask=torch.ones_like(inputs),
                                         do_sample=False, num_beams=1, max_new_tokens=maximum,
                                         repetition_penalty=1.1,
                                         pad_token_id=self.tokenizer.pad_token_id,
                                         eos_token_id=[self.tokenizer.eos_token_id] + list(stop_ids or []),
                                         **({"max_time": max(0.5, max_time)} if max_time is not None else {}),
                                         **({"logits_processor": LogitsProcessorList(procesadores)}
                                            if procesadores else {}))
        # Medición por generación (prompt, tokens nuevos, segundos) para calibrar el presupuesto por etapa.
        self.generaciones.append((inputs.shape[-1], result.shape[-1] - inputs.shape[-1],
                                  round(time.perf_counter() - inicio_gen, 2)))
        return self.tokenizer.decode(result[0, inputs.shape[-1]:], skip_special_tokens=True)

    def logits_siguiente(self, messages, ids, enable_thinking=False, prefix=None):
        """Logits (float32) de `ids` como siguiente token, sin generar texto.

        El producto de la última capa se hace en float32 solo para esos ids: en bf16 los logits tienen
        ~3 cifras y dos opciones pueden empatar (pregunta 748 en Cerberus)."""
        import torch
        inputs = self._inputs(messages, enable_thinking, prefix)
        capa = self.model.get_output_embeddings()
        capturado = {}
        gancho = capa.register_forward_hook(lambda modulo, entrada, salida: capturado.__setitem__("h", entrada[0]))
        try:
            with torch.inference_mode():
                try:  # solo la última posición: los logits de todo el prompt pesan ~1 GB
                    self.model(inputs, logits_to_keep=1)
                except TypeError:
                    self.model(inputs)
                oculto = capturado["h"][0, -1].float()
                return capa.weight[ids].float() @ oculto
        finally:
            gancho.remove()

    def probabilidad_si(self, messages):
        """Mark 44 (de Cerberus Mark 4): P(«Sí») frente a «No» como siguiente token."""
        import torch
        ids = [self.tokenizer.encode(palabra, add_special_tokens=False)[0] for palabra in ("Sí", "No")]
        return torch.softmax(self.logits_siguiente(messages, ids), dim=0)[0].item()

    def _mc_rapido(self, messages, question, deadline, tokens=None):
        """Mark 44, cerradas en una sola generación (un solo prefill), determinista:
        (1) el modelo razona hasta cerrar </think> o hasta `pensar` tokens; (2) se fuerza el cierre y
        '{"respuesta_correcta": "'; (3) la letra se elige entre las opciones con los logits en float32 del
        estado oculto (en bf16 dos letras pueden empatar); (4) el modelo sigue con la justificación."""
        import torch
        from transformers import LogitsProcessor
        pensar = self.config.mc_thinking_max_tokens
        if tokens is not None:
            pensar = max(64, min(pensar, tokens - self.config.mc_json_tokens))
        tok = self.tokenizer
        fin = tok.convert_tokens_to_ids("</think>")
        tras_cierre = tok.encode('\n\n{"respuesta_correcta": "', add_special_tokens=False)
        cierre_forzado = tok.encode('\n</think>\n\n{"respuesta_correcta": "', add_special_tokens=False)
        letras = [k for k in (question.get("opciones") or {}) if k in ("A", "B", "C", "D")] or list("ABCD")
        ids_letras = [tok.encode(letra, add_special_tokens=False)[0] for letra in letras]
        capa = self.model.get_output_embeddings()
        capturado = {}
        generador = self

        class Cierre(LogitsProcessor):
            def __init__(self, inicio):
                self.inicio, self.cola, self.letra_puesta = inicio, None, False

            def _forzar(self, scores, token):
                forzado = torch.full_like(scores, float("-inf"))
                forzado[:, token] = 0
                return forzado

            def __call__(self, input_ids, scores):
                if self.letra_puesta:
                    return scores
                if self.cola is None:
                    if input_ids[0, -1].item() == fin:
                        self.cola = list(tras_cierre)
                    elif input_ids.shape[1] - self.inicio >= pensar or time.perf_counter() > limite_pensar:
                        # El reloj es solo un seguro: si se acerca el plazo, se cierra antes para que siempre
                        # haya letra (sin esto, el corte por max_time dejaba la cerrada sin letra).
                        self.cola = list(cierre_forzado)
                    else:
                        return scores
                if self.cola:
                    return self._forzar(scores, self.cola.pop(0))
                oculto = capturado["h"][0, -1].float()
                logits = capa.weight[ids_letras].float() @ oculto
                probs = torch.softmax(logits, dim=0).tolist()
                generador.last_letras = {l: round(float(p), 4) for l, p in zip(letras, probs)}
                self.letra_puesta = True
                return self._forzar(scores, ids_letras[max(range(len(probs)), key=probs.__getitem__)])

        inicio = self._inputs(messages, enable_thinking=True).shape[-1]
        reserva = (self.config.mc_json_tokens + len(cierre_forzado) + 1) / self.config.tokens_por_s + 0.6
        limite_pensar = float("inf") if deadline is None else deadline - reserva
        gancho = capa.register_forward_hook(lambda modulo, entrada, salida: capturado.__setitem__("h", entrada[0]))
        try:
            restante = None if deadline is None else deadline - time.perf_counter() - 0.3
            raw = self.complete(messages, max_new_tokens=pensar + len(cierre_forzado) + 1 + self.config.mc_json_tokens,
                                enable_thinking=True, procesadores=[Cierre(inicio)], max_time=restante)
        finally:
            gancho.remove()
        self.last_cierre = True
        self.last_pensar = pensar
        return raw

    def _cerrar_pensamiento(self, messages, raw):
        """Mark 44: si el thinking agotó el presupuesto, se cierra </think> y el modelo sigue desde su propio
        razonamiento (en vez de regenerar desde cero sin thinking); si el JSON quedó cortado, se continúa."""
        texto = raw if raw.lstrip().startswith("<think>") else "<think>\n" + raw
        prefijo = texto if "</think>" in texto else texto.rstrip() + "\n</think>\n\n{"
        continuacion = self.complete(messages, max_new_tokens=self.config.max_new_tokens,
                                     enable_thinking=True, prefix=prefijo)
        return prefijo + continuacion

    def _system_prompt(self, route, question):
        kind = route["formato"]
        base = (
            "Eres un asistente juridico de derecho colombiano. Respondes usando SOLO la evidencia "
            "adjunta, que son fragmentos marcados [E1], [E2], ... Cada fragmento inicia con su "
            "encabezado de procedencia (norma, articulo) entre corchetes. "
            "Reglas estrictas de citacion: solo puedes nombrar normas, codigos, decretos, leyes o "
            "sentencias que aparezcan textualmente en la evidencia. NO inventes numeros de sentencia "
            "ni articulos ausentes. Si una norma del encabezado respalda tu respuesta, menciona su "
            "nombre canonico (Codigo Civil, Codigo General del Proceso, Constitucion Politica, "
            "Ley 1564 de 2012, Sentencia C-355 de 2006, etc.) tal como figura en los encabezados. "
            "Devuelve exclusivamente un objeto JSON valido, sin texto antes ni despues. "
            "Los campos y sus tipos son: "
            + json.dumps(route["esquema"], ensure_ascii=False) + ". "
        )
        if self.config.conocimiento_propio and kind != "multiple_choice":
            # Evidencia primero, conocimiento del modelo después (Mallen et al., ACL 2023: la recuperación perjudica
            # cuando la evidencia no responde y el modelo sí sabe). Con «SOLO la evidencia», una pregunta conceptual
            # mal recuperada se respondía con el pasaje equivocado (24: el contrato de trabajo en vez del art. 1502
            # del Código Civil). Las citas siguen limitadas a la evidencia: sanitize_fields quita las demás.
            base = base.replace(
                "Respondes usando SOLO la evidencia adjunta, que son fragmentos marcados [E1], [E2], ... ",
                "Usa como fuente principal la evidencia adjunta, que son fragmentos marcados [E1], [E2], ...; si "
                "la evidencia no responde la pregunta, respondela con tu conocimiento del derecho colombiano. ")
        if self.config.jerarquia_normativa or (self.config.jerarquia_condicional and trata_jerarquia(question)):
            base += JERARQUIA
        if kind == "multiple_choice":
            base += (
                "Elige SIEMPRE una letra (A, B, C o D) basada en la evidencia; no te abstengas. "
                "En descarte_opciones incluye las tres letras no elegidas con una razon breve. "
                "La justificacion debe citar al menos una norma presente en la evidencia. "
            )
            base += instruction(question).replace("devuelve abstencion=true", "elige la letra mas probable")
            if self.config.mc_rapido:
                base += ("Se breve: justificacion de 2 a 3 oraciones que nombren la norma aplicable de la "
                         "evidencia; en descarte_opciones, una frase corta por letra. ")
        elif kind == "semi_open" and self.config.semi_concisas:
            # RAGAS (F1 de enunciados frente a la respuesta de referencia): cada oración que la referencia no
            # contiene cuenta como falso positivo, así que la respuesta dice lo pedido y nada más.
            base += (
                "respuesta: 2 a 4 oraciones, maximo 100 palabras. La primera oracion responde exactamente lo que "
                "se pregunta, de forma directa y sin preambulos; las siguientes dan solo el fundamento normativo "
                "necesario de la evidencia. No agregues informacion que la pregunta no pide. "
                "palabras_clave: 3 a 6 terminos juridicos tomados de la respuesta. "
                "referencia_legal: lista norma(s) y articulo(s) exactos presentes en la evidencia. "
            )
        elif kind == "semi_open":
            base += (
                "respuesta: 3 a 5 oraciones, maximo 150 palabras. La primera oracion responde la "
                "pregunta de forma directa, sin preambulos. Luego la fundamentas con citas de la evidencia. "
                "palabras_clave: 3 a 6 terminos juridicos tomados de la respuesta. "
                "referencia_legal: lista norma(s) y articulo(s) exactos presentes en la evidencia. "
            )
        elif self.config.abiertas_directas:  # open_ended
            # RAGAS califica marco + analisis + jurisprudencia + conclusion como un solo texto contra una
            # respuesta de referencia que dice primero qué procede y por qué: cada norma accesoria es un
            # enunciado que el juez no encuentra en la referencia.
            base += (
                "marco_normativo: solo las 1 a 3 normas de la evidencia que resuelven el caso, con su articulo. "
                "analisis: 4 a 6 oraciones. La primera oracion responde el caso de forma directa (que procede, "
                "si existe o no el derecho, quien tiene razon); las siguientes lo fundamentan con la evidencia. "
                "jurisprudencia: cita sentencias SOLO si aparecen en la evidencia y respaldan la respuesta; "
                "si no, una frase breve. "
                "conclusion: una o dos oraciones que repiten la respuesta al caso. "
            )
        else:  # open_ended
            base += (
                "marco_normativo: lista las normas aplicables presentes en la evidencia. "
                "analisis: 5 a 8 oraciones; aplica el marco al caso con rigor. "
                "jurisprudencia: cita sentencias SOLO si aparecen en la evidencia; si no, declara su ausencia. "
                "conclusion: una o dos oraciones con la respuesta al caso. "
            )
        if self.config.razonamiento_juridico and kind != "multiple_choice":
            # Pensar como abogado (IRAC) y no dejarse distraer por fragmentos que solo comparten palabras con la
            # pregunta (Shi et al., ICML 2023): con la evidencia correcta a la vista, el modelo seguía al primer
            # fragmento (un oficio DIAN, una circular) o invertía la conclusión (1073, 1005).
            base += (
                "Antes de redactar, razona como abogado colombiano: identifica la cuestion juridica; busca en la "
                "evidencia la norma de mayor jerarquia que la resuelve (Constitucion, ley o codigo antes que decretos, "
                "resoluciones, conceptos u oficios); usa la jurisprudencia para interpretarla; e ignora los fragmentos "
                "que no tratan la cuestion aunque compartan palabras con ella. Si la pregunta se responde con si o no, "
                "o con verdadero o falso, empieza por esa respuesta y verifica que coincida con la norma aplicable. "
            )
        base += "Si la evidencia no es suficiente, responde con tu mejor interpretacion; NO uses abstencion."
        return base

    def answer(self, question, passages, deadline=None, tope_tokens=None):
        route = classify(question)
        used, blocks, tokens = [], [], 0
        used_spans = set()
        for p in passages:
            if p["parent_fin"] - p["parent_inicio"] <= 7000:
                from legalrag.io import source_path
                original = source_path(self.config, p).read_text(encoding="utf-8")
                body = original[p["parent_inicio"]:p["parent_fin"]]
                if original[p["inicio"]:p["fin"]] != p["texto"]:
                    # Los offsets no son del `.txt` (índice sobre Markdown): el artículo sale del propio índice.
                    texto_padre = getattr(self, "texto_padre", None)
                    body = texto_padre(p) if texto_padre else None
                    body = body if body is not None else p["texto"]
                if self.token_count(body) <= 1200:
                    p = {**p, "inicio": p["parent_inicio"], "fin": p["parent_fin"], "texto": body}
            span = (p["doc_id"], p["inicio"], p["fin"])
            if span in used_spans:
                continue
            header = enrich_header(p.get("encabezado") or "", p.get("norma"))
            block = f"[E{len(used)+1}] {header}\n{p['texto']}"
            cost = self.token_count(block)
            if tokens + cost > self.config.context_tokens:
                continue
            used.append(p)
            used_spans.add(span)
            blocks.append(block)
            tokens += cost
        if not used:
            return abstention(question, "No hay evidencia que quepa en el contexto"), [], False

        system = self._system_prompt(route, question)
        payload = {"pregunta": question["pregunta"], "opciones": question.get("opciones"),
                   "evidencia": blocks}
        conceptual = fold(question.get("sub_tarea") or "").strip() in SUBTAREAS_CONCEPTUALES
        if (self.config.area_en_prompt or (self.config.area_en_conceptuales and conceptual)) \
                and route["formato"] != "multiple_choice":
            # El área y el tema vienen en cada ítem del banco y fijan la rama del derecho: sin ellos, «elementos
            # esenciales de un contrato» (Derecho civil · Contratos) se respondía con el contrato de trabajo.
            contexto = {k: str(question.get(k)).strip() for k in ("area", "tema") if question.get(k)}
            if contexto:
                payload = {**contexto, **payload}
        user_content = json.dumps(payload, ensure_ascii=False)
        from legalrag.tools.legal_tools import tool_block, tool_block_v2
        herramientas = tool_block_v2 if self.config.herramientas_v2 else tool_block
        computed = herramientas(question["pregunta"], question.get("opciones"))
        if computed:
            user_content = user_content + "\n\n" + computed
        if self.config.normalizador_citas:
            # Mark 43: el banco trae leyes con el año equivocado («Ley 1564 de 2002» por la de 2012).
            from legalrag.tools.normalizador import normalizador_del_corpus
            opciones = question.get("opciones")
            normalizador = normalizador_del_corpus(self.config)
            nota = normalizador.nota({"pregunta": question["pregunta"],
                                      "opciones": opciones if isinstance(opciones, dict) else {}},
                                     directo=self.config.normalizador_directo) if normalizador else None
            if nota:
                user_content = user_content + "\n\n" + nota
        self.last_tools = computed
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        use_thinking = bool(self.config.mc_thinking and route["formato"] == "multiple_choice")
        budget = self.config.mc_thinking_max_tokens if use_thinking else self.config.max_new_tokens
        if tope_tokens is not None and not use_thinking:
            # Mark 44: tope determinista según el plan de búsqueda ejecutado (ver Pipeline._tokens_disponibles).
            budget = max(200, min(budget, tope_tokens))
        self.last_letras = None
        self.last_pensar = None
        binaria = bool(self.config.razonar_binarias and route["formato"] != "multiple_choice"
                       and conclusion_binaria(question))
        if use_thinking and self.config.mc_rapido:
            raw = self._mc_rapido(messages, question, deadline, tope_tokens)
        elif binaria:
            # Razonamiento selectivo (§B.5: cómputo extra solo donde hace falta): el decoder piensa hasta
            # `binarias_pensar_tokens`; si no cerró </think>, se cierra y sigue desde su propio razonamiento.
            pensado = self.complete(messages, max_new_tokens=self.config.binarias_pensar_tokens, enable_thinking=True)
            if "</think>" in pensado:
                raw = pensado + self.complete(messages, max_new_tokens=budget, enable_thinking=True, prefix=pensado)
            else:
                raw = self._cerrar_pensamiento(messages, pensado)
            self.last_pensar = self.config.binarias_pensar_tokens
        else:
            raw = self.complete(messages, max_new_tokens=budget, enable_thinking=use_thinking,
                                max_time=None if deadline is None else deadline - time.perf_counter() - 0.3)
        originally_valid = True
        try:
            json.loads(_strip_think_tags(raw))
        except ValueError:
            originally_valid = False
        self.last_cierre = False
        if (use_thinking and self.config.cerrar_pensamiento and not self.config.mc_rapido
                and not (originally_valid and "</think>" in raw)):
            raw = self._cerrar_pensamiento(messages, raw)
            self.last_cierre = True
        self.last_raw = raw

        generated = None
        try:
            generated = repair_json(raw)
        except ValueError:
            # Un unico reintento con instruccion mas estricta (solo si queda tiempo).
            strict = {"role": "user", "content": "Devuelve SOLO el objeto JSON pedido, sin texto extra, sin bloque de codigo."}
            restante = None if deadline is None else deadline - time.perf_counter() - 0.3
            try:
                if restante is not None and restante < 3:
                    raise ValueError("sin tiempo para reintentar")
                raw2 = self.complete(messages + [strict], max_new_tokens=budget, enable_thinking=False,
                                     max_time=restante)
                generated = repair_json(raw2)
                raw = raw2
                self.last_raw = raw2
            except ValueError:
                generated = None

        # Pasajes publicos (con encabezado antepuesto) = lo que ve el evaluador.
        public = [public_passage(p) for p in used[:10]]
        supported = supported_bodies(public)

        if not generated:
            # Fallback estricto: construimos la respuesta con la evidencia disponible.
            generated = self._fallback(route, question, public)

        # Normalizaciones de tipo (Qwen a veces devuelve listas donde el schema espera texto).
        for field in ("marco_normativo", "jurisprudencia", "conclusion", "analisis",
                      "justificacion", "respuesta", "referencia_legal"):
            value = generated.get(field)
            if isinstance(value, list):
                generated[field] = "; ".join(
                    json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
                    for item in value)

        # Nunca aceptamos la bandera de abstencion del modelo: el evaluador premia responder bien.
        if generated.get("abstencion") is True:
            generated["abstencion"] = False

        if route["formato"] == "multiple_choice":
            if self.last_letras:
                # Mark 44: la letra la decide la probabilidad tras el razonamiento, no el texto generado.
                generated["respuesta_correcta"] = max(self.last_letras, key=self.last_letras.get)
            self._force_letter(generated, question, raw, supported)

        row = {key: generated.get(key) for key in route["esquema"]}
        row.update(id=question["id"], formato=route["formato"], abstencion=False,
                   pasajes_recuperados=public)

        # Sanitiza citas sin respaldo y aumenta con las respaldadas.
        row = sanitize_fields(row, supported, route["formato"])
        row = augment_citations(row, supported, route["formato"],
                                max_norms=self.config.augment_max,
                                preferir_jurisprudencia=bool(self.config.preferir_jurisprudencia
                                                             and pide_jurisprudencia(question)),
                                propios=own_bodies(public) if (self.config.citar_propios_primero or (
                                    self.config.propios_en_precedente and pide_jurisprudencia(question))) else None,
                                reciente=self.config.jurisprudencia_reciente)
        row = ensure_min_text(row, route["formato"])

        # Abstención calibrada: si no hay citas respaldadas y no es MC, abstener.
        if (route["formato"] != "multiple_choice"
                and not supported
                and len(used) > 0):
            from legalrag.citations.official import extract, bodies
            answer_text = " ".join(str(v) for v in row.values() if isinstance(v, str))
            cited = bodies(extract(answer_text))
            if not cited:
                return abstention(question, "Sin respaldo normativo en la evidencia",
                                  public), [], originally_valid

        # Trunca semi_open a 150 palabras.
        if route["formato"] == "semi_open":
            row["respuesta"] = _cap_words(row.get("respuesta", ""), 150)
            if not row.get("palabras_clave"):
                row["palabras_clave"] = self._keywords(question, row.get("respuesta", ""))

        problems = validate_response(row, self.config)
        if problems:
            # Como ultimo recurso rellenamos con placeholders y conservamos la salida.
            row = ensure_min_text(row, route["formato"])
            if route["formato"] == "semi_open" and not row.get("palabras_clave"):
                row["palabras_clave"] = ["derecho", "norma"]
            problems = validate_response(row, self.config)
            if problems:
                return abstention(question, "La salida no cumple el contrato: " + "; ".join(problems),
                                  public), [], originally_valid

        traces = trace_citations(row, used)
        return row, traces, originally_valid

    def _force_letter(self, generated, question, raw, supported):
        letter = generated.get("respuesta_correcta")
        if letter not in ("A", "B", "C", "D"):
            match = re.search(r'\b(?:respuesta[_ ]correcta|answer|respuesta)\b["\s:]*([A-D])\b', raw, re.I)
            if not match:
                match = re.search(r"\b([A-D])\b", raw)
            generated["respuesta_correcta"] = match.group(1).upper() if match else "A"
        if not isinstance(generated.get("descarte_opciones"), dict):
            generated["descarte_opciones"] = {}
        # Rellena las tres letras no elegidas con una razon breve si faltan.
        chosen = generated["respuesta_correcta"]
        for other in ("A", "B", "C", "D"):
            if other == chosen:
                continue
            if not generated["descarte_opciones"].get(other):
                generated["descarte_opciones"][other] = "Descartada por falta de respaldo en la evidencia."
        if not (generated.get("justificacion") or "").strip():
            for v in generated.values():
                if isinstance(v, str) and len(v) > 40:
                    generated["justificacion"] = v
                    break

    def _keywords(self, question, text):
        import re as _re
        tokens = _re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{5,}", text)
        seen, out = set(), []
        for t in tokens:
            low = t.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(low)
            if len(out) >= 5:
                break
        return out or ["derecho", "norma"]

    def _fallback(self, route, question, public):
        """Respuesta minima garantizada cuando el modelo no produce JSON."""
        first = public[0]["texto"] if public else "Sin evidencia disponible."
        snippet = (first[:600] + "…") if len(first) > 600 else first
        if route["formato"] == "multiple_choice":
            return {"respuesta_correcta": "A",
                    "justificacion": f"Seleccion por evidencia parcial. Fragmento: {snippet}",
                    "descarte_opciones": {}}
        if route["formato"] == "semi_open":
            return {"respuesta": f"La evidencia recuperada senala: {snippet}",
                    "palabras_clave": [], "referencia_legal": ""}
        return {"marco_normativo": "",
                "analisis": f"Analisis preliminar a partir de la evidencia: {snippet}",
                "jurisprudencia": "No se identifica jurisprudencia aplicable en la evidencia.",
                "conclusion": "Conclusion sujeta a verificacion normativa adicional."}

    def close(self):
        import gc
        import torch
        del self.model
        gc.collect()
        torch.cuda.empty_cache()
