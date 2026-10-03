# Entrega del viernes — reporte de avance

**Plazo:** viernes, 17:00
**Canal:** correo electrónico a `rf.manrique@uniandes.edu.co`
**Asunto:** `[Hackathon 2026] Avance — <nombre del equipo>`
**Adjunto:** un único archivo `REPORTE_AVANCE.pdf`, de una página

## Qué debe contener

El reporte ocupa una página y responde cuatro puntos, en este orden.

1. **Puntaje sobre las preguntas de muestra.** El resultado de correr el
   evaluador oficial sobre las 50 preguntas de muestra, con la fecha de la
   medición.

   ```bash
   python scripts/evaluate.py --submission entrega.jsonl --split sample
   ```

2. **Estado del corpus.** Número de documentos incorporados, áreas del banco
   que cubren y fuentes consultadas.

3. **Arquitectura actual.** Encoder, decoder y estrategia de recuperación
   elegidos hasta el momento.

4. **Riesgos identificados.** Los obstáculos que el equipo prevé para el sábado
   y cómo piensa abordarlos.

La plantilla [`REPORTE_AVANCE.md`](REPORTE_AVANCE.md) contiene esa estructura.
El equipo la completa y la exporta a PDF.

## Qué se evalúa

El reporte del viernes es un punto de control, no un componente de la
calificación de 100 puntos. Su ausencia sí se registra, y el equipo pierde la
retroalimentación previa a la jornada del sábado.

## Verificación antes de enviar

- [ ] El archivo se llama `REPORTE_AVANCE.pdf`.
- [ ] Ocupa una página.
- [ ] Incluye el nombre del equipo y los tres integrantes.
- [ ] Incluye el puntaje obtenido con `evaluate.py` y la fecha de la medición.
- [ ] El asunto del correo sigue el formato indicado arriba.
