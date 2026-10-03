class Reranker:
    def __init__(self, config):
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        self.config = config
        self.tokenizer = AutoTokenizer.from_pretrained(config.reranker_model,
                                                      revision=config.reranker_revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            config.reranker_model, revision=config.reranker_revision,
            dtype=torch.float16 if config.device == "cuda" else torch.float32,
            trust_remote_code=False).to(config.device).eval()
        self.revision = getattr(self.model.config, "_commit_hash", None)
        self._memo_pregunta, self._memo = None, {}

    def rank(self, question, passages):
        import torch
        if not passages:
            return []
        # Mark 44: memoria de puntajes por (consulta, fragmento). Los rescates vuelven a ordenar la unión de
        # candidatos (50 → 100 → 250); sin memoria, cada pasaje se puntuaba otra vez en cada _rank.
        if self._memo_pregunta != question:
            self._memo_pregunta, self._memo = question, {}
        nuevos = [p for p in passages if p["chunk_id"] not in self._memo]
        for start in range(0, len(nuevos), self.config.reranker_batch_size):
            batch = nuevos[start:start + self.config.reranker_batch_size]
            inputs = self.tokenizer([[question, p["encabezado"] + "\n" + p["texto"]] for p in batch],
                                    padding=True, truncation="only_second", max_length=1024,
                                    return_tensors="pt").to(self.config.device)
            with torch.inference_mode():
                valores = torch.sigmoid(self.model(**inputs).logits.float().reshape(-1)).cpu().tolist()
            self._memo.update((p["chunk_id"], v) for p, v in zip(batch, valores))
        scores = [self._memo[p["chunk_id"]] for p in passages]
        if self.config.kelsen_boost:
            from legalrag.retrieval.kelsen import especialidad, factor, vigencia
            area = getattr(self, "area_pregunta", None) if self.config.kelsen_especial else None
            scores = [s * factor(p, self.config.kelsen_codigos, self.config.kelsen_doctrina)
                      * vigencia(p, self.config.kelsen_horizontal) * especialidad(p, area, self.config)
                      for p, s in zip(passages, scores)]
        # Devolvemos TODO el ranking para que la capa superior pueda diversificar.
        ranked = sorted(({**p, "reranker_score": float(s)} for p, s in zip(passages, scores)),
                        key=lambda p: (-p["reranker_score"], p["chunk_id"]))
        return ranked

    def close(self):
        import gc
        import torch
        del self.model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
