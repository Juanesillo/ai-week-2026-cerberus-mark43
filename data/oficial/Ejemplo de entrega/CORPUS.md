# Bitácora del corpus — Equipo Ejemplo

> **Documento de ejemplo.** Las cifras y los textos son ficticios y sirven
> únicamente para mostrar el nivel de detalle esperado. Corresponde a una entrega
> reducida de cinco preguntas, no a una entrega completa.

---

## 1. Inventario

| doc_id | Título | Fuente | URL | Fecha de consulta | Artículos | Fragmentos | Áreas |
|---|---|---|---|---|---:|---:|---|
| `constitucion_politica_1991` | Constitución Política de Colombia de 1991 | Secretaría del Senado | [enlace](http://www.secretariasenado.gov.co/senado/basedoc/constitucion_politica_1991.html) | 2026-09-14 | 380 | 380 | Constitucional, Administrativo |
| `ley_472_1998` | Ley 472 de 1998, acciones populares y de grupo | Secretaría del Senado | [enlace](http://www.secretariasenado.gov.co/senado/basedoc/ley_0472_1998.html) | 2026-09-14 | 88 | 88 | Constitucional, Procesal |
| `ley_1010_2006` | Ley 1010 de 2006, acoso laboral | Secretaría del Senado | [enlace](http://www.secretariasenado.gov.co/senado/basedoc/ley_1010_2006.html) | 2026-09-15 | 20 | 20 | Laboral |
| `ley_1562_2012` | Ley 1562 de 2012, riesgos laborales | Secretaría del Senado | [enlace](http://www.secretariasenado.gov.co/senado/basedoc/ley_1562_2012.html) | 2026-09-15 | 32 | 32 | Laboral |
| `codigo_sustantivo_trabajo` | Código Sustantivo del Trabajo | Secretaría del Senado | [enlace](http://www.secretariasenado.gov.co/senado/basedoc/codigo_sustantivo_trabajo.html) | 2026-09-15 | 493 | 493 | Laboral |
| `ley_1676_2013` | Ley 1676 de 2013, garantías mobiliarias | Secretaría del Senado | [enlace](http://www.secretariasenado.gov.co/senado/basedoc/ley_1676_2013.html) | 2026-09-16 | 91 | 91 | Comercial y sociedades |
| `sentencia_c_145_2018` | Sentencia C-145 de 2018 | Relatoría de la Corte Constitucional | [enlace](https://www.corteconstitucional.gov.co/relatoria/2018/C-145-18.htm) | 2026-09-16 | — | 214 | Comercial, Constitucional |
| `sentencia_sl3385_2022` | Sentencia SL3385-2022 | Relatoría de la Corte Suprema | [enlace](https://www.cortesuprema.gov.co/relatoria/EJEMPLO-SL3385-2022) | 2026-09-16 | — | 424 | Laboral |

**Totales**

| Métrica | Valor |
|---|---:|
| Documentos incorporados | 8 |
| Artículos indexados | 1.104 |
| Fragmentos en el índice | 1.742 |
| Tamaño del corpus procesado | 14,3 MB |
| Tamaño del índice vectorial | 7,1 MB |

## 2. Criterio de selección

La selección se dirigió a las áreas de las cinco preguntas trabajadas en este
ejemplo, siguiendo la composición del banco publicada en la sección 4.2 del
enunciado.

| Área | Ítems en el banco | Documentos incorporados | Cobertura estimada |
|---|---:|---:|---|
| Derecho constitucional | 134 | 3 | Parcial. Constitución y dos sentencias; falta jurisprudencia de tutela. |
| Derecho administrativo | 124 | 1 | Baja. Solo la Constitución; falta la Ley 1437 de 2011. |
| Derecho penal | 123 | 0 | Sin cobertura en este ejemplo. |
| Derecho procesal | 111 | 1 | Baja. Falta el Código General del Proceso. |
| Derecho comercial y sociedades | 104 | 2 | Parcial. Garantías mobiliarias; falta el Código de Comercio. |
| Derecho civil | 102 | 0 | Sin cobertura en este ejemplo. |
| Derecho de familia | 93 | 0 | Sin cobertura en este ejemplo. |
| Derecho tributario | 92 | 0 | Sin cobertura en este ejemplo. |
| Derecho laboral | 87 | 3 | Buena. CST, Ley 1562 y jurisprudencia de casación. |
| Derecho de los mercados | 72 | 0 | Sin cobertura en este ejemplo. |

**Documentos descartados.** Se consideró incorporar el Diario Oficial completo y
se descartó por volumen frente al beneficio esperado. Las circulares de la
Superintendencia de Sociedades se dejaron para una segunda iteración, porque el
banco las cita con poca frecuencia.

## 3. Método de ingesta y limpieza

1. **Descarga.** Peticiones HTTP a las URL declaradas, con registro de la fecha
   y del código de respuesta. Los documentos de la Secretaría del Senado llegan
   en HTML; las sentencias de la Corte Suprema, en PDF.
2. **Extracción de texto.** `BeautifulSoup` para el HTML, con eliminación de los
   elementos de navegación, encabezados y publicidad. `pdfplumber` para los PDF
   con capa de texto y `tesseract` en español para los escaneados.
3. **Normalización.** Conversión a UTF-8, unificación de comillas y guiones,
   colapso de espacios y eliminación de los saltos de línea internos a un mismo
   párrafo.
4. **Segmentación.** Corte por expresión regular sobre el patrón
   `ART[IÍ]CULO\s+\d+`, conservando el encabezado del artículo dentro del
   fragmento. Las sentencias se segmentan por párrafo, con solapamiento de dos
   frases entre fragmentos contiguos.
5. **Extracción de metadatos.** Cada fragmento conserva `doc_id`, tipo de norma,
   número, año, número de artículo, órgano emisor y offsets en el documento
   original.
6. **Indexación.** `intfloat/multilingual-e5-large` con el prefijo `passage: `,
   vectores normalizados a longitud unitaria e índice `faiss.IndexFlatIP` de
   1.024 dimensiones.

**Problemas encontrados.** El OCR de la Sentencia SL3385-2022 confundió de forma
sistemática los caracteres `1` y `l` en las citas normativas, lo que rompía la
extracción de referencias; se corrigió con una regla de sustitución aplicada
únicamente dentro de los patrones de citación. El Código Sustantivo del Trabajo
presenta artículos derogados intercalados con los vigentes, así que cada
fragmento lleva una bandera `vigente` derivada de las notas de la fuente.

**Decisión sobre el encabezado de los fragmentos.** Cada fragmento comienza con
el nombre completo de la norma de la que procede. Sin ese dato, el evaluador no
puede ligar una cita de la respuesta con el pasaje recuperado, y el respaldo de
las citaciones queda en cero aunque la recuperación haya sido correcta.

## 4. Evolución del puntaje

Medición sobre las 50 preguntas de muestra con `scripts/evaluate.py`, sin RAGAS.

| Fecha | Documentos | Fragmentos | Cerradas /20 | Citación /20 | Abstención /10 | Total /50 | Qué cambió |
|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-14 | 2 | 468 | 6,67 | 1,21 | 3,40 | 11,28 | Corpus inicial: Constitución y Ley 472 |
| 2026-09-15 | 5 | 1.013 | 9,33 | 4,86 | 5,10 | 19,29 | Bloque laboral: CST, Ley 1562, Ley 1010 |
| 2026-09-16 | 8 | 1.742 | 12,00 | 8,43 | 6,20 | 26,63 | Jurisprudencia y garantías mobiliarias |

**Lectura de la curva.** El salto mayor en calidad de citación ocurrió al
incorporar la jurisprudencia, porque el `legal_basis` de varias preguntas
semiabiertas apunta a sentencias y no a normas. La incorporación del bloque
laboral mejoró sobre todo la abstención, dado que el sistema dejó de declarar
falta de fundamento en un área que antes no tenía cobertura. La exactitud en
preguntas cerradas crece más despacio, porque depende también del razonamiento
del decoder y no solo de la disponibilidad de la fuente.

## 5. Licencia

El corpus se publica bajo **CC-BY-4.0**. Los textos normativos colombianos son
de dominio público; la licencia cubre el trabajo de procesamiento, segmentación,
corrección de OCR y extracción de metadatos realizado por el equipo.

## 6. Enlace al corpus e índice

| Recurso | Enlace | Tamaño | Vigencia |
|---|---|---|---|
| `corpus_equipo_ejemplo.zip` | `https://drive.google.com/file/d/EJEMPLO-NO-FUNCIONAL/view?usp=sharing` | 21,4 MB | Hasta 2026-10-18 |

El comprimido contiene `LICENSE`, `corpus_manifest.json`, `corpus/` con los ocho
documentos procesados e `indice/` con `index.faiss` y `chunks.jsonl`.
