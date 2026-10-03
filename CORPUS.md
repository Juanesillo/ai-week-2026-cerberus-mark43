# Bitácora del corpus — Cerberus

Corpus jurídico colombiano construido para la Hackathon 2026. Todas las cifras de este
documento salen de `corpus_manifest.json` (generado el 2026-10-01T23:19:54Z, estado
`auditado`, licencia `CC-BY-4.0`) y son reproducibles con el flujo de la sección Método.

| Medida | Valor |
|---|---:|
| Documentos incorporados | 32.617 |
| — núcleo (indexado como evidencia citable) | 22.253 |
| — complementario | 10.364 |
| Fuentes distintas | 25 |
| Artículos identificados | 199.896 |
| Documentos segmentados por artículo | 6.318 |
| Texto procesado | 2.041.871.828 caracteres (~2,04 GB) |
| Rango de expedición | 1873 – 2026 |
| Fechas de consulta | 2026-09-28 a 2026-10-01 |
| Documentos con SHA-256 del original | 32.617 (100 %) |
| Aptos para búsqueda | 32.609 (8 excluidos por extracción no utilizable) |

## 1. Inventario

El registro **por documento** vive en `corpus_manifest.json`, en la raíz del repositorio:
un objeto por documento dentro de la llave `documentos`. Cada registro trae los campos que
exige el §5 Paso 5 del enunciado —`doc_id`, `titulo`, `fuente`, `url`, `fecha_consulta`,
`areas`— presentes y no vacíos en los 32.617 registros, más `n_articulos`, `caracteres`,
`tipo`, `numero`, `anio`, `organo_emisor`, `vigencia`, `sha256`, `licencia_fuente` y
`nivel`. No se publica aquí la lista completa porque son 32.617 entradas; el manifiesto es
el inventario y este documento lo resume.

### Por fuente

| Fuente | Documentos |
|---|---:|
| Corte Constitucional | 7.973 |
| DIAN — Normograma | 7.546 |
| Secretaría General del Senado — Base documental | 6.889 |
| Corte Constitucional — Relatoría | 5.369 |
| Corte Suprema de Justicia — Relatoría | 1.196 |
| Superintendencia Financiera de Colombia | 1.071 |
| Corte Suprema de Justicia | 661 |
| Corte Suprema de Justicia — Relatoría Penal | 499 |
| Función Pública — Gestor Normativo | 469 |
| Departamento Administrativo de la Función Pública — Gestor Normativo | 281 |
| Superintendencia de Sociedades | 274 |
| Colpensiones — Normativa | 156 |
| Consejo de Estado — Relatoría | 130 |
| Colpensiones — Compilación normativa | 50 |
| DIAN — Compilación jurídica | 21 |
| Ministerio de Relaciones Exteriores — Compilación jurídica | 18 |
| Superintendencia de Industria y Comercio — Sede electrónica | 6 |
| Otras 8 fuentes con un documento cada una | 8 |

Las ocho restantes: Rama Judicial — SIDN, Cancillería — Compilación jurídica, Comisión de
Regulación de Agua Potable y Saneamiento Básico, DIAN, Ministerio de Salud, ICBF,
Superintendencia de Industria y Comercio y Superservicios — Normograma.

Todas son fuentes públicas y de libre distribución, dentro de las admitidas por el §5 Paso 5.

### Por tipo de documento

| Tipo | Documentos |
|---|---:|
| Sentencia | 19.498 |
| Concepto | 6.359 |
| Decreto | 3.091 |
| Ley | 2.894 |
| Resolución | 271 |
| Compendio | 240 |
| Auto | 178 |
| Acto legislativo | 66 |
| Circular | 15 |
| Decisión, acuerdo, constitución, memorando | 5 |

### Por área del banco

Un documento puede responder a varias áreas, así que la suma excede el total. La columna
de la derecha es el peso de cada área en el banco de 1.042 ítems (§4.2 del enunciado).

| Área | Documentos del corpus | Ítems del banco |
|---|---:|---:|
| Constitucional | 17.369 | 134 |
| Tributario | 8.417 | 92 |
| Laboral | 6.938 | 87 |
| Administrativo | 5.982 | 124 |
| Procesal | 5.415 | 111 |
| Penal | 3.773 | 123 |
| Familia | 3.601 | 93 |
| Civil | 2.555 | 102 |
| Comercial y sociedades | 2.455 | 104 |
| Mercados (competencia, consumidor, datos, PI) | 1.734 | 72 |

## 2. Criterio

**La selección se ordenó por la composición del banco, no por volumen disponible.** Las
diez áreas del §4.2 están cubiertas, y ninguna quedó sin fuente normativa primaria. El
banco no cubre derecho ambiental ni internacional, así que esas áreas no se trabajaron.

El corpus está desbalanceado respecto del banco a propósito, por dos razones:

- **Constitucional (17.369 documentos para 134 ítems).** La jurisprudencia constitucional
  es transversal: una sentencia de la Corte sobre debido proceso responde preguntas de
  procesal, penal y administrativo. El área no está sobrerrepresentada, está compartida.
- **Tributario (8.417 documentos para 92 ítems).** El Normograma de la DIAN se incorpora
  completo porque es la fuente que resuelve las preguntas de vigencia temporal y de
  requisitos legales con texto oficial, y separarlo por pertinencia habría costado más
  tiempo del que ahorraba.

