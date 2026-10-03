from dataclasses import replace
import json
import hashlib
import os
import re
import time
from legalrag.agent.classifier import blind_question, classify
from legalrag.agent.filter import scope
from legalrag.citations.extract import trace_citations
from legalrag.generation.generator import Generator, abstention, validate_response, public_passage
from legalrag.retrieval.kelsen import nivel, normativo
from legalrag.io import records, write_json, dump_line, sha256, now
from legalrag.retrieval.dense import Retriever
from legalrag.retrieval.reranker import Reranker
from legalrag.retrieval.hyde import expand


# Codigo canonico por area del banco. Cuando la pregunta no cita la norma, el
# nombre del codigo entra como parte de la consulta de recuperacion.
_AREA_HINTS = {
    "derecho constitucional": "Constitucion Politica",
    "derecho administrativo": "CPACA Ley 1437 de 2011 Ley 80 de 1993 Ley 1150 de 2007 contratacion estatal",
    "derecho penal": "Codigo Penal Ley 599 de 2000",
    "derecho procesal": "Codigo General del Proceso Ley 1564 de 2012",
    "derecho comercial y sociedades": "Codigo de Comercio Decreto 410 de 1971",
    "derecho civil": "Codigo Civil",
    "derecho de familia": "Codigo de la Infancia y la Adolescencia Ley 1098 de 2006 Codigo Civil",
    "derecho tributario": "Estatuto Tributario Decreto 624 de 1989",
    "derecho laboral": "Codigo Sustantivo del Trabajo Ley 1562 de 2012",
    "derecho de los mercados [competencia, consumidor, datos personales y propiedad intelectual]":
        "Estatuto del Consumidor Ley 1480 de 2011 Ley 1581 de 2012",
}


def _area_hint(area):
    if not area:
        return ""
    key = area.strip().lower()
    return _AREA_HINTS.get(key, "")


_NO_FIGURA = re.compile(r"\b(ninguna|todas|anteriores)\b|\d|\([a-d]\)", re.IGNORECASE)


def es_figura(opcion):
    """Opción de una cerrada que nombra una figura jurídica («Falsa motivación», «Acción reivindicatoria»): hasta 6
    palabras, sin cifras ni fórmulas de cierre («Ninguna de las anteriores», «(a) y (b)») y con alguna palabra de 6
    letras o más, lo que deja fuera plazos y cantidades («Dos años»)."""
    palabras = str(opcion).split()
    return (0 < len(palabras) <= 6 and not _NO_FIGURA.search(str(opcion))
            and any(len(p.strip(".,;:()")) >= 6 for p in palabras))


