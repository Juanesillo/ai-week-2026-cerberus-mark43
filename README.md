# Cerberus — Equipo P34K, Hackathon 2026

**Integrantes:**

Samuel Charry Tobar

Juan Esteban Triviño nieves 

Shaiel Mateo Jimenez Posada 


**Universidad de los Andes** · Departamento de Ingeniería de Sistemas y Computación · AI Week 2026

Sistema de respuesta a preguntas de derecho colombiano con un modelo abierto de tamaño
reducido y un corpus jurídico propio. Recuperación híbrida sobre un índice FAISS del
corpus, reordenamiento con un *reranker* abierto, recuperación iterativa, generación
determinista con Qwen3-8B y verificación de que toda norma citada proceda de un pasaje
efectivamente recuperado.

## Reproducción en un solo comando

Desde un árbol recién clonado, con Python 3.10 disponible:

```bash
./reproducir.sh
```

Crea el entorno, instala las dependencias, comprueba que estén el corpus y el índice,
responde las 50 preguntas de muestra y pasa el evaluador oficial. Si su intérprete 3.10 se
llama de otro modo: `PYTHON=/ruta/a/python3.10 ./reproducir.sh`.

El script **no descarga el corpus**: pesa ~15 GB y se publica aparte (§9.3). Descárguelo
del enlace de la sección siguiente y descomprímalo en la raíz, de modo que queden `index/`
y `data/processed/`.

Para generar la entrega sobre el banco completo, una vez colocado `test_992.jsonl` en
`data/oficial/data/`:

```bash
python src/main.py --split test        # 992 preguntas -> submissions.jsonl
```

## Corpus e índice



| Recurso | Enlace | Tamaño | Licencia |
|---|---|---|---|
| Corpus procesado e índice vectorial | https://drive.google.com/drive/folders/1Wb9210bh26VtHSink3AOwv5I4wn-rs9F?usp=sharing | ~15 GB | CC-BY-4.0 |

link alternativo: https://uniandes-my.sharepoint.com/shared?listurl=https%3A%2F%2Funiandes%2Dmy%2Esharepoint%2Ecom%2Fpersonal%2Fj%5Ftrivinon%5Funiandes%5Fedu%5Fco%2FDocuments&id=%2Fpersonal%2Fj%5Ftrivinon%5Funiandes%5Fedu%5Fco%2FDocuments%2FDATAP34K&ct=1791057150815&or=OWA%2DNT%2DMail&shareLink=1&ga=1


Requisitos del enlace (§9.3): descarga sin solicitud de permiso, lectura para cualquiera
que tenga el vínculo, y activo durante treinta días.

## Video

| Entregable | Enlace |
|---|---|
| Video de máximo 5 minutos | https://youtu.be/vCRKbU21F-I?si=ddW7PB6i-I5zPsb3 |

## Entrega

`submissions.jsonl` con las 992 respuestas se sube a la raíz de este repositorio. El
esquema es `data/oficial/schema/submission.schema.json`; lo produce
`python src/main.py --split test`.

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

## Detalle de ejecución

`./reproducir.sh` equivale a estos pasos, por si prefiere darlos a mano:

```bash
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # incluye `-e .`, que exige Python 3.10
python src/main.py --split sample        # escribe salidas/mark50.jsonl + evaluador oficial
```

El mark por defecto es el 50 (`MARK_ACTUAL` en `src/legalrag/config.py`); `--mark N` corre
cualquier otro. La interfaz usa esa misma configuración, para que lo que el jurado
regenere en vivo coincida con lo entregado (§7).

Para evaluar con el juez de texto libre, tal como lo indica el enunciado:

```bash
python3.10 -m venv .venv-evaluador && source .venv-evaluador/bin/activate
pip install -r data/oficial/scripts/requirements-evaluador.txt
python data/oficial/scripts/evaluate.py --submission entrega.jsonl --split sample --ragas
```

**En un entorno aparte, a propósito.** El evaluador trae `ragas`, `datasets`,
`langchain-openai` y `langchain-community<0.4`, con rangos de `numpy`, `pandas` y
`sentence-transformers` que chocan con los pines de `requirements.txt`. Instalar ambos
sobre el mismo entorno rompe uno de los dos.

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

Evaluador oficial sobre `data/oficial/data/sample_50.jsonl`, sin errores de validación.
Solo los 50 puntos deterministas: los 30 de texto libre dependen del juez de OpenRouter.

