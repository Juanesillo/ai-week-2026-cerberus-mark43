# Entrega del sábado — entrega final

**Plazo:** sábado, 15:00
**Canal:** repositorio del equipo (GitHub o GitLab), con el corpus y el índice
vectorial depositados en un servicio en la nube y enlazados desde el `README`.

## Estructura esperada del repositorio

```
<repositorio del equipo>/
├── README.md                  # plantilla en README_EQUIPO.md
├── LICENSE
├── requirements.txt
├── submissions.jsonl          # 992 respuestas, esquema oficial
├── CORPUS.md                  # bitácora, plantilla en CORPUS.md
├── corpus_manifest.json       # plantilla en corpus_manifest.ejemplo.json
├── informe/
│   └── INFORME_TECNICO.pdf    # máximo 3 páginas
├── interfaz/                  # código de la interfaz gráfica
└── src/                       # pipeline reproducible
```

El corpus procesado, el índice vectorial y el video **no se versionan en el
repositorio**. Se depositan en la nube y se enlazan desde el `README`.

## Los ocho entregables

| N.º | Entregable | Ubicación |
|---|---|---|
| 2 | Repositorio con `README` que documente dependencias, arquitectura y comando único de reproducción | Repositorio |
| 3 | `submissions.jsonl` con las 992 respuestas conforme al esquema oficial | Repositorio |
| 4 | `CORPUS.md` y `corpus_manifest.json` | Repositorio |
| 5 | Corpus enriquecido e índice vectorial, bajo licencia abierta | Nube, enlazado en el `README` |
| 6 | Informe técnico de máximo 3 páginas | Repositorio |
| 7 | Video de máximo 5 minutos | Repositorio o nube |
| 8 | Interfaz gráfica funcional, inspirada en la identidad visual de Software Colombia | Repositorio |

El entregable 1 es el reporte de avance del viernes.

## Publicación del corpus y del índice vectorial

El corpus y el índice no caben en un repositorio de código, así que se depositan
en un servicio de almacenamiento (Google Drive, OneDrive, Dropbox, Zenodo u otro
equivalente). El enlace se declara en el `README` del repositorio, bajo una
sección titulada `## Corpus e índice`.

El enlace debe cumplir tres condiciones.

1. Permitir la descarga sin solicitud de permiso adicional, con acceso de
   lectura para cualquier persona que disponga del vínculo.
2. Permanecer activo durante los treinta días siguientes al evento, plazo en el
   que el jurado verifica la reproducibilidad.
3. Apuntar a un archivo comprimido con la siguiente estructura.

```
corpus_<nombre_del_equipo>.zip
├── LICENSE                    # licencia abierta escogida por el equipo
├── corpus_manifest.json       # copia del manifiesto del repositorio
├── corpus/                    # documentos procesados, un archivo por norma
│   ├── ley_1564_2012.txt
│   └── ...
└── indice/                    # índice vectorial serializado
    ├── index.faiss            # o el formato del motor que usen
    └── chunks.jsonl           # fragmentos con doc_id, offsets y metadatos
```

Un enlace inaccesible en el momento de la calificación equivale a la ausencia
del entregable correspondiente. Conviene verificarlo desde una sesión privada
del navegador antes de las 15:00.

## Entrega de referencia

La carpeta [`Ejemplo de entrega/`](../../Ejemplo%20de%20entrega/) contiene un
`submissions.jsonl`, un `CORPUS.md` y un `corpus_manifest.json` ya diligenciados
con cinco de las cincuenta preguntas de muestra, incluido un caso de abstención.

## Plantillas de esta carpeta

| Archivo | Para qué sirve |
|---|---|
| [`README_EQUIPO.md`](README_EQUIPO.md) | Plantilla del `README` del repositorio |
| [`CORPUS.md`](CORPUS.md) | Plantilla de la bitácora del corpus |
| [`corpus_manifest.ejemplo.json`](corpus_manifest.ejemplo.json) | Ejemplo del manifiesto |
| [`INFORME_TECNICO.md`](INFORME_TECNICO.md) | Plantilla del informe técnico |

## Verificación antes de las 15:00

- [ ] `submissions.jsonl` valida contra `schema/submission.schema.json`.
- [ ] `python scripts/evaluate.py --submission submissions.jsonl --split sample` corre sin errores de validación.
- [ ] El índice quedó congelado y no se modifica después de la entrega.
- [ ] La temperatura del decoder está en 0.
- [ ] El `README` tiene la sección `## Corpus e índice` con el enlace.
- [ ] El enlace abre desde una sesión privada del navegador, sin pedir permisos.
- [ ] El comprimido incluye `LICENSE`.
- [ ] La interfaz gráfica corre en el equipo del grupo.
- [ ] El repositorio es accesible para el jurado.