class Pipeline:
    def __init__(self, config):
        self.config = config
        self.retriever = Retriever(config)
        self.reranker = Reranker(config) if config.use_reranker else None
        self.generator = Generator(config)
        self.generator.texto_padre = self.retriever.texto_padre
        if config.presupuesto_s or config.seguridad_s:
            self._calentar()

    # Mark 44: costo fijo (s) de cada etapa de búsqueda, medido en la RTX 4090 con el índice de 1 M de
    # fragmentos. El tope de tokens se calcula con el plan ejecutado y no con el reloj, para que la misma
    # pregunta dé siempre la misma respuesta; el reloj (max_time) queda solo como red de seguridad.
    COSTO_ETAPA = {"base": 2.6, "complementario": 0.8, "multi_query": 6.5, "iterativo": 4.0, "insuficiente": 0.4,
                   "reserva_nombradas": 0.4}
    MARGEN_S = 1.6  # prefill del prompt (~6 k tokens) + posproceso

    def _tokens_disponibles(self, rescates):
        costo = self.COSTO_ETAPA["base"] + sum(self.COSTO_ETAPA.get(r, 0) for r in rescates)
        return int((self.config.presupuesto_s - costo - self.MARGEN_S) * self.config.tokens_por_s)

    def _calentar(self):
        """Mark 44: con plazo por pregunta, la primera no puede pagar el arranque en frío (índices desde disco,
        kernels de CUDA): se cargan los dos índices y se hace una búsqueda, un rerank y una generación corta."""
        for tier in ("complementario", "nucleo"):
            if (self.config.index_dir / f"{tier}.faiss").exists():
                self.retriever._load(tier)
        pasajes = self.retriever.search("calentamiento contrato de arrendamiento")
        if self.reranker and pasajes:
            self.reranker.rank("calentamiento", pasajes[:4])
        self.generator.complete([{"role": "user", "content": "Responde OK."}], max_new_tokens=4)

    def _rank(self, question, candidates):
        unique = {p["chunk_id"]: p for p in candidates}
        candidates = list(unique.values())
        if self.reranker:
            ranked = self.reranker.rank(question, candidates)
        else:
            ranked = sorted(candidates, key=lambda p: (-(p.get("dense_score") or -1), p["chunk_id"]))[
                :self.config.top_k_evidence]
        return self._diversify(ranked, candidates)

    def _diversify(self, ranked, pool):
        """Garantiza >=3 estatutos en el top-k y los coloca al frente.

        El modelo responde con mayor atencion a los primeros pasajes del contexto;
        anteponer los estatutos ayuda a elegir la letra correcta en MC donde la
        norma aplicable es un codigo y las sentencias son solo doctrina derivada.
        """
        k = self.config.top_k_evidence
        if not ranked:
            return ranked
        # Orden jurídico de la evidencia: en todas las preguntas (kelsen_diversificar) o solo en texto libre
        # (orden_juridico_libre): en cerradas cambiaba la letra (647: B → D), en texto libre subía RAGAS.
        orden_juridico = self.config.kelsen_diversificar or (
            self.config.orden_juridico_libre and getattr(self, "_formato", None) != "multiple_choice")

        def is_sentencia(p):
            if orden_juridico:
                # Solo las fuentes formales cuentan como estatuto; los oficios, conceptos y circulares no.
                return not normativo(p)
            norma = (p.get("norma") or "").lower()
            doc = (p.get("doc_id") or "").lower()
            return norma.startswith("sentencia") or doc.startswith("sentencia")
        if self.config.max_por_documento:
            # Diversidad por documento (MMR en su forma más simple, Carbonell y Goldstein 1998): como mucho N
            # fragmentos de un mismo documento entre los k; el resto del ranking llena los cupos. Sin esto, tres
            # fragmentos de un mismo oficio DIAN ocupaban 3 de 10 cupos y la Constitución quedaba fuera (1073).
            from collections import Counter
            por_doc, depurado, resto = Counter(), [], []
            for p in ranked:
                if por_doc[p["doc_id"]] < self.config.max_por_documento:
                    por_doc[p["doc_id"]] += 1
                    depurado.append(p)
                else:
                    resto.append(p)
            ranked = depurado + resto
        kept = list(ranked[:k])
        statutes_in_top = sum(1 for p in kept if not is_sentencia(p))
        # Si faltan estatutos en el top, trae mas desde el resto del ranking.
        if statutes_in_top < 3:
            extras = [p for p in ranked[k:] if not is_sentencia(p)]
            if not extras:
                seen = {p["chunk_id"] for p in kept}
                extras = [p for p in pool if not is_sentencia(p) and p["chunk_id"] not in seen]
            needed = min(len(extras), max(0, 3 - statutes_in_top))
            # Reemplaza desde el final las sentencias por los estatutos nuevos.
            indices = [i for i, p in enumerate(kept) if is_sentencia(p)][::-1]
            for extra, idx in zip(extras[:needed], indices):
                kept[idx] = extra
        # Reordena: estatutos primero (preservando su orden del reranker), despues sentencias.
        statutes = [p for p in kept if not is_sentencia(p)]
        if orden_juridico:
            statutes.sort(key=nivel)  # estable: dentro de cada nivel, el orden del reranker
        sentencias = [p for p in kept if is_sentencia(p)]
        return statutes + sentencias

    def _fundamentar_opciones(self, question, selected, diagnostics):
        """Cerberus, abogado de las opciones: en una cerrada con evidencia débil cuyas opciones nombran figuras
        jurídicas, cada figura se busca por sí sola (una consulta por opción, como el solucionador de recuperación de
        Clark et al., AAAI 2016) y el reranker elige, frente a la pregunta, el pasaje que mejor la explica. Esos pasajes
        ocupan los últimos cupos de la evidencia: la letra se decide contrastando qué es cada figura, no por el pasaje
        más parecido al relato (748: la consulta previa tapaba la doctrina de la falsa motivación)."""
        figuras = {letra: str(texto).strip().rstrip(".") for letra, texto in question["opciones"].items()
                   if es_figura(texto)}
        if len(figuras) < 2:
            return selected
        inicio = time.perf_counter()
        k = self.config.top_k_evidence
        vistos = {p["chunk_id"] for p in selected[:k]}
        definiciones = {}
        for (letra, figura), hallados in zip(figuras.items(), self.retriever.search_many(list(figuras.values()))):
            hallados = [p for p in hallados if p["chunk_id"] not in vistos][:15]
            if self.reranker and hallados:
                hallados = self.reranker.rank(f"{figura}. {question['pregunta']}", hallados)
            if hallados and hallados[0].get("reranker_score", 0) >= self.config.umbral_opciones:
                definiciones[letra] = hallados[0]
                vistos.add(hallados[0]["chunk_id"])
        diagnostics["tiempo_opciones_s"] = round(time.perf_counter() - inicio, 2)
        if not definiciones:
            return selected
        diagnostics["rescate"].append("opciones")
        diagnostics["opciones_fundamentadas"] = {letra: p["chunk_id"] for letra, p in definiciones.items()}
        return selected[:k - len(definiciones)] + list(definiciones.values())

    def _reservar_nombradas(self, question, rank_query, selected, diagnostics):
        """Mark 44 (de Cerberus, «reservar_nombradas»): si la pregunta nombra una norma (no las opciones), sus 2
        mejores fragmentos entran al frente de la evidencia. Sin esto el reranker puede dejarla fuera aunque la
        pregunta la cite (pregunta 272: Ley 1116 de 2006 nombrada y ausente del top-10). Solo en texto libre:
        en cerradas, Cerberus midió que los ajustes de evidencia empeoraban."""
        from legalrag.citations.extract import extract_references
        normas = list(dict.fromkeys(r.norma for r in extract_references(question["pregunta"])))[:2]
        # Mark 44 (de Cerberus, «reservar_expansion»): las normas que nombra el reformulador también pueden entrar,
        # pero solo si el reranker confirma que su mejor fragmento es pertinente a la pregunta. El reformulador a
        # veces nombra leyes que no aplican; el umbral las deja fuera (pregunta 679: nombra la Ley 1581 de 2012,
        # que es la aplicable, junto con las Leyes 1098 de 2006 y 1257 de 2008, que no lo son).
        sugeridas = []
        if self.config.reservar_reformulador and diagnostics.get("consulta_iterativa"):
            sugeridas = [n for n in dict.fromkeys(r.norma for r in extract_references(diagnostics["consulta_iterativa"]))
                         if n not in normas][:3]
        reservados = []
        confirmadas = []
        for norma in normas + sugeridas:
            propios = [p for p in selected if p.get("norma") == norma]
            if len(propios) >= 2:
                continue
            hallados = self.retriever.search_norma(rank_query, norma)
            if self.reranker and hallados:
                hallados = self.reranker.rank(rank_query, hallados)
            if norma in sugeridas:
                if not hallados or hallados[0].get("reranker_score", 0) < self.config.umbral_reformulador:
                    continue
                confirmadas.append(norma)
            vistos = {p["chunk_id"] for p in selected + reservados}
            reservados += [p for p in hallados if p["chunk_id"] not in vistos][:2 - len(propios)]
        if confirmadas:
            diagnostics["normas_reformulador"] = confirmadas
        if not reservados:
            return selected
        diagnostics["rescate"].append("reserva_nombradas")
        diagnostics["reservados"] = [p["chunk_id"] for p in reservados]
        return (reservados + selected)[:self.config.top_k_evidence]

    def _weak(self, passages):
        if not passages:
            return True
        if self.reranker:
            return passages[0].get("reranker_score", 0) < self.config.min_reranker_score
        return False

    def answer(self, supplied):
        question = blind_question(supplied)
        question["formato"] = classify(question)["formato"]
        started = time.perf_counter()
        # Mark 44: plazo por pregunta. Los rescates de búsqueda solo corren si queda tiempo para generar.
        # El enunciado exige determinismo (§3.1) y que la verificación en vivo reproduzca normas y pasajes (§7):
        # ninguna decisión depende del reloj. `seguridad_s` solo corta una generación desbocada (nunca en uso
        # normal); los 22 s del enunciado son un promedio sobre las 992 preguntas, no un límite por pregunta.
        deadline = started + self.config.seguridad_s if self.config.seguridad_s else None

        def hay_tiempo():
            return True

        self.generator.generaciones = []
        route = classify(question)
        scope_result = scope(question)
        diagnostics = {"ruta": route["formato"], "alcance": scope_result, "rescate": [], "citas": []}
        self._formato = route["formato"]
        if self.reranker is not None:
            # Materia de la pregunta para el criterio de especialidad (kelsen_especial).
            from legalrag.retrieval.kelsen import area_de_pregunta
            self.reranker.area_pregunta = area_de_pregunta(question.get("area"))
        # Enrutador de Cerberus: el redactor de esta pregunta usa los especialistas de su sub-tarea.
        activos = {}
        if self.config.enrutador:
            from legalrag.generation.generator import especialistas
            activos = especialistas(question)
            if activos:
                diagnostics["especialistas"] = sorted(activos)
        self.generator.config = replace(self.config, **activos) if activos else self.config
        if scope_result["fuera_de_alcance"]:
            response = abstention(question, "El área declarada está fuera del alcance del banco")
            candidates = []
        else:
            hypothetical = None
            if self.config.use_hyde and route["compleja"]:
                hypothetical = expand(question["pregunta"], self.generator)
                diagnostics["rescate"].append("hyde")
                diagnostics["consulta_hipotetica"] = hypothetical
            # Para MC enriquecemos la consulta al reranker con las opciones.
            rank_query = question["pregunta"]
            if question.get("opciones"):
                opc = question["opciones"]
                if isinstance(opc, dict):
                    rank_query += " Opciones: " + " ".join(f"{k}) {v}" for k, v in opc.items())
                elif isinstance(opc, list):
                    rank_query += " Opciones: " + " ".join(str(v) for v in opc)
            # El codigo canonico del area se agrega a la consulta de recuperacion:
            # resuelve preguntas donde la norma nunca aparece explicita en la pregunta.
            area_hint = _area_hint(question.get("area"))
            retrieval_query = rank_query + (" " + area_hint if area_hint else "")
            tema = (question.get("tema") or "").strip()
            if tema and self.config.consulta_con_tema:
                # Mark 44: el «tema» del banco ciego nombra la figura (p. ej. «Acciones públicas», «habeas data»)
                # que la pregunta, narrada como caso, no menciona.
                retrieval_query += " " + tema
                if self.config.tema_en_reranker:
                    rank_query += " Tema: " + tema
            candidates = self.retriever.search(retrieval_query, expanded=hypothetical)
            diagnostics["t_busqueda_s"] = round(time.perf_counter() - started, 2)
            selected = self._rank(rank_query, candidates)
            diagnostics["t_rerank_s"] = round(time.perf_counter() - started, 2)
            if self._weak(selected) and hay_tiempo():
                diagnostics["rescate"].append("complementario")
                candidates += self.retriever.search(retrieval_query, tier="complementario", expanded=hypothetical)
                selected = self._rank(rank_query, candidates)
            debil = bool(selected) and selected[0].get("reranker_score", 1.0) < self.config.multi_query_threshold
            if self.config.suficiencia and selected and not debil and hay_tiempo():
                # Mark 44: además del puntaje del reranker, el decoder juzga si los primeros pasajes bastan.
                from legalrag.retrieval.suficiencia import suficiencia
                inicio = time.perf_counter()
                p_si = suficiencia(question, selected[:5], self.generator)
                diagnostics["suficiencia"] = round(p_si, 4)
                diagnostics["tiempo_suficiencia_s"] = round(time.perf_counter() - inicio, 2)
                if p_si < self.config.umbral_suficiencia:
                    debil = True
                    diagnostics["rescate"].append("insuficiente")
            debil = debil and hay_tiempo()
            if self.config.reformulador_iterativo and debil:
                from legalrag.retrieval.suficiencia import reformular
                inicio = time.perf_counter()
                texto = reformular(question, selected[:5], self.generator)
                if texto:
                    diagnostics["rescate"].append("iterativo")
                    diagnostics["consulta_iterativa"] = texto
                    candidates += self.retriever.search(texto + (" " + area_hint if area_hint else ""), expanded=None)
                    selected = self._rank(rank_query, candidates)
                diagnostics["tiempo_iterativo_s"] = round(time.perf_counter() - inicio, 2)
            if self.config.multi_query and debil and hay_tiempo():
                from legalrag.retrieval.multi_query import decompose
                sub_queries = decompose(question["pregunta"], self.generator)
                if sub_queries:
                    diagnostics["rescate"].append("multi_query")
                    diagnostics["sub_queries"] = sub_queries
                    pista = (" " + area_hint) if area_hint and not self.config.subconsultas_sin_pista else ""
                    for hits in self.retriever.search_many([sq + pista for sq in sub_queries],
                                                           paralelo=self.config.subconsultas_sin_pista):
                        candidates += hits
                    selected = self._rank(rank_query, candidates)
            if (self.config.mc_opciones and debil and route["formato"] == "multiple_choice" and selected
                    and isinstance(question.get("opciones"), dict)):
                selected = self._fundamentar_opciones(question, selected, diagnostics)
            if self.config.agente_figuras and debil and route["formato"] != "multiple_choice" and selected:
                # Agente de figuras (Cerberus): el decoder nombra la figura del caso y el corpus dice qué estatuto la
                # regula; su mejor artículo entra a la evidencia solo si el reranker lo confirma frente a la pregunta
                # y la figura. Solo con evidencia débil (§B.5) y en texto libre (en cerradas, tocar la evidencia
                # empeoraba).
                from legalrag.retrieval.suficiencia import figuras
                inicio = time.perf_counter()
                halladas = figuras(question, self.generator)
                diagnostics["figuras"] = halladas
                k = self.config.top_k_evidence
                reservados = []
                for figura in halladas:
                    norma = self.retriever.estatuto_de_figura(figura)
                    if not norma or any(p.get("norma") == norma for p in selected[:k] + reservados):
                        continue
                    consulta = rank_query + " " + figura
                    hallados = self.retriever.search_norma(consulta, norma)
                    if self.reranker and hallados:
                        hallados = self.reranker.rank(consulta, hallados)
                    if hallados and hallados[0].get("reranker_score", 0) >= self.config.umbral_figuras:
                        reservados.append(hallados[0])
                        diagnostics.setdefault("estatutos_figuras", []).append(norma)
                if reservados:
                    diagnostics["rescate"].append("figuras")
                    vistos = {p["chunk_id"] for p in reservados}
                    selected = (reservados + [p for p in selected if p["chunk_id"] not in vistos])[:k]
                diagnostics["tiempo_figuras_s"] = round(time.perf_counter() - inicio, 2)
            if ((self.config.reservar_nombradas or self.config.reservar_reformulador)
                    and route["formato"] != "multiple_choice" and selected):
                selected = self._reservar_nombradas(question, rank_query, selected, diagnostics)
            diagnostics["t_recuperacion_s"] = round(time.perf_counter() - started, 2)
            diagnostics["evidencia_recuperada"] = selected
            self.retriever.verify_sources(selected)
            diagnostics["top3_score"] = sum(p.get("reranker_score", p.get("dense_score") or 0)
                                           for p in selected[:3]) / max(1, min(3, len(selected)))
            # Nunca abstenerse si hay cualquier pasaje: el evaluador penaliza mas
            # abstener bien hecho que una respuesta incorrecta respaldada.
            if not selected:
                response = abstention(question, "La recuperación no devolvió evidencia",
                                      [])
            else:
                tokens = (self._tokens_disponibles(diagnostics["rescate"])
                          if self.config.presupuesto_s else None)
                diagnostics["tokens_disponibles"] = tokens
                response, traces, valid = self.generator.answer(question, selected, deadline, tokens)
                diagnostics.update(citas=traces, json_original_valido=valid,
                                   cierre_pensamiento=getattr(self.generator, "last_cierre", False),
                                   letras=getattr(self.generator, "last_letras", None),
                                   pensar=getattr(self.generator, "last_pensar", None),
                                   salida_original=getattr(self.generator, "last_raw", None))
                # Garantiza top_k_evidence pasajes conservando el orden del generador.
                existing = {(p["doc_id"], p["inicio"], p["fin"]) for p in response["pasajes_recuperados"]}
                for p in selected:
                    if len(response["pasajes_recuperados"]) >= self.config.top_k_evidence:
                        break
                    k = (p["doc_id"], p["inicio"], p["fin"])
                    if k not in existing:
                        response["pasajes_recuperados"].append(public_passage(p))
                        existing.add(k)
        response["latencia_ms"] = round((time.perf_counter() - started) * 1000)
        diagnostics["generaciones"] = self.generator.generaciones
        problems = validate_response(response, self.config)
        if problems:
            raise ValueError(f"Salida inválida para {question['id']}: {problems}")
        return response, diagnostics

    def close(self):
        self.generator.close()
        if self.reranker:
            self.reranker.close()
        self.retriever.close()


