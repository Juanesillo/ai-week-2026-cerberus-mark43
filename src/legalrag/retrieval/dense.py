from collections import Counter
from dataclasses import replace
import json
import sqlite3
from legalrag.encoding.embed import Encoder
from legalrag.ingestion.coverage_audit import lexical_query
from legalrag.citations.extract import extract_references
from legalrag.io import sha256, source_path


class Retriever:
    def __init__(self, config):
        import faiss
        self.config = config
        path = config.index_dir / "build.json"
        if not path.is_file():
            raise FileNotFoundError("Ejecuta index antes de run.")
        self.build = json.loads(path.read_text(encoding="utf-8"))
        if self.build["config"]["embedding_model"] != config.embedding_model:
            raise ValueError("El encoder no coincide con el índice.")
        revision = self.build.get("encoder_revision")
        self.encoder = Encoder(replace(config, embedding_revision=revision or config.embedding_revision))
        self.databases = {}
        for tier in self.build["particiones"]:
            dbpath = config.index_dir / f"{tier}.sqlite"
            if sha256(dbpath) != self.build["particiones"][tier]["sha256_metadata"]:
                raise ValueError(f"Metadatos alterados: {tier}")
            self.databases[tier] = sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True)
        self.index = None
        self.loaded_tier = None
        self.cache = {}
        import threading
        self._hilos = threading.local()
        self.verified = set()
        self.verified_sources = set()
        faiss.omp_set_num_threads(1)

    def _load(self, tier):
        import faiss
        import psutil
        if self.loaded_tier == tier:
            return self.index
        # Mark 44: los índices quedan en memoria (nucleo 4 GB + complementario 0,7 GB). Antes, cada rescate
        # «complementario» recargaba su índice desde disco y la pregunta siguiente recargaba nucleo (1,4-3,4 s).
        if tier in self.cache:
            self.index, self.loaded_tier = self.cache[tier], tier
            return self.index
        self.index = None
        self.loaded_tier = None
        path = self.config.index_dir / f"{tier}.faiss"
        if path.stat().st_size > psutil.virtual_memory().available * .8:
            raise MemoryError(f"{tier}: FAISS necesita aproximadamente {path.stat().st_size / 2**30:.1f} GiB de RAM.")
        if tier not in self.verified:
            if sha256(path) != self.build["particiones"][tier]["sha256_index"]:
                raise ValueError(f"Índice alterado: {tier}")
            self.verified.add(tier)
        self.index = faiss.read_index(str(path))
        if self.index.d != (getattr(self.encoder.model, 'get_embedding_dimension', None) or self.encoder.model.get_sentence_embedding_dimension)():
            raise ValueError("Dimensión incompatible con el encoder.")
        self.loaded_tier = tier
        self.cache[tier] = self.index
        return self.index

    def _db(self, tier):
        """Conexión de solo lectura por hilo (las sub-búsquedas corren en paralelo)."""
        import threading
        if threading.current_thread() is threading.main_thread():
            return self.databases[tier]
        conexiones = self._hilos.__dict__.setdefault("db", {})
        if tier not in conexiones:
            dbpath = self.config.index_dir / f"{tier}.sqlite"
            conexiones[tier] = sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True)
        return conexiones[tier]

    def search_many(self, questions, tier="nucleo", paralelo=False):
        """Mark 44: varias consultas (sub-consultas de multi_query) con el mismo resultado que llamar a `search`
        una por una, en el mismo orden. Los vectores se calculan antes, en serie (la GPU no se comparte entre
        hilos); FAISS y SQLite sueltan el GIL, así que BM25 y la búsqueda densa corren en paralelo."""
        from concurrent.futures import ThreadPoolExecutor
        self._load(tier)
        if not paralelo:
            # Si las consultas nombran normas (p. ej. con la pista de área), la ruta exacta ordena en Python y
            # en paralelo queda atada al GIL: en serie es más rápido (748: 3,3 s frente a 5,7 s).
            return [self.search(q, tier) for q in questions]
        vectores = [self.encoder.encode([q]) for q in questions]
        with ThreadPoolExecutor(max_workers=max(1, len(questions))) as pool:
            return list(pool.map(lambda qv: self.search(qv[0], tier, vectors=[qv[1]]), zip(questions, vectores)))

    def search(self, question, tier="nucleo", expanded=None, vectors=None):
        index = self._load(tier) if vectors is None else self.cache[tier]
        if index.ntotal == 0:
            return []
        k = min(self.config.top_k_retrieval * 3, index.ntotal)
        db = self._db(tier)
        ranking_lists = []
        dense_scores = {}
        consultas = [question] + ([expanded] if expanded else [])
        vectors = vectors or [self.encoder.encode([q]) for q in consultas]
        for vector in vectors:
            scores, ids = index.search(vector, k)
            ranking_lists.append([int(i) for i in ids[0] if i >= 0])
            for i, score in zip(ids[0], scores[0]):
                if i >= 0:
                    dense_scores[int(i)] = max(dense_scores.get(int(i), -1), float(score))
        exact = []
        if self.config.hybrid:
            query = lexical_query(question, self.config.bm25_sin_vacias)
            # Mark 44: una sola pasada de BM25 por consulta; el top global y el top dentro de cada norma nombrada
            # salen de la misma lista ordenada por (bm25, rowid). Mismo resultado que una consulta FTS por norma,
            # que repetía el puntaje de todas las coincidencias (~0,5 s por norma nombrada).
            referencias = extract_references(question)
            if query and any(not ref.articulo for ref in referencias):
                todos = sorted(db.execute("SELECT rowid, bm25(lexical) FROM lexical WHERE lexical MATCH ?",
                                          (query,)).fetchall(), key=lambda r: (r[1], r[0]))
            elif query:  # sin normas nombradas basta el top global, que SQLite calcula sin traer todo
                todos = db.execute("SELECT rowid, bm25(lexical) FROM lexical WHERE lexical MATCH ? "
                                   "ORDER BY bm25(lexical),rowid LIMIT ?", (query, k)).fetchall()
            else:
                todos = []
            for ref in referencias:
                if ref.articulo:
                    hits = [h[0] for h in db.execute(
                        "SELECT id FROM chunks WHERE norma=? AND articulo=? ORDER BY id LIMIT ?",
                        (ref.norma, ref.articulo, k))]
                else:
                    de_la_norma = {h[0] for h in db.execute("SELECT id FROM chunks WHERE norma=?", (ref.norma,))}
                    hits = [i for i, _ in todos if i in de_la_norma][:k]
                    if not hits:
                        hits = sorted(de_la_norma)[:k]
                exact.extend(hits)
            if query:
                ranking_lists.append([i for i, _ in todos[:k]])
            if exact:
                ranking_lists.append(list(dict.fromkeys(exact)))
        fused = Counter()
        for ranking in ranking_lists:
            for position, vector_id in enumerate(ranking, 1):
                fused[vector_id] += 1 / (self.config.rrf_k + position)
        result = []
        parents_count = Counter()
        for vector_id, score in sorted(fused.items(), key=lambda item: (-item[1], item[0])):
            row = db.execute("SELECT metadata,texto FROM chunks WHERE id=?", (vector_id,)).fetchone()
            passage = json.loads(row[0])
            passage["texto"] = row[1]
            if parents_count[passage["parent_id"]] >= 2:
                continue
            parents_count[passage["parent_id"]] += 1
            passage.update(score=float(score), dense_score=dense_scores.get(vector_id),
                           exact_match=vector_id in exact)
            result.append(passage)
            if len(result) == self.config.top_k_retrieval:
                break
        return result

    def search_norma(self, question, norma, k=12, tier="nucleo"):
        """Mark 44: los fragmentos de una norma más cercanos a la consulta (FAISS exacto restringido a sus ids)."""
        import faiss
        import numpy as np
        index = self._load(tier)
        db = self._db(tier)
        ids = [r[0] for r in db.execute("SELECT id FROM chunks WHERE norma=?", (norma,))]
        if not ids:
            return []
        selector = faiss.IDSelectorBatch(np.array(ids, dtype="int64"))
        scores, found = index.search(self.encoder.encode([question]), min(k, len(ids)),
                                     params=faiss.SearchParameters(sel=selector))
        result = []
        for vector_id, score in zip(found[0], scores[0]):
            if vector_id < 0:
                continue
            row = db.execute("SELECT metadata,texto FROM chunks WHERE id=?", (int(vector_id),)).fetchone()
            passage = json.loads(row[0])
            passage.update(texto=row[1], score=float(score), dense_score=float(score), exact_match=True)
            result.append(passage)
        return result

    def estatuto_de_figura(self, figura, minimo=3, tier="nucleo"):
        """El estatuto (ley, decreto, código o Constitución) cuyo propio texto más menciona la figura, o None.

        «acción popular» → Ley 472 de 1998; «habeas data» → Ley 1581 de 2012. Búsqueda de frase exacta en FTS5
        (sin tildes), contando fragmentos por norma; exige al menos `minimo` fragmentos y que la norma ganadora
        no empate con la segunda."""
        frase = '"' + figura.replace('"', " ").strip() + '"'
        filas = self._db(tier).execute(
            "SELECT c.norma, count(*) n FROM lexical l JOIN chunks c ON c.id = l.rowid WHERE lexical MATCH ? AND "
            "(c.norma LIKE 'ley\\_%' ESCAPE '\\' OR c.norma LIKE 'decreto\\_%' ESCAPE '\\' "
            "OR c.norma LIKE 'constitucion%' OR c.norma LIKE 'codigo%') "
            "GROUP BY c.norma ORDER BY n DESC, c.norma LIMIT 2", (frase,)).fetchall()
        if not filas or filas[0][1] < minimo or (len(filas) > 1 and filas[1][1] == filas[0][1]):
            return None
        return filas[0][0]

    def texto_padre(self, p):
        """Artículo completo (parent) de un pasaje, reconstruido con sus fragmentos del índice.

        El índice del 2-oct se construyó sobre el corpus convertido a Markdown: sus offsets son posiciones en ese
        Markdown, no en el `.txt` de `texto_archivo`, así que cortar el `.txt` con ellos da otro artículo. Cada
        fragmento es un corte exacto del Markdown (`len(texto) == fin - inicio`), de modo que el artículo se arma
        uniendo los fragmentos del mismo parent. None si quedan huecos.
        """
        filas = self._db(p["nivel"]).execute("SELECT inicio, fin, texto FROM chunks WHERE parent_id=? "
                                             "ORDER BY inicio, fin", (p["parent_id"],)).fetchall()
        partes, hasta = [], p["parent_inicio"]
        for inicio, fin, texto in filas:
            if fin <= hasta:
                continue
            if inicio > hasta or len(texto) != fin - inicio:
                return None
            partes.append(texto[hasta - inicio:])
            hasta = fin
        return "".join(partes) if hasta == p["parent_fin"] else None

    def verify_sources(self, passages):
        for passage in passages:
            identity = passage["doc_id"]
            if identity in self.verified_sources:
                continue
            expected = self.build["particiones"][passage["nivel"]]["hashes_texto"][identity]
            if sha256(source_path(self.config, passage)) != expected:
                raise ValueError(f"El texto canónico cambió desde la indexación: {identity}")
            self.verified_sources.add(identity)

    def close(self):
        self.index = None
        self.cache = {}
        for db in self.databases.values():
            db.close()
        self.encoder.close()
