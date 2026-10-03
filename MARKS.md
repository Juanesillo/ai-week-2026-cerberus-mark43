# Cerberus: iteraciones (marks)

Cada mark se corre con `python3 src/main.py --mark N` (comprueba datos e índice, responde la muestra de 50 y pasa
el evaluador oficial). Para comparar dos salidas pregunta por pregunta: `scripts/comparar_salidas.py`. Cada mark se corre sobre la muestra de 50 y se compara con el anterior con `scripts/comparar_salidas.py`
(evaluador oficial, cambios pregunta por pregunta y RAGAS≈). Las opciones nuevas de cada mark se agregan sin
cambiar el comportamiento de los anteriores: sin ellas, el sistema reproduce el mark previo.

| Mark | Opciones de `run` | Muestra (determinista /50) |
|---|---|---|
| 42 | `--hybrid --no-hyde --mc-thinking --multi-query` | 42,90 (`reports/eval_phase6.json`) |
| 43 | Mark 42 + `--herramientas-v2 --normalizador` | 39,77 (transformers 5.3, torch 2.11) |
| 44a | Mark 43 + `--mc-rapido --mc-pensar-tokens 1536 --seguridad 90 --reranker-lote 16` | 42,90 · cerradas 13/15 · 15,8 s/preg |
| 44b | 44a + `--suficiencia --reformulador-iterativo` (agentes de Cerberus) | 44,47 · cerradas 14/15 · RAGAS≈ 12,97 · 19,3 s/preg |
| 44c | 44b + `--encabezado-canonico --reservar-nombradas` | 45,11 · citas 17,14 · RAGAS≈ 13,16 · 18,9 s/preg |
| 44d | 44c + arreglo de `render` (sentencias con año; siempre activo) | 45,52 · citas 17,55 · RAGAS≈ 13,12 · 19,0 s/preg |
| 44 | 44d + `--preferir-jurisprudencia` | **45,93** · cerradas 14/15 · citas 17,96 (recall 0,898) · abstención 9,30 · 19,0 s/preg |

```bash
python -m legalrag.cli run --questions data/oficial/data/sample_50.jsonl --output salidas/mark42.jsonl \
  --hybrid --no-hyde --mc-thinking --multi-query
python -m legalrag.cli run --questions data/oficial/data/sample_50.jsonl --output salidas/mark43.jsonl \
  --hybrid --no-hyde --mc-thinking --multi-query --herramientas-v2 --normalizador
python scripts/comparar_salidas.py salidas/mark42.jsonl salidas/mark43.jsonl
```

## Mark 43 (de Cerberus sobre Mark 42)

- **Herramientas v2** (`tools/legal_tools.py`, `tool_block_v2`): SMLMV 2026 = $1.750.905 (Decreto 0159 de 2026; la
  tabla v1 tenía $1.500.000); UVT 2015–2026 en ambos sentidos (pesos ↔ UVT); sin año en la pregunta, los dos años
  más recientes (v1 suponía 2024); los plazos de liquidación del art. 11 de la Ley 1150 solo si se habla de liquidar
  un contrato (v1 los agregaba ante cualquier «plazo»).
- **Normalizador de citas** (`tools/normalizador.py`): si la pregunta u opción cita una ley o decreto con un año
  que no existe en el corpus pero sí con otro año, lo anota en el prompt (pregunta 58: «Ley 1564 de 2002» → 2012).

## Mark 44 (razonamiento determinista dentro del tiempo)

- **Cerradas en una sola generación** (`generation/generator.py`, `_mc_rapido`): el modelo piensa hasta cerrar
  `</think>` o hasta 1.536 tokens; un `LogitsProcessor` fuerza el cierre y `{"respuesta_correcta": "`, la letra
  se elige con los logits en float32 del estado oculto y el modelo sigue con la justificación. Un solo prefill.
  Barrido en las 15 cerradas: 768 → 11/15 (23 s), 1.024 → 12/15 (25 s), 1.536 → 13/15 (26 s).
- **Sin decisiones por reloj**: el enunciado exige determinismo (§3.1) y que la verificación en vivo reproduzca
  normas y pasajes (§7). Los 22 s son un promedio sobre las 992 (§B.5); 90 s por pregunta solo como seguridad.
- **Reproducibilidad**: `supported_bodies` devolvía un `set` y `augment_citations` agregaba normas distintas en
  cada proceso (PYTHONHASHSEED). Ahora el orden es el del ranking.
- **Velocidad sin cambiar resultados**: índices FAISS en memoria (antes se recargaban de disco en cada rescate),
  una sola pasada de BM25 por consulta con normas nombradas, memoria de puntajes del reranker, calentamiento.
- **Agentes de Cerberus** (`retrieval/suficiencia.py`): el decoder juzga P(«Sí») a «¿bastan los 5 primeros
  pasajes?» y, si no, un reformulador escribe con esos pasajes a la vista la consulta de una segunda búsqueda.
  Se suma al disparador por puntaje del reranker. 42,90 → 44,47 (+748), 19,3 s de promedio.
