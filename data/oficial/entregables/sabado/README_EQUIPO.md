# <Nombre del equipo> — Hackathon 2026

**Integrantes:**
**Universidad de los Andes**

Sistema de respuesta a preguntas de derecho colombiano con un modelo abierto de
tamaño reducido y un corpus jurídico propio.

## Corpus e índice

<!-- OBLIGATORIO. El jurado descarga desde aquí. Verificar el enlace desde una
     sesión privada del navegador antes de las 15:00. -->

| Recurso | Enlace | Tamaño | Licencia |
|---|---|---|---|
| Corpus procesado e índice vectorial | `<URL>` | | |

El comprimido contiene `LICENSE`, `corpus_manifest.json`, `corpus/` con los
documentos procesados e `indice/` con el índice serializado y los fragmentos.

El enlace permanece activo hasta el `<fecha, treinta días después del evento>`.

## Arquitectura

| Componente | Elección | Motivo |
|---|---|---|
| Encoder | | |
| Decoder | | |
| Segmentación | | |
| Recuperación | | |
| Reordenamiento | | |
| Mecanismo de abstención | | |

## Reproducción

Un único comando reconstruye el índice y genera la entrega.

```bash
pip install -r requirements.txt
bash run.sh            # o: python src/main.py --split sample
```

Requisitos de hardware:

Tiempo estimado sobre las 50 preguntas de muestra:

## Resultados sobre las preguntas de muestra

| Componente | Puntos | Posibles |
|---|---:|---:|
| Exactitud en cerradas | | 20 |
| Calidad de citación | | 20 |
| Abstención calibrada | | 10 |

## Interfaz gráfica

Cómo ejecutarla:

```bash
```

## Limitaciones conocidas

1.
2.
3.