def run(config, questions_path, output, resume=False, expected_count=None):
    from tqdm import tqdm
    questions_path, output = questions_path.resolve(), output.resolve()
    if output == questions_path:
        raise ValueError("La salida no puede sobrescribir el banco de preguntas.")
    if output.exists() and not resume:
        raise FileExistsError(f"{output} ya existe. Usa --resume o elige otra salida.")
    questions = [blind_question(q) for q in records(questions_path)]
    if not questions:
        raise ValueError("El banco de preguntas está vacío.")
    ids = [q["id"] for q in questions]
    if len(set(ids)) != len(ids) or any(type(i) is not int for i in ids):
        raise ValueError("El banco contiene IDs duplicados o no enteros.")
    if expected_count is not None and len(ids) != expected_count:
        raise ValueError(f"Se esperaban {expected_count} preguntas, llegaron {len(ids)}.")
    config.index_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_path = output.with_suffix(".run.json")
    build_file = config.index_dir / "build.json"
    source_hash = hashlib.sha256()
    for path in sorted((config.root / "src/legalrag").rglob("*.py")):
        source_hash.update(str(path.relative_to(config.root)).replace("\\", "/").encode())
        source_hash.update(path.read_bytes())
    signature = {"questions_sha256": sha256(questions_path), "index_sha256": sha256(build_file),
                 "codigo_sha256": source_hash.hexdigest(),
                 "config": config.serializable()}
    if resume and output.exists():
        if not run_path.exists():
            raise ValueError("No hay metadatos de la ejecución que se intenta retomar.")
        previous = json.loads(run_path.read_text(encoding="utf-8"))
        if previous["firma"] != signature:
            raise ValueError("Cambió el banco, el índice o la configuración. Usa otra salida.")
    existing = list(records(output)) if resume and output.exists() else []
    if any(validate_response(row, config) for row in existing):
        raise ValueError("La salida previa tiene líneas inválidas. Conserva una copia y revisa la última línea.")
    done = {r["id"] for r in existing}
    if len(done) != len(existing) or not done.issubset(set(ids)):
        raise ValueError("IDs incompatibles en la salida previa.")
    if len(done) == len(ids):
        print(f"  Ya completado: {len(done)}/{len(ids)}", flush=True)
        return output
    pipeline = Pipeline(config)
    write_json(run_path, {"fecha": now(), "firma": signature, "estado": "en_curso",
                         "decoder_revision": pipeline.generator.revision,
                         "reranker_revision": pipeline.reranker.revision if pipeline.reranker else None,
                         "parametros_decoder": pipeline.generator.parameter_count})
    trace_path = output.with_suffix(".trace.jsonl")
    generated, original_valid, abstained = 0, 0, 0
    score_total, latency_total = 0.0, 0.0
    fmt_answered = {}
    fmt_abstained = {}
    try:
        with output.open("a", encoding="utf-8") as stream, trace_path.open("a", encoding="utf-8") as trace:
            bar = tqdm(questions, desc="Generando", unit="q", bar_format="  {l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
            for question in bar:
                if question["id"] in done:
                    continue
                t0 = time.perf_counter()
                try:
                    response, diagnostic = pipeline.answer(question)
                except Exception as error:
                    # Una pregunta que falla (memoria de la GPU, una salida inválida, un dato raro del banco) no puede
                    # tumbar las otras: queda como abstención válida y el error queda en la traza para revisarlo.
                    import traceback
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except Exception:
                        pass
                    response = abstention(question, f"error interno ({type(error).__name__})")
                    response["latencia_ms"] = round((time.perf_counter() - t0) * 1000)
                    diagnostic = {"error": traceback.format_exc()[-4000:], "json_original_valido": False}
                    print(f"\n  Pregunta {question['id']}: {type(error).__name__}: {error} → abstención", flush=True)
                dt = time.perf_counter() - t0
                dump_line(trace, {"id": question["id"], **diagnostic})
                trace.flush()
                os.fsync(trace.fileno())
                dump_line(stream, response)
                stream.flush()
                os.fsync(stream.fileno())
                done.add(question["id"])
                generated += 1
                original_valid += int(diagnostic.get("json_original_valido", False))
                is_abs = response["abstencion"]
                abstained += int(is_abs)
                top3 = diagnostic.get("top3_score", 0)
                score_total += top3
                latency_total += dt
                fmt = response.get("formato", "?")
                if is_abs:
                    fmt_abstained[fmt] = fmt_abstained.get(fmt, 0) + 1
                else:
                    fmt_answered[fmt] = fmt_answered.get(fmt, 0) + 1
                status = "ABS" if is_abs else "OK "
                bar.set_postfix_str(f"{status} top3={top3:.2f} {dt:.1f}s")
    finally:
        pipeline.close()
    metadata = json.loads(run_path.read_text(encoding="utf-8"))
    metadata.update(estado="completo", respuestas=len(done), sha256_salida=sha256(output))
    write_json(run_path, metadata)

    # ── Resumen ──
    results = list(records(output))
    total = len(results)
    answered = sum(1 for r in results if not r.get("abstencion"))
    abs_count = total - answered
    avg_lat = latency_total / max(generated, 1)
    avg_score = score_total / max(generated, 1)
    all_fmts = sorted(set(list(fmt_answered) + list(fmt_abstained)))

    print("\n" + "=" * 50, flush=True)
    print("  RESULTADOS", flush=True)
    print("=" * 50, flush=True)
    print(f"  Respondidas:    {answered}/{total}", flush=True)
    print(f"  Abstenciones:   {abs_count}/{total}", flush=True)
    print(f"  JSON válido:    {original_valid}/{generated}", flush=True)
    print(f"  Retrieval avg:  {avg_score:.3f}", flush=True)
    print(f"  Latencia avg:   {avg_lat:.1f}s/pregunta", flush=True)
    print(f"  Tiempo total:   {latency_total/60:.1f} min", flush=True)
    print("-" * 50, flush=True)
    for fmt in all_fmts:
        a = fmt_answered.get(fmt, 0)
        b = fmt_abstained.get(fmt, 0)
        print(f"  {fmt:20s}  {a}/{a+b} ok", flush=True)
    print(f"\n  Salida: {output}", flush=True)
    print("=" * 50 + "\n", flush=True)

    return output
