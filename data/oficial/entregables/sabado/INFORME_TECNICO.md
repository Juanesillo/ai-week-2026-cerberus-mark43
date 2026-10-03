# Informe técnico — <Nombre del equipo>

**Hackathon 2026 · Universidad de los Andes**
**Integrantes:**

Máximo 3 páginas al exportar a PDF. Se entrega como `informe/INFORME_TECNICO.pdf`.

---

## 1. Arquitectura del sistema

Descripción del recorrido de una pregunta desde la entrada hasta la respuesta
entregada, con los componentes que intervienen en cada etapa.

<!-- Un diagrama o una descripción de las etapas: ingesta, indexación,
     recuperación, generación y verificación de citas. -->

## 2. Selección de encoder y decoder

| Componente | Modelo | Motivo de la elección | Alternativas descartadas |
|---|---|---|---|
| Encoder | | | |
| Decoder | | | |
| Reranker | | | |

Configuración de inferencia: cuantización, ventana de contexto, temperatura y
tiempo medio por pregunta.

## 3. Estrategia de recuperación

Criterio de segmentación, tamaño de los fragmentos, tipo de índice, valor de
top-k y uso de recuperación léxica o híbrida.

## 4. Verificación de citas y abstención

Cómo comprueba el sistema que cada norma citada figura en la evidencia
recuperada, y bajo qué condición declara la abstención.

## 5. Resultados sobre las preguntas de muestra

| Componente | Puntos | Posibles |
|---|---:|---:|
| Exactitud en cerradas | | 20 |
| Calidad de citación | | 20 |
| Abstención calibrada | | 10 |
| **Total automático sin RAGAS** | | **50** |

Análisis de los errores más frecuentes:

## 6. Limitaciones

Las limitaciones que el propio equipo identifica en el sistema. Su
identificación precisa se valora por encima de la presentación del sistema como
solución infalible.

1.
2.
3.
