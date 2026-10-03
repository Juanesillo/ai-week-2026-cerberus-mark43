"""Mark 44 (de Cerberus Mark 3 y 4): búsqueda bajo demanda.

1. Juicio de contexto suficiente (Joren et al., ICLR 2025): el mismo decoder mira los primeros pasajes y se mide
   P(«Sí») a «¿bastan para responder?», sin generar texto. Si no bastan, se dispara la segunda búsqueda.
2. Reformulador anclado en la evidencia (ITER-RETGEN, Shao et al., 2023): una respuesta breve escrita con esos
   pasajes a la vista, que nombra la figura y las normas, se usa como nueva consulta. Pedir las normas de memoria
   falló en Cerberus: Qwen3-8B nombraba leyes que no aplican o no existen.
"""
from __future__ import annotations

SISTEMA_SUFICIENCIA = ("Eres un abogado colombiano que decide si unos pasajes bastan para responder una pregunta "
                       "jurídica con fundamento. Respondes solo «Sí» o «No».")

SISTEMA_ITERATIVO = ("Eres un abogado colombiano. Con unos pasajes de una primera búsqueda, escribes una respuesta "
                     "breve que sirva para buscar mejor evidencia.")


def bloque_pasajes(pasajes, max_caracteres=600):
    return "\n\n".join(f"[E{i}] {p.get('encabezado') or ''}\n{(p.get('texto') or '')[:max_caracteres]}"
                       for i, p in enumerate(pasajes, 1))


def _pregunta(question):
    opciones = question.get("opciones")
    if isinstance(opciones, dict) and opciones:
        return question["pregunta"].strip() + "\n" + "\n".join(f"{k}) {v}" for k, v in opciones.items())
    return question["pregunta"].strip()


def mensajes_suficiencia(question, pasajes):
    return [{"role": "system", "content": SISTEMA_SUFICIENCIA},
            {"role": "user", "content": (
                f"PASAJES\n{bloque_pasajes(pasajes)}\n\nPREGUNTA ({question.get('area') or ''})\n{_pregunta(question)}"
                "\n\n¿Los pasajes contienen la norma o la información jurídica necesaria para responder la pregunta "
                "con fundamento? Responde solo «Sí» o «No».")}]


def mensajes_iterativo(question, pasajes):
    return [{"role": "system", "content": SISTEMA_ITERATIVO},
            {"role": "user", "content": (
                f"PASAJES DE UNA PRIMERA BÚSQUEDA\n{bloque_pasajes(pasajes)}\n\nPREGUNTA ({question.get('area') or ''})"
                f"\n{_pregunta(question)}\n\nCon base en esos pasajes, responde en máximo tres oraciones y nombra la "
                "figura jurídica y las normas colombianas que regulan el caso (tipo, número y año, y el artículo si "
                "aparece). Si los pasajes no bastan, nombra la figura jurídica que habría que buscar.")}]


def suficiencia(question, pasajes, generator):
    return generator.probabilidad_si(mensajes_suficiencia(question, pasajes))


def reformular(question, pasajes, generator, max_new_tokens=160):
    return generator.complete(mensajes_iterativo(question, pasajes), max_new_tokens=max_new_tokens,
                              enable_thinking=False).strip()


# Agente de figuras (Cerberus, 2-oct): el reformulador acierta la figura del caso («acción popular») pero inventa el
# número de la ley que la regula («Ley 1448 de 2011»). Siguiendo a Nguyen et al. (arXiv 2410.12154, conceptos
# jurídicos implícitos en consultas narradas), el decoder solo nombra la figura y es el corpus el que dice qué
# estatuto la regula (Retriever.estatuto_de_figura).
def mensajes_figuras(question):
    return [{"role": "system", "content": "Eres un abogado colombiano. Respondes solo con lo que se pide, sin explicaciones."},
            {"role": "user", "content": (
                _pregunta(question) + "\n\nNombra de 1 a 3 figuras o instituciones juridicas colombianas que resuelven "
                "este caso (por ejemplo, el nombre de una accion, un derecho, un contrato o un recurso). Una por linea, "
                "de 2 a 5 palabras cada una, en minusculas, SIN numeros de leyes ni articulos.")}]


def figuras(question, generator, max_new_tokens=40):
    import re
    texto = generator.complete(mensajes_figuras(question), max_new_tokens=max_new_tokens, enable_thinking=False)
    salida = []
    for linea in texto.splitlines():
        linea = re.sub(r"^[\s\-\*\d\.\)]+", "", linea).strip().strip(".").strip("*").strip()
        if 2 <= len(linea.split()) <= 6 and not re.search(r"\d", linea):
            salida.append(linea.lower())
    return list(dict.fromkeys(salida))[:3]