- **Citas**: `--encabezado-canonico` agrega «Ley N de AAAA» al encabezado cuando su nombre descriptivo no es
  citable (66 normas, 23 mil fragmentos); `--reservar-nombradas` pone 2 fragmentos de cada norma nombrada en la
  pregunta (texto libre). 44,47 → 45,11 (+272).
- **Sentencias con año** (`citations/official.py`, `render`): «Sentencia SU-16» sin año no lo reconoce el extractor
  oficial; cada sentencia agregada por `augment_citations` era texto muerto desde Mark 42. 45,11 → 45,52 (+253).
- **Jurisprudencia primero** (`--preferir-jurisprudencia`): en sub-tareas de precedente o sentido del fallo
  (§4.2), la jurisprudencia respaldada se agrega antes que códigos y leyes. 45,52 → 45,93 (+453).
- Medido y descartado: `--jerarquia` (pirámide de Kelsen en todas las preguntas: 44,47 → 39,14) y
  `--jerarquia-condicional` (solo sub-tareas de jerarquía/conflicto: neutra en la muestra).
- Opciones aún sin medir en las 50: (pirámide de Kelsen colombiana), `--normalizador-directo`, `--encabezado-canonico` y
  `--reservar-nombradas` (techo de citas 0,898 → 0,918 juntas), `--bm25-sin-vacias`, `--subconsultas-sin-pista`.

## Corpus reindexado (2-oct) y Marks 45–46

El equipo reindexó el corpus (núcleo 22.247 documentos, 1,22 M de fragmentos, texto en Markdown con metadatos
Kelsen). Con el mismo Mark 44 dio **41,98** (índice anterior: 45,93). El usuario decidió entregar con el índice nuevo
(el anterior está incompleto); todo lo que sigue se midió en él, contra la corrida inmediatamente anterior y aceptando
solo con 0 empeoras.

- **Offsets del índice en Markdown** (`retrieval/dense.py`, `texto_padre`): el generador expandía cada pasaje al
  artículo completo cortando el `.txt` con offsets que eran del Markdown, así que Qwen leía otro artículo (el «Art. 1501»
  del Código Civil llegaba con el texto del 1512). Ahora, si los offsets no cuadran, el artículo se arma con los
  fragmentos del propio índice (1.411 de 1.411 reconstruidos exactos). Error real; el puntaje no cambió (41,98).
- **Diagnóstico del embudo** (`scripts/embudo.py`): la búsqueda trae el **100 %** de las normas de referencia entre los
  candidatos; se pierden en el reranker (247, 128) y en la selección final. La recuperación no es el cuello de botella.
- **Mark 45 = Mark 44 + `kelsen_boost`** (`retrieval/kelsen.py`): el puntaje del reranker se multiplica por la jerarquía
  normativa (Constitución 1,15 · sentencias C 1,12 · SU 1,10 · leyes 1,08 · decretos 1,05 · resoluciones 1,02), con el
  nivel recalculado desde `norma` (el `nivel_kelsen` del índice clasifica mal las sentencias `sentencia_cc_c…`).
  41,98 → **42,80** (+253, +1073), 19,8 s. En el índice anterior empeoraba (45,93 → 43,54): depende del índice.
- **Mark 46 = Mark 45 + `normalizador_directo`**: la nota pide evaluar la opción con el año corregido; si otra opción ya
  cita esa norma con el año real (distractor deliberado), solo informa. 42,80 → **44,36** (+58), 19,6 s.
  Reproducido por el usuario a las 14:41 (44,36, 19,5 s); Mark 45 y Mark 46, corridas en procesos distintos, coinciden en
  las otras 49 preguntas salvo `latencia_ms` (`scripts/determinismo.py`).
- Medido y descartado (índice nuevo): tope de 1 fragmento por documento (MMR; techo de citas 0,898 → 0,939 pero 41,33),
  tope + Kelsen (42,15), citar primero las normas propias de los pasajes (41,10), agente de figuras de Cerberus (neutro:
  Qwen nombra figuras genéricas y el reranker rechaza el artículo), `reservar_reformulador`, `consulta_con_tema`,
  `area_en_prompt`, 100 candidatos y el grafo normativo como expansión (0 normas nuevas en 41 preguntas, sin GPU).
- Neutras en lo determinista, pendientes del juez real: redacción concisa (`--semi-concisas --abiertas-directas`,
  15,7 s en texto libre) y orden jurídico del contexto + razonamiento tipo IRAC (`--kelsen-diversificar
  --razonamiento-juridico`, 16,4 s).
- RAGAS real: `scripts/ragas_oficial.py` ejecuta el evaluador oficial sin modificarlo, una respuesta por vez (sin llamadas
  simultáneas al juez) y con caché; `scripts/analizar_ragas.py` cruza la nota de cada pregunta con el diagnóstico.
