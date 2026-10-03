# Dónde quedamos (2026-10-02, 08:45)

Traspaso de la sesión de trabajo de Mark 44. Más detalle técnico en `MARKS.md`.

## Estado al 2-oct, 15:00 — ENTREGA: Mark 46 con el índice nuevo

**Mark 46 = 44,36/50** (cerradas 13/15 · citas 17,96 · abstención 9,07 · 19,5 s), por defecto en `src/main.py`, con el
índice del SanDisk (el anterior está incompleto; decisión del usuario). Detalle de cada prueba en `MARKS.md`.

- **Mañana:** 8:00 congelar índice y código; 9:00 `python3 src/main.py --split test` → `submissions.jsonl` (~5,5 h a
  ~20 s por pregunta). Determinismo comprobado con `scripts/determinismo.py` (mismas normas y pasajes entre corridas).
- **RAGAS real:** solo con `scripts/ragas_oficial.py` (o `src/main.py --ragas`): evaluador oficial SIN modificar, una
  respuesta por vez. Rubén prohibió cambiar el evaluador y el equipo no quiere llamadas paralelas (queman la cuota).
  La llave se exporta en la terminal (`export OPENROUTER_API_KEY='sk-or-v1-…'`); verificar con `scripts/probar_juez.py`.
- **Pendiente de decidir con el juez real** (neutras en lo determinista): redacción concisa
  (`salidas/n7_redaccion.jsonl`) y orden jurídico + IRAC (`salidas/n9_irac_kelsenorden.jsonl`).
  `scripts/analizar_ragas.py` compara la nota de cada pregunta.
- **Reporte del viernes 17:00:** `data/oficial/entregables/viernes/REPORTE_AVANCE.pdf` (plantilla oficial llenada, una página; faltan los nombres de los integrantes),
  por correo a rf.manrique@uniandes.edu.co, asunto `[Hackathon 2026] Avance — P34K`.

## Corpus nuevo (2026-10-02, tarde): hay que volver a medir

El equipo reemplazó corpus e índice: nucleo 22.247 documentos (1,22 M fragmentos, antes 17.833) y complementario
10.362 (antes 10.276), inventario congelado en `data/processed/corpus_final/` (32.617 documentos). Índice,
inventario, manifiesto y textos comprobados como un mismo build (sha256). **El 45,93 de Mark 44 se midió con el
índice anterior**: la línea base sobre el corpus nuevo está pendiente (`python3 src/main.py`). Lo apartado está en
`_archivo/` (ver `LEEME.md`, sección «Corpus reindexado»).

## Refactor de la versión de entrega (2026-10-02)

El repositorio quedó en la estructura del §9.2 del enunciado, **sin tocar la lógica**. Lo que no usa la
solución se apartó a `_archivo/` (28 MB, nada se borró salvo cachés regenerables); ver `_archivo/LEEME.md`.
Fuera: el prototipo anterior de `legalrag/` (9 módulos que el redirect de `__init__.py` volvía inalcanzables),
los shims `cli.py`/`cobertura.py`/`grafo.py`, `tests/` + `pytest.ini` (escritos contra la API muerta, no
colectaban), `machine_b/`, `notebooks/`, `demo/`, las ablaciones de Mark 42 y 58 corridas de experimentos.

Además: README reescrito según `README_EQUIPO.md` (el anterior describía otra máquina y decía Salamandra en
4 bits); `scripts/prueba_variante.sh` sin rutas absolutas; `.gitignore` al día. Y **la interfaz ya responde
con Mark 44**: `legalrag.cli serve` servía con los valores por defecto (`hybrid=False`, `use_hyde=True`,
`mc_rapido=False`, sin suficiencia), o sea una configuración de Mark 41 distinta de la entregada, lo que
contradecía el §7. `MARKS` vive ahora en `legalrag/config.py` y lo usan tanto `src/main.py` como `serve`.

**Verificado con una corrida completa** (2-oct, 16,1 min, 19,3 s/pregunta): **45,93 · cerradas 14/15 ·
citas 17,96 (recall 0,898) · abstención 9,30**, idéntico a antes del refactor.

### Corrección: el determinismo no es byte a byte, y nunca lo fue

