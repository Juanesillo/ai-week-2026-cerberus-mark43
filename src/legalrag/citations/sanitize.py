"""Saneo y aumento de citas sobre la salida del generador.

Dos operaciones:

- `drop_unsupported`: elimina de cada campo las citas (y oraciones) cuya
  norma no aparece en los pasajes recuperados. El evaluador oficial penaliza
  `citas_sin_respaldo` con el doble del valor de un acierto, asi que un solo
  descuido anula el componente completo.

- `augment`: agrega citas canonicas de las normas que si estan en la evidencia
  pero el modelo omitio. El evaluador no penaliza citas respaldadas que no
  coincidan con el fundamento de referencia, de modo que ampliar aqui solo
  puede subir el recall.

El soporte se calcula con el extractor oficial sobre el texto de los diez
primeros pasajes (lo que el evaluador considera para el respaldo).
"""
from __future__ import annotations

import re
from legalrag.citations.official import bodies, enrich_header, extract, render


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")


def own_bodies(passages: list[dict]) -> set:
    """Normas que SON los pasajes (las del encabezado entre corchetes con que public_passage abre el texto)."""
    found = set()
    for p in passages[:10]:
        texto = str(p.get("texto") or "")
        if texto.startswith("[") and "]" in texto:
            found |= bodies(extract(texto[:texto.index("]") + 1]))
    return found


def supported_bodies(passages: list[dict]) -> set[tuple]:
    """Cuerpos normativos presentes en los primeros 10 pasajes.

    Replica exacta de lo que hace citas_respaldadas() del evaluador oficial.
    El encabezado ya fue enriquecido por public_passage y antepuesto a texto,
    por lo que aqui NO se vuelve a enriquecer: enriquecer el cuerpo expandiria
    aliases que el evaluador no reconoce y permitiria falsos positivos.
    """
    # Orden determinista: por pasaje (ranking) y, dentro de cada pasaje, por el valor del cuerpo. Un set de
    # tuplas de texto cambia de orden entre procesos (PYTHONHASHSEED) y augment_citations elegía otras normas
    # en cada corrida. Las vistas de llaves admiten `in`, `&` y `|` como un set.
    found: dict = {}
    for p in passages[:10]:
        for body in sorted(bodies(extract(str(p.get("texto") or ""))), key=lambda b: tuple(str(x) for x in b)):
            found.setdefault(body, None)
    return found.keys()


def _sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def _clean_sentence(sentence: str, supported: set[tuple]) -> str | None:
    """Devuelve la oracion si todas sus citas estan respaldadas, o None."""
    cites = bodies(extract(sentence))
    unsupported = cites - supported
    if not unsupported:
        return sentence
    return None


def drop_unsupported(text: str, supported: set[tuple]) -> str:
    """Elimina oraciones con citas sin respaldo. Preserva el resto literal."""
    if not text:
        return text
    kept: list[str] = []
    for sentence in _sentences(text):
        cleaned = _clean_sentence(sentence, supported)
        if cleaned is not None:
            kept.append(cleaned)
    return " ".join(kept)


def sanitize_fields(row: dict, supported: set[tuple], formato: str) -> dict:
    """Aplica drop_unsupported a los campos sustantivos segun formato."""
    fields = {
        "multiple_choice": ("justificacion",),
        "semi_open": ("respuesta", "referencia_legal"),
        "open_ended": ("marco_normativo", "analisis", "jurisprudencia", "conclusion"),
    }.get(formato, ())
    for field in fields:
        row[field] = drop_unsupported(row.get(field, ""), supported)
    return row


def _precedente(body: tuple) -> tuple:
    """Orden del precedente vigente (lex posterior aplicada a la jurisprudencia): primero las sentencias con fuerza
    general (control abstracto C, unificación SU, casación SL/SC/SP), después las de tutela y los autos (efectos inter
    partes: T, STC, STL, AC, AU); dentro de cada grupo, de la más reciente a la más antigua."""
    sala = str(body[1] or "").split("-")[0].upper()
    anio = int(body[2]) if str(body[2] or "").isdigit() else 0
    return (int(sala in {"T", "STC", "STL", "AC", "AU"}), -anio)


