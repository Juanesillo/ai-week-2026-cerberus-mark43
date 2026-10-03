# P34K — Hackathon 2026

**Integrantes:** <!-- PENDIENTE: los tres nombres, como se registraron en la sesión inaugural -->
**Universidad de los Andes**

Sistema de respuesta a preguntas de derecho colombiano con un modelo abierto de tamaño
reducido y un corpus jurídico propio. Recuperación híbrida sobre un índice FAISS del
corpus, reordenamiento con un *reranker* abierto, generación determinista con Qwen3-8B y
verificación de que toda norma citada proceda de un pasaje efectivamente recuperado.

## Corpus e índice

<!-- OBLIGATORIO. El jurado descarga desde aquí. Verificar el enlace desde una sesión
     privada del navegador antes de las 15:00. -->

| Recurso | Enlace | Tamaño | Licencia |
|---|---|---|---|
| Corpus procesado e índice vectorial | `<PENDIENTE: URL del comprimido>` | ~15 GB | CC-BY-4.0 |

El comprimido contiene `LICENSE`, `corpus_manifest.json`, `corpus/` con los documentos
procesados e `indice/` con el índice serializado y los fragmentos.

El enlace permanece activo hasta el `<PENDIENTE: fecha, treinta días después del evento>`.

## Arquitectura

| Componente | Elección | Motivo |
|---|---|---|
| Encoder | `BAAI/bge-m3`, revisión `5617a9f6`, vectores normalizados | Multilingüe y entrenado para recuperación; rinde en español jurídico sin ajuste |
| Decoder | `Qwen/Qwen3-8B`, revisión `b968826d`, bf16 (4 bits `nf4` si no cabe en memoria) | Modelo abierto con razonamiento explícito, que aprovechamos para acotar el *thinking* de las preguntas cerradas |
| Segmentación | El artículo completo como unidad citable, más ventanas de búsqueda de 512 *tokens* con solapamiento de 64, con el encabezado jurídico antepuesto | El artículo es la unidad de sentido del texto normativo. El encabezado hace que el evaluador reconozca la norma de procedencia del pasaje |
| Recuperación | Híbrida: densa sobre FAISS `FlatIP` + BM25 léxico, fusionadas por RRF (*k* = 60), 50 candidatos. Índice de núcleo y complementario | Las referencias numéricas («artículo 42») son indistinguibles para un *embedding*; BM25 resuelve justo ese caso |
| Reordenamiento | `BAAI/bge-reranker-v2-m3`, revisión `953dc6f6`, umbral 0,25, hasta 10 pasajes de evidencia | Procesa consulta y fragmento a la vez, más preciso que comparar vectores por separado |
| Recuperación iterativa | El decoder juzga si los cinco primeros pasajes bastan; si no, un reformulador escribe con esos pasajes a la vista la consulta de una segunda búsqueda | Una segunda pasada solo donde hace falta, para no gastar el presupuesto de tiempo de manera uniforme |
| Mecanismo de abstención | `abstencion: true` cuando el corpus no da fundamento tras la segunda búsqueda; toda cita se contrasta contra los pasajes recuperados y se suprime si no figura en ellos | Una cita sin respaldo se penaliza al doble de un acierto; abstenerse vale más que inventar |

Generación determinista: `do_sample=False`, `num_beams=1`, temperatura 0 y semilla fija.

## Reproducción

```bash
pip install -r requirements.txt
python src/main.py --split sample
```

Ese comando comprueba los datos, responde las 50 preguntas de muestra, escribe
`salidas/mark46.jsonl` y pasa el evaluador oficial. Para generar la entrega sobre el banco
completo:

```bash
python src/main.py --split test        # 992 preguntas -> submissions.jsonl
```

Para evaluar con el juez de texto libre, tal como lo indica el enunciado:

```bash
pip install -r data/oficial/scripts/requirements-evaluador.txt
python data/oficial/scripts/evaluate.py --submission entrega.jsonl --split sample --ragas
```

Para autoevaluarnos usamos `python scripts/ragas_oficial.py salidas/<corrida>.jsonl` (o
`python src/main.py --ragas`). Ejecuta ese mismo evaluador **sin modificarlo**, pero con una sola
respuesta por ejecución, de modo que el juez nunca recibe llamadas simultáneas (con las 35 juntas,
RAGAS lanza 16 a la vez y en nuestra red el juez no devolvió veredicto en ninguna), y guarda cada
nota para no pagarla dos veces. Como el evaluador divide siempre por las 35 respuestas juzgadas, la
suma de las notas reproduce el puntaje de la corrida conjunta. Requiere `OPENROUTER_API_KEY`.