Comparando las dos corridas del 1-oct **entre sí** (ambas anteriores al refactor) ya diferían en el byte
20.386. La causa es `latencia_ms`, que por definición cambia entre corridas. Comparadas campo a campo
ignorando ese campo, las tres corridas (1-oct 20:19, 1-oct 21:10 y 2-oct post-refactor) son **idénticas en las
50 preguntas**: mismas respuestas, justificaciones, citas, pasajes recuperados y abstenciones.

Es decir: el sistema es determinista en todo lo que el §7 exige verificar (normas citadas y pasajes), pero
`md5sum` sobre el `.jsonl` **no** sirve para comprobarlo. Para comparar dos corridas hay que ignorar
`latencia_ms`. La frase anterior de este documento, «las 50 respuestas idénticas entre corridas», era cierta
en contenido y engañosa en bytes.

## Estado

**Mark 44 = 45,93 / 50** en la parte automática de la muestra (Mark 43: 39,77). Validado de punta a punta con
`python3 src/main.py`, determinista (las 50 respuestas idénticas entre corridas) y con 19,0 s de promedio por
pregunta. Es la configuración por defecto de `src/main.py`.

| | Mark 43 | Mark 44 |
|---|---|---|
| Total automático (de 50) | 39,77 | **45,93** |
| Cerradas | 11/15 | 14/15 |
| Citas | 16,73 (recall 0,837) | 17,96 (recall 0,898) |
| Abstención | 8,37 | 9,30 |
| RAGAS≈ local (de 30) | 12,92 | 13,12 |
| Latencia promedio | 17,6 s | 19,0 s |

Entorno: `~/Escritorio/mark/.venv-sistema` (transformers 5.3.0, torch 2.11.0+cu128, ragas 0.4.3). Salida
validada: `salidas/mark44.jsonl` (reporte sin RAGAS: `salidas/mark44_oficial.json`).

## Lo primero mañana: RAGAS con OpenRouter

La corrida `python3 src/main.py --ragas` del 1-oct dio **RAGAS 0,0**: el juez no calificó ninguna de las 35
respuestas (`n_fallidos: 35`) y aun así cobró 0,89 USD. Diagnóstico:

- La llave funciona y quedan ~16 de 20 USD (`python3 scripts/probar_juez.py`).
- Con una sola respuesta, RAGAS sí califica (pregunta 24: 0,55) (`python3 scripts/probar_ragas.py`).
- Hipótesis (sin confirmar): la concurrencia por defecto de RAGAS (16 llamadas simultáneas, 180 s, 10 reintentos).

Arreglo, sin tocar el evaluador oficial (md5 `3a8d274f271042621342dcc61d850697`): `scripts/evaluar_ragas.py`
corre `evaluate.py` tal cual con 4 llamadas simultáneas, 300 s y 3 reintentos, y guarda en caché
(`salidas/ragas_cache.json`) cada calificación exitosa para no pagarla dos veces. `main.py --ragas` ya lo usa.

```bash
cd ~/Escritorio/mark/mark43v2/ai-week-2026-cerberus-mark43
source ~/Escritorio/mark/.venv-sistema/bin/activate
export OPENROUTER_API_KEY="..."
python3 scripts/evaluar_ragas.py salidas/mark44.jsonl     # ~0,9 USD; reporte: salidas/mark44_ragas.json
```

Si quedan fallidos, repetir el mismo comando (solo se pagan esos) o bajar a `--workers 2`. Presupuesto: cuidar
la llave; iterar con RAGAS≈ local (gratis, `scripts/comparar_salidas.py`) y usar el juez solo para medir la
versión final. Referencia a superar: correctness 0,451 (≈13,5 de 30).

## Qué cambió en Mark 44 (todo detrás de opciones de `legalrag.cli run`)

Configuración en `src/main.py` (`MARKS[44]`):

1. **Cerradas en una sola generación** (`--mc-rapido --mc-pensar-tokens 1536`): Qwen3 piensa hasta 1.536 tokens,
   un `LogitsProcessor` fuerza el cierre de `</think>`, la letra se elige con logits float32 y luego genera la
   justificación. Barrido: 768 → 11/15, 1.024 → 12/15, 1.536 → 13/15.
2. **Sin decisiones por reloj** (`--seguridad 90` solo corta generaciones desbocadas): el enunciado exige
   determinismo (§3.1) y que la verificación en vivo reproduzca normas y pasajes (§7). Los 22 s son un
   **promedio** sobre las 992 (§B.5), no un límite por pregunta (las cerradas tardan hasta ~51 s).
