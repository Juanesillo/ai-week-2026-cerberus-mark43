"""Verificación en vivo (§7) por adelantado: ¿dos corridas del mismo sistema dan las mismas respuestas?

    python3 scripts/determinismo.py salidas/mark46_base_usuario.jsonl salidas/mark46.jsonl

El jurado regenera 2 o 3 preguntas y exige que coincidan las normas citadas y los pasajes recuperados. Aquí se comparan
las dos corridas pregunta por pregunta en todos los campos menos `latencia_ms` (que cambia en cada corrida por
definición), y se detalla qué difiere: pasajes (doc_id, inicio, fin, texto), normas citadas (extractor del evaluador
oficial) o solo la redacción.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "data/oficial/scripts"))
import citations  # noqa: E402  (extractor de citas del evaluador oficial, solo lectura)

CAMPOS_TEXTO = ("respuesta", "referencia_legal", "marco_normativo", "analisis", "jurisprudencia", "conclusion",
                "justificacion", "respuesta_correcta", "descarte_opciones", "palabras_clave")


def cargar(ruta):
    return {r["id"]: r for r in (json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip())}


def normas(r):
    texto = " ".join(str(r.get(k) or "") for k in CAMPOS_TEXTO)
    return citations.bodies(citations.extract(texto))


def pasajes(r):
    return [(p.get("doc_id"), p.get("inicio"), p.get("fin"), p.get("texto")) for p in r.get("pasajes_recuperados") or []]


def main():
    a, b = cargar(sys.argv[1]), cargar(sys.argv[2])
    ids = sorted(set(a) | set(b))
    identicas, solo_redaccion, distintas = 0, [], []
    for i in ids:
        if i not in a or i not in b:
            distintas.append((i, "falta en una corrida"))
            continue
        ra = {k: v for k, v in a[i].items() if k != "latencia_ms"}
        rb = {k: v for k, v in b[i].items() if k != "latencia_ms"}
        if ra == rb:
            identicas += 1
        elif pasajes(a[i]) == pasajes(b[i]) and normas(a[i]) == normas(b[i]):
            solo_redaccion.append(i)
        else:
            motivo = []
            if pasajes(a[i]) != pasajes(b[i]):
                motivo.append("pasajes")
            if normas(a[i]) != normas(b[i]):
                motivo.append("normas citadas")
            distintas.append((i, " y ".join(motivo)))
    print(f"{len(ids)} preguntas: {identicas} idénticas (salvo latencia), {len(solo_redaccion)} con las mismas normas y "
          f"pasajes pero otra redacción, {len(distintas)} con normas o pasajes distintos")
    if solo_redaccion:
        print("  solo redacción (el §7 lo admite):", solo_redaccion)
    for i, motivo in distintas:
        print(f"  ✗ {i}: difieren {motivo}")
    print("Veredicto §7:", "APRUEBA" if not distintas else "REVISAR: el jurado exige mismas normas y pasajes")


if __name__ == "__main__":
    main()