**Requisitos de hardware:** Python 3.10, GPU NVIDIA de 24 GB (probado en RTX 4090); el
decoder cae a 4 bits si no cabe en bf16. FAISS corre sobre la RAM del equipo. El corpus
procesado y el índice ocupan ~15 GB en disco.

**Tiempo estimado sobre las 50 preguntas de muestra:** 19,5 s por pregunta, unos 16
minutos en total, más la carga inicial de los modelos. El enunciado dispone de ~22 s por
pregunta de promedio (§B.5).

Reconstruir el corpus y el índice desde los originales es un flujo aparte, que no hace
falta para reproducir la entrega:

```bash
python -m legalrag.cli prepare     # extrae y normaliza los originales de data/raw/
python -m legalrag.cli finalize    # reextrae la ampliación
python -m legalrag.cli audit --coverage
python -m legalrag.cli index       # FAISS FlatIP + metadatos en index/
```

## Resultados sobre las preguntas de muestra

Mark 46 (índice reindexado el 1-oct), evaluador oficial sobre `data/oficial/data/sample_50.jsonl`,
sin errores de validación, medido el 2-oct. Reporte completo en `salidas/mark46_oficial.json`.

| Componente | Puntos | Posibles |
|---|---:|---:|
| Exactitud en cerradas | 17,33 | 20 |
| Calidad de citación | 17,96 | 20 |
| Abstención calibrada | 9,07 | 10 |
| **Total determinista** | **44,36** | **50** |

Detalle: 13 de 15 cerradas (exactitud 0,867 frente a la referencia de 0,905); *recall*
ponderado de citas 0,898, con **0 citas sin respaldo** en la evidencia recuperada;
calibración de abstención 0,907. La corrección en texto libre (30 puntos adicionales) se
mide con el juez de OpenRouter y está pendiente de una corrida válida.

La muestra son 50 ítems: cada mejora de esta tabla equivale a una o dos preguntas, así que
el resultado sobre las 992 será más bajo.

## Interfaz gráfica

```bash
python src/main.py --interfaz       # http://127.0.0.1:8000 (o: python -m legalrag.cli serve)
```

Permite formular una pregunta jurídica y ver la respuesta junto con los pasajes
recuperados y las normas citadas. Responde con la misma configuración que generó la
entrega. Detenerla con `Ctrl + C` antes de lanzar otra ejecución que use los modelos, para
no competir por la memoria de la GPU.

## Limitaciones conocidas

1. **El corpus determina el techo.** Las preguntas que seguimos fallando lo son por
   cobertura, no por generación: la 679 (Ley 1581 de 2012) y la 253 (Código Sustantivo del
   Trabajo, pregunta genérica) no recuperan la disposición aplicable, y la 453 cita una
   sentencia que queda fuera del tope de seis citas por respuesta.
2. **La muestra de 50 es optimista.** Cada opción se aceptó midiendo sobre esas 50 y solo
   con cero empeoras, pero cada ganancia venía de una o dos preguntas. Sobre las 992 el
   resultado será menor, y las opciones calibradas contra la muestra pueden no
   generalizar.
3. **El tamaño del decoder está en el límite.** Qwen3-8B tiene 8.190.735.360 parámetros
   contando los *embeddings*, por encima de los 8.000 millones del §3.1. Está pendiente
   confirmarlo por escrito con la organización.
4. **El juez de texto libre no se ha medido con éxito.** Los 30 puntos de RAGAS siguen sin
   una corrida válida, así que de los 80 automáticos solo tenemos verificados los 50
   deterministas.
5. **La abstención casi no se ejerce.** En la muestra el sistema no se abstuvo ninguna vez
   y acertó 39 de 43; el mecanismo existe y está probado, pero su calibración sobre
   preguntas cuyo fundamento falta en el corpus no se ha podido verificar a esta escala.

## Estructura del repositorio

```
src/                      pipeline completo (entrada: src/main.py)
interfaz/                 interfaz gráfica
scripts/                  evaluación con el juez y herramientas de medición
data/oficial/             material de los organizadores (preguntas, esquema, evaluador)
informe/INFORME_TECNICO.pdf
CORPUS.md                 bitácora del corpus
corpus_manifest.json      un registro por documento incorporado
MARKS.md, CONTINUAR.md    bitácora de iteraciones y estado del trabajo
```

El código usa MIT (`LICENSE`). El procesamiento del corpus conserva la licencia de
`data/raw/LICENSE` y sus excepciones para contenido de terceros; cada modelo mantiene la
suya. Se conservan fuentes, fechas, *hashes* y marcas de vigencia, sin que una descarga
certifique vigencia jurídica.

El esquema oficial describe `null` para la abstención en preguntas cerradas, pero su
`enum` solo admite A–D. Por compatibilidad se guarda `A` como valor técnico junto a
`abstencion: true`, sin tratarla como respuesta elegida.
