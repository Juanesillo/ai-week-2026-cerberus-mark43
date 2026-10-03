# Ejemplo de entrega

Entrega de referencia con **cinco de las cincuenta preguntas de muestra** que se
entregan a los equipos. Todos los textos de respuesta y de los pasajes llevan la
marca `TEXTO DE EJEMPLO` y las cifras son ficticias. El propósito es mostrar el
formato exacto y el nivel de detalle esperado.

## Contenido

| Archivo | Qué ilustra |
|---|---|
| [`submissions.jsonl`](submissions.jsonl) | Las cinco respuestas en el esquema oficial |
| [`CORPUS.md`](CORPUS.md) | La bitácora del corpus con sus cinco secciones |
| [`corpus_manifest.json`](corpus_manifest.json) | El manifiesto de los ocho documentos del corpus |

## Los cinco ítems

Cubren los tres formatos y los tres niveles de complejidad.

| id | Formato | Complejidad | Área | Qué ilustra |
|---|---|---|---|---|
| 51 | `multiple_choice` | — | Constitucional | Respuesta cerrada con `descarte_opciones` y tres pasajes de respaldo |
| 79 | `semi_open` | baja | Laboral | Respuesta breve con `referencia_legal` y `palabras_clave` |
| 140 | `semi_open` | media | Comercial y sociedades | Citación de jurisprudencia respaldada por la evidencia |
| 218 | `semi_open` | alta | Administrativo | **Abstención**: campos vacíos, `abstencion: true` y evidencia insuficiente |
| 253 | `open_ended` | — | Laboral | Análisis casuístico con los cuatro campos del formato abierto |

## Puntos que conviene observar

**Toda norma citada aparece en los pasajes recuperados.** El texto de cada pasaje
comienza con el nombre completo de la norma de la que procede. Sin ese dato el
evaluador no puede ligar la cita con la evidencia, y el respaldo de las
citaciones queda en cero aunque la recuperación haya sido correcta. Sobre este
ejemplo, las 7 normas citadas se clasifican como respaldadas.

**El ítem 218 se abstiene.** El sistema recuperó un pasaje con un puntaje de
similitud bajo, insuficiente para resolver un conflicto normativo entre la
Constitución y una ley. Los campos de contenido quedan como cadena vacía, la
bandera `abstencion` queda en `true` y los pasajes recuperados se conservan, lo
que permite al jurado verificar la decisión.

**Los pasajes traen offsets y puntaje.** Los campos `inicio`, `fin` y `score`
hacen trazable cada fragmento hasta su posición en el documento original.

## Verificación

```bash
cd "Hackathon/2026"
python scripts/evaluate.py --submission "Ejemplo de entrega/submissions.jsonl" --split sample
```

El evaluador reporta un error de validación, porque faltan 45 de los 50 ítems del
split. Es el comportamiento esperado en una entrega parcial de cinco preguntas.
Sobre los cinco ítems presentes, el reporte muestra 7 aciertos de citación, los 7
respaldados por la evidencia y ninguna cita sin respaldo.

Una entrega real debe traer las 992 respuestas del conjunto de evaluación.