| Mark | Qué añade | Total determinista /50 |
|---|---|---:|
| 46 | normalizador de citas directo | 44,36 |
| 47 | orden jurídico e IRAC en texto libre | 44,36 |
| 48 | criterio cronológico (lex posterior) | 44,36 |
| 49 | precedente reciente primero | 44,77 |
| **50** (por defecto) | semiabiertas concisas | **44,77** |

Desglose por componente de la última corrida con detalle completo del evaluador oficial
(Mark 46, medido el 2-oct, reporte en `salidas/mark46_oficial.json`):

| Componente | Puntos | Posibles |
|---|---:|---:|
| Exactitud en cerradas | 17,33 | 20 |
| Calidad de citación | 17,96 | 20 |
| Abstención calibrada | 9,07 | 10 |
| **Total determinista** | **44,36** | **50** |

Detalle: 13 de 15 cerradas (exactitud 0,867 frente a la referencia de 0,905); *recall*
ponderado de citas 0,898, con **0 citas sin respaldo** en la evidencia recuperada;
calibración de abstención 0,907. Mark 49 y 50 suben el total a 44,77 sin empeorar ninguna
pregunta; las cifras por mark están anotadas en `src/legalrag/config.py`.

La muestra son 50 ítems: cada mejora de esta tabla equivale a una o dos preguntas, así que
el resultado sobre las 992 será más bajo.

## Interfaz gráfica

```bash
python -m legalrag.cli serve        # http://127.0.0.1:8000
```

Permite formular una pregunta jurídica y ver la respuesta junto con los pasajes
recuperados y las normas citadas. Responde con la misma configuración que generó la
entrega (§7). Detenerla con `Ctrl + C` antes de lanzar otra ejecución que use los modelos,
para no competir por la memoria de la GPU.

Cubre los tres criterios del §6.2:

- **Consulta de extremo a extremo.** Formulario de pregunta contra el mismo pipeline de la
  entrega, con la traza de la corrida (modelo, candidatos, tiempo, decodificación).
- **Pasajes y normas citadas.** El resultado lista los pasajes recuperados con su score, y
  el panel «Ver la evidencia» separa las normas citadas en la respuesta de los pasajes que
  recibió el generador.
- **Identidad visual de Software Colombia.** Paleta y tipografía en
  `interfaz/styles/tokens.css` (`--sc-cyan`, `--sc-orange`, `--sc-deep`), con el
  descargo de que es un trabajo académico y no un producto oficial del patrocinador.

El arranque tarda varios minutos: carga los índices y los modelos, y la primera vez
también los descarga.

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
reproducir.sh             comando único de reproducción (§6.2)
src/                      pipeline completo (entrada: src/main.py)
interfaz/                 interfaz gráfica
scripts/                  evaluación con el juez y herramientas de medición
data/oficial/             material de los organizadores (preguntas, esquema, evaluador)
informe/INFORME_TECNICO.pdf
CORPUS.md                 bitácora del corpus (inventario, criterio, método)
corpus_manifest.json      un registro por documento incorporado (32.617)
submissions.jsonl         las 992 respuestas de la entrega
MARKS.md, CONTINUAR.md    bitácora de iteraciones y estado del trabajo
```

### Mapa de entregables (§9.2)

| N.º | Entregable | Dónde |
|---|---|---|
| 2 | Repositorio con README (dependencias, arquitectura, comando único) | este archivo |
| 3 | `submissions.jsonl` con las 992 respuestas | raíz del repositorio |
| 4 | `CORPUS.md` y `corpus_manifest.json` | raíz del repositorio |
| 5 | Corpus e índice bajo licencia abierta | sección «Corpus e índice» |
| 6 | Informe técnico de máximo 3 páginas | `informe/INFORME_TECNICO.pdf` |
| 7 | Video de máximo 5 minutos | sección «Video» |
| 8 | Interfaz gráfica | `interfaz/`, se levanta con `legalrag.cli serve` |

El código usa MIT (`LICENSE`). El procesamiento del corpus conserva la licencia de
`data/raw/LICENSE` y sus excepciones para contenido de terceros; cada modelo mantiene la
suya. Se conservan fuentes, fechas, *hashes* y marcas de vigencia, sin que una descarga
certifique vigencia jurídica.

El esquema oficial describe `null` para la abstención en preguntas cerradas, pero su
`enum` solo admite A–D. Por compatibilidad se guarda `A` como valor técnico junto a
`abstencion: true`, sin tratarla como respuesta elegida.
