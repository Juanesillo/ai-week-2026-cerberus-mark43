# Reporte de avance — Hackathon 2026

**Equipo:** P34K  
**Fecha de la medición:** 2 de octubre de 2026, 15:11
**Integrantes:**  Samuel Charry, Shaiel Jimenez, Juan Triviño 
---

## 1. Puntaje sobre las preguntas de muestra

Resultado de `python scripts/evaluate.py --submission mark46.jsonl --split sample`.

| Componente | Puntos obtenidos | Puntos posibles |
|---|---:|---:|
| Exactitud en cerradas | 17,33 | 20 |
| Calidad de citación | 17,96 | 20 |
| Abstención calibrada | 9,07 | 10 |
| **Total automático sin RAGAS** | **44,36** | **50** |



## 2. Estado del corpus

| Métrica | Valor |
|---|---|
| Documentos incorporados | 32.617 |
| Fragmentos indexados | 1.406.293 |
| Áreas del banco con cobertura | 10 de 10 |
| Áreas del banco sin cobertura | Ninguna |

Fuentes consultadas: Corte Constitucional (relatoría), Secretaría General del Senado (base documental), DIAN
(normograma), Corte Suprema de Justicia (relatorías civil, laboral y penal), Consejo de Estado (relatoría),
Superintendencia Financiera, Superintendencia de Sociedades, Función Pública (gestor normativo) y Colpensiones.

## 3. Arquitectura actual

| Componente | Elección |
|---|---|
| Encoder | BAAI/bge-m3 |
| Decoder | Qwen/Qwen3-8B (bf16, temperatura 0) |
| Estrategia de recuperación | Híbrida BM25 + densa (FAISS), fusión RRF, reranker BAAI/bge-reranker-v2-m3 ponderado por la jerarquía normativa colombiana, y segunda búsqueda reformulada solo cuando la evidencia es insuficiente |
| Segmentación del corpus | Artículo completo como unidad citable, más ventanas de 512 tokens con solapamiento de 64 y encabezado jurídico |
| Mecanismo de abstención | Abstención cuando no hay evidencia; toda norma citada se verifica contra los pasajes recuperados y se elimina si no tiene respaldo |

## 4. Riesgos identificados

1. **Tiempo.** 992 preguntas en ~6 h exigen ~22 s de promedio; medimos 19,5 s. La iteración extra solo se activa con
   evidencia insuficiente, sin decisiones por reloj para conservar el determinismo.
2. **Calidad del texto libre.** RAGAS de 13,42/30: en parte de las preguntas la norma aplicable está en los pasajes y la
   respuesta no la usa. Validamos ajustes de redacción por tipo de sub-tarea, sin costo de tiempo.
3. **Tamaño del decoder.** Qwen3-8B suma 8,19 mil millones de parámetros contando los embeddings; solicitamos confirmar
   que cumple el §3.1.