3. **Agentes de Cerberus** (`--suficiencia --reformulador-iterativo`, `retrieval/suficiencia.py`): juez de
   contexto suficiente P(«Sí») + reformulador anclado en los 5 primeros pasajes. 42,90 → 44,47.
4. **Citas** (`--encabezado-canonico --reservar-nombradas`): 66 normas con encabezado descriptivo no eran citables;
   reserva de 2 fragmentos para cada norma nombrada en la pregunta (texto libre). 44,47 → 45,11.
5. **Errores corregidos (siempre activos)**: sentencias agregadas sin año (`render`, no contaban como cita);
   orden aleatorio de las citas agregadas entre procesos (`supported_bodies`); el parámetro de tope de tokens que
   la variable local `tokens` pisaba; cerradas sin letra cuando el reloj cortaba. 45,11 → 45,52.
6. **Jurisprudencia primero** (`--preferir-jurisprudencia`) en sub-tareas de precedente/sentido del fallo.
   45,52 → 45,93.
7. Velocidad sin cambiar resultados: índices FAISS en memoria, BM25 en una pasada, memoria del reranker,
   calentamiento. Compatibilidad con transformers 5 (`apply_chat_template` con `return_dict=True`).

## Probado y descartado

- `--jerarquia` (pirámide de Kelsen colombiana en todas las preguntas): 44,47 → 39,14.
- `--jerarquia-condicional` (solo sub-tareas de jerarquía/conflicto, 218 y 563): neutra.
- `--tema-en-reranker`: baja el techo de citas (0,918 → 0,878).
- Citar todas las normas respaldadas: +0,8 que salía de una sola pregunta (453), con ~9 citas de relleno.
- `--cerrar-pensamiento` (regenerar tras el thinking): 12/15 pero ~28 s por cerrada.
- Límite por reloj (`--presupuesto`): cumple el tiempo pero no es determinista.

## Pendiente (implementado, apagado, sin medir completo)

Para intentar pasar de 47 (el equipo de recuperación decide):

- `--consulta-con-tema`: el campo `tema` del banco en la consulta. Techo de citas 0,918 → **0,939** (+247, Ley
  472). Estimado ~46,6. La corrida completa `t12_tema` quedó a medias.
- `--reservar-reformulador`: reserva las normas que nombra el reformulador si el reranker las confirma (≥ 0,5).
  Pensada para la 679 (Ley 1581). Sin probar. Estimado con `tema`: ~47,2.
- Otros: `--normalizador-directo`, `--bm25-sin-vacias`, `--subconsultas-sin-pista`.

Siguen fallando: **128** (la clave del banco, D con «Fintech», no la respalda el corpus; parece error del banco,
no perseguir), **679** (Ley 1581), **253** (CST genérico), **453** (C-468 de 2024 fuera del tope de 6 citas).

Regla usada para aceptar cambios: medir uno a la vez en las 50 y aceptar solo con **0 empeoras**. Mecanismos
generales, nunca reglas por pregunta (el examen son 992 preguntas que no se pueden ajustar). La ganancia en la
muestra es optimista por su tamaño (cada mejora fue de 1 pregunta).

## Para el equipo

- Confirmar por escrito con rf.manrique@uniandes.edu.co que Qwen3-8B (8,19 mil millones de parámetros con
  embeddings) cumple el límite de 8.000 millones.
- El campo `texto` de los pasajes lleva antepuesto el encabezado de procedencia (desde Mark 42); el equipo decidió
  dejarlo así.

## Herramientas

| Script | Para qué |
|---|---|
| `scripts/prueba_variante.sh NOMBRE <flags>` | Una variante en las 50: evaluador oficial, latencias, comparación con Mark 44 y RAGAS≈ |
| `scripts/techo_citas.py "" "opcion=1"` | Techo de citas por configuración, sin generar (~4-7 min cada una) |
| `scripts/comparar_salidas.py A.jsonl B.jsonl` | Cambios pregunta por pregunta y RAGAS≈ local |
| `scripts/evaluar_ragas.py salida.jsonl` | Evaluador oficial con RAGAS, concurrencia baja y caché |
| `scripts/probar_juez.py` / `scripts/probar_ragas.py [--n 5]` | Diagnóstico del juez de OpenRouter (centavos) |

Corridas guardadas en `salidas/` (`t1`…`t12`): la secuencia de pruebas de este documento.