Donde la proporción juega en contra —**administrativo, penal, civil y comercial** tienen
menos documentos que su peso en el banco— se priorizó el cuerpo normativo completo
(códigos y leyes marco) sobre la acumulación de jurisprudencia, de modo que la
recuperación encuentre la disposición aplicable aunque no encuentre el precedente.

### Frente a las sub-tareas del banco

El catálogo de sub-tareas del §4.2 guio qué *tipo* de documento hacía falta, no solo de qué
área:

| Sub-tarea | Qué la resuelve en este corpus |
|---|---|
| Existencia normativa, reproducción literal, requisitos y excepciones legales | Leyes, decretos y códigos (5.985 documentos) segmentados por artículo, con el texto oficial literal |
| Jerarquía normativa, conflicto normativo, interpretación sistemática | Constitución, actos legislativos (66) y la ponderación jerárquica del recuperador (`retrieval/kelsen.py`) |
| Sentido del fallo, precedente jurisprudencial, problema jurídico | Sentencias y autos (19.676) de Corte Constitucional, Corte Suprema y Consejo de Estado |
| Autoridad competente, juez que decide | Normativa orgánica de Función Pública y las superintendencias |
| Definición básica, clasificación jurídica, elementos esenciales | Códigos y compendios (240) |
| Vigencia temporal | Campo `vigencia` y `anio` por documento, más el criterio cronológico del recuperador |

La trazabilidad hasta la norma y el artículo —requisito mínimo del §5 Paso 1, sin el cual
el Paso 4 no es realizable— se cumple porque cada fragmento indexado lleva antepuesto su
encabezado jurídico y conserva su `doc_id` hacia el manifiesto.

## 3. Método

### Ingesta

`data/data_raw_oficial.zip` contiene `data/raw/` y `data/oficial/`: es el paquete de
entrada, no el corpus procesado de la entrega. `data/raw/base/` conserva los originales del
inventario inicial (13.945 documentos en `data/raw/base_manifest.json`, más 22 fuentes
registradas en `src/legalrag/ingestion/base_additions.jsonl`). `data/raw/ampliacion/`
conserva los originales descargados, sus catálogos y las páginas HTML de normas divididas.

Cada fuente conserva URL, identificador, fecha de consulta y SHA-256 del archivo
descargado. `prepare` verifica los originales contra ese hash antes de extraer: los 32.617
registros del manifiesto tienen `sha256` y `integridad_originales`.

### Limpieza y extracción

- Los `.doc` requieren LibreOffice o antiword.
- 13 documentos se reconstruyeron desde HTML multipágina (`metodo_extraccion:
  html_multipagina`).
- El OCR está disponible para originales escaneados, con el modelo español de
  [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast/blob/main/spa.traineddata)
  guardado en `data/raw/ocr_model/` bajo su licencia Apache 2.0. En el corpus final
  ningún documento quedó dependiendo de OCR.
- La limpieza para búsqueda no sustituye el pasaje original: se conservan ambos, y lo que
  se cita es el texto citable.

### Segmentación y metadatos

El artículo completo es la unidad citable, más ventanas de búsqueda de 512 *tokens* con
solapamiento de 64, con el encabezado jurídico antepuesto. El artículo es la unidad de
sentido del texto normativo (§B.2), y el encabezado hace que el evaluador reconozca la
norma de procedencia del pasaje.

Las áreas se asignaron por `heuristica_de_terminos_y_catalogo` en 18.650 documentos; en el
resto provienen del catálogo de la fuente. Las sentencias no reciben como artículo propio
las normas que mencionan. Las marcas de vigencia y las anotaciones editoriales permanecen
como metadatos: **ninguna descarga certifica vigencia jurídica**, y 32.616 documentos
quedan como `vigencia: por_verificar`.

### Reconstrucción

```bash
python -m legalrag.cli prepare     # extrae y normaliza los originales de data/raw/
python -m legalrag.cli finalize    # reextrae la ampliación, verifica hashes, resuelve duplicados
python -m legalrag.cli profile     # perfil de calidad y metadatos
python -m legalrag.cli audit --coverage
python -m legalrag.cli index       # FAISS FlatIP + metadatos en index/
```

Salidas en `data/processed/`, `reports/` y `corpus_manifest.json`. Los conteos,
exclusiones y decisiones de cada ejecución quedan en `reports/ampliacion_corpus.json`,
`reports/perfil_resumen.json`, `reports/brechas_corpus.json` y `reports/cobertura.json`.

## 4. Publicación y licencia

El corpus procesado y el índice vectorial **no se versionan en el repositorio** por su
tamaño (§9.3). Se publican en un comprimido que contiene `LICENSE`, `corpus_manifest.json`,
el corpus procesado y el índice serializado.

> **Enlace de descarga:** `<<< PEGAR AQUÍ LA URL DEL COMPRIMIDO >>>`
>
> El mismo enlace debe quedar en la sección «Corpus e índice» del `README.md`.

El manifiesto declara `licencia: CC-BY-4.0` para la selección y el procesamiento. El
procesamiento conserva además la licencia de origen de cada documento en
`licencia_fuente`: los textos jurídicos oficiales se reproducen conforme al art. 41 de la
Ley 23 de 1982, y los derechos sobre notas y edición de terceros no se relicencian. 24.914
documentos están marcados `redistribuir_raw: true`; el resto se redistribuye solo como
texto procesado. El código del repositorio usa MIT (`LICENSE`) y el modelo de OCR conserva
Apache 2.0.