def augment_citations(row: dict, supported: set[tuple], formato: str,
                      max_norms: int = 6, preferir_jurisprudencia: bool = False, propios=None,
                      reciente: bool = False) -> dict:
    """Agrega citas canonicas de normas respaldadas que aun no se citaron.

    Preferimos las normas que no son jurisprudencia porque el banco penaliza
    con mas peso las sentencias sin respaldo y porque las normas tienen mayor
    recall promedio en el fundamento de referencia (84%).
    """
    present = bodies(extract(_response_text(row, formato)))
    missing = [b for b in supported if b not in present]
    # Prioridad: codigos antes que leyes/decretos; sentencias al final.
    def rank(body: tuple) -> tuple:
        kind = body[0]
        if kind == "jurisprudencia":
            # Mark 44: si la pregunta pide precedente o el sentido de un fallo, la jurisprudencia va primero.
            if preferir_jurisprudencia and reciente:
                return (-1,) + _precedente(body)
            return (-1,) if preferir_jurisprudencia else (2,)
        if kind in {"constitucion", "codigo_civil", "codigo_penal",
                    "codigo_comercio", "codigo_sustantivo_trabajo",
                    "codigo_general_proceso", "cpaca", "estatuto_tributario",
                    "codigo_procedimiento_penal", "codigo_infancia",
                    "codigo_disciplinario", "estatuto_consumidor",
                    "codigo_nacional_policia"}:
            return (0,)
        return (1,)
    if propios:
        # Primero las normas que SON los pasajes recuperados (su encabezado) y después las que esos pasajes solo
        # mencionan: un oficio que cita seis sentencias llenaba los cupos y dejaba fuera las sentencias recuperadas.
        missing.sort(key=lambda b: (b not in propios,) + rank(b))
    else:
        missing.sort(key=rank)
    missing = missing[:max_norms]
    if not missing:
        return row
    extras = "; ".join(render(b) for b in missing)
    if formato == "multiple_choice":
        base = row.get("justificacion") or ""
        row["justificacion"] = (base + f" Fundamento normativo adicional recuperado: {extras}.").strip()
    elif formato == "semi_open":
        base = (row.get("referencia_legal") or "").strip()
        row["referencia_legal"] = (f"{base}; {extras}".strip("; ")).strip()
    else:  # open_ended
        base = (row.get("marco_normativo") or "").strip()
        row["marco_normativo"] = (f"{base}; {extras}".strip("; ")).strip()
    return row


def _response_text(row: dict, formato: str) -> str:
    if formato == "multiple_choice":
        return row.get("justificacion") or ""
    if formato == "semi_open":
        return " ".join(str(row.get(k) or "") for k in ("respuesta", "referencia_legal"))
    return " ".join(str(row.get(k) or "")
                    for k in ("marco_normativo", "analisis", "jurisprudencia", "conclusion"))


def ensure_min_text(row: dict, formato: str) -> dict:
    """Rellena campos vacios con una frase neutra respaldable por evidencia.

    Despues de sanear, un campo requerido no puede quedar en blanco (el schema
    oficial lo exige). El relleno no agrega citas.
    """
    neutral = "Fundamento inferido a partir de la evidencia recuperada."
    required = {
        "multiple_choice": ("justificacion",),
        "semi_open": ("respuesta", "referencia_legal"),
        "open_ended": ("marco_normativo", "analisis", "jurisprudencia", "conclusion"),
    }[formato]
    for field in required:
        if not (row.get(field) or "").strip():
            if field == "jurisprudencia":
                row[field] = "No se cita jurisprudencia por falta de respaldo en la evidencia."
            else:
                row[field] = neutral
    return row
