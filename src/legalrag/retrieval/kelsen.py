"""Nivel de la jerarquía normativa colombiana de un pasaje, calculado del campo `norma` del índice.

El índice reindexado trae `nivel_kelsen`, pero su clasificador solo reconoce los prefijos `sentencia_c_` del doc_id
(las sentencias `sentencia_cc_c...` quedan en 7) y deja sin nivel la Constitución y los códigos. `norma` sí está
normalizado (`sentencia_c_332_2025`, `ley_1437_2011`, `constitucion_1991`), así que el nivel se recalcula aquí.
"""

import re

# 1 Constitución y bloque · 2 sentencias C · 3 SU · 4 leyes · 5 decretos · 6 resoluciones · 7 el resto
# (jurisprudencia inter partes, conceptos, circulares, autos).
BOOST = {1: 1.15, 2: 1.12, 3: 1.10, 4: 1.08, 5: 1.05, 6: 1.02, 7: 1.00}
PREFIJOS = (("constitucion", 1), ("acto_legislativo", 1), ("sentencia_c_", 2), ("sentencia_su_", 3),
            ("ley_", 4), ("decision_", 4), ("decreto_", 5), ("resolucion_", 6))


def nivel(p):
    norma = (p.get("norma") or "").lower()
    for prefijo, n in PREFIJOS:
        if norma.startswith(prefijo):
            return n
    return 7


def normativo(p):
    """Fuente formal de derecho (Constitución, ley, decreto, resolución), no jurisprudencia ni doctrina."""
    return nivel(p) in (1, 4, 5, 6)


# Decretos con fuerza de ley: el encabezado del índice los nombra como código o estatuto («[Código Sustantivo del
# Trabajo]», «[Código de Comercio]») o como decreto-ley («[Decreto Ley 624 de 1989]», el Estatuto Tributario). En la
# jerarquía son ley (nivel 4), no decreto reglamentario (nivel 5).
FUERZA_DE_LEY = re.compile(r"^\[\s*(c[oó]digo|estatuto)\b|\bdecreto[\s-]+(ley|legislativo|extraordinario)\b", re.IGNORECASE)


def factor(p, codigos=False, doctrina=False):
    """Factor de `kelsen_boost` para un pasaje.

    codigos: los decretos con fuerza de ley pesan como ley.
    doctrina: dentro del nivel 7, la jurisprudencia (sentencias y autos de las cortes) queda por encima de la
    doctrina administrativa (conceptos, oficios, circulares): el precedente vincula, el concepto no."""
    n = nivel(p)
    if codigos and n == 5 and FUERZA_DE_LEY.search(p.get("encabezado") or ""):
        n = 4
    if doctrina and n == 7:
        norma = (p.get("norma") or "").lower()
        return 1.01 if norma.startswith(("sentencia", "auto")) else 1.00
    return BOOST[n]


# Ponderación horizontal (criterio cronológico, lex posterior; Ley 153 de 1887, arts. 2 y 3; Nino, «Introducción al
# análisis del derecho», antinomias): un artículo derogado por entero ya no es derecho vigente y no debe ocupar un cupo de
# la evidencia frente a la norma posterior que lo sustituyó. La base del Senado lo anota justo después del encabezado del
# artículo («<Artículo derogado por el artículo 626 de la Ley 1564 de 2012>»). Parágrafos o incisos derogados no cuentan:
# el resto del artículo sigue vigente.
ARTICULO_DEROGADO = re.compile(r"<\s*Art[ií]culo\s+derogado\b", re.IGNORECASE)


def vigencia(p, horizontal=False):
    """Factor horizontal: 0,5 si el pasaje es un artículo derogado por entero; 1 en otro caso."""
    if horizontal and ARTICULO_DEROGADO.search((p.get("texto") or "")[:400]):
        return 0.5
    return 1.0


# Criterio de especialidad (lex specialis; Ley 57 de 1887, art. 5: «la disposición relativa a un asunto especial prefiere a
# la que tenga carácter general»). La especialidad se mide frente a la materia de la pregunta: el área del banco (campo
# ciego `area`) contra las áreas del documento en el inventario. Una norma de la rama de la pregunta gana ×1,02 (×1,01 si
# abarca 3 áreas o más); el tope es menor que el salto entre niveles, para que la jerarquía (lex superior) prevalezca.
AREA_BANCO = (("constitucional", "constitucional"), ("administrativo", "administrativo"), ("penal", "penal"),
              ("procesal", "procesal"), ("comercial", "comercial"), ("civil", "civil"), ("familia", "familia"),
              ("tributario", "tributario"), ("laboral", "laboral"), ("mercados", "mercados"))
_AREAS_DOC = {}


def area_de_pregunta(area):
    from legalrag.citations.extract import fold
    texto = fold(area or "")
    return next((etiqueta for clave, etiqueta in AREA_BANCO if clave in texto), None)


def areas_documento(config):
    """doc_id → áreas del inventario congelado (se carga una vez por raíz)."""
    clave = str(config.root)
    if clave not in _AREAS_DOC:
        import json
        from legalrag.io import inventory_path
        mapa = {}
        for linea in open(inventory_path(config), encoding="utf-8"):
            d = json.loads(linea)
            a = d.get("areas") or []
            mapa[d["doc_id"]] = [a] if isinstance(a, str) else list(a)
        _AREAS_DOC[clave] = mapa
    return _AREAS_DOC[clave]


def especialidad(p, area, config):
    """Factor de especialidad del pasaje frente a la materia de la pregunta (1,0 si no hay área o no coincide)."""
    if not area:
        return 1.0
    areas = areas_documento(config).get(p.get("doc_id"), [])
    if area not in areas:
        return 1.0
    return 1.02 if len(areas) <= 2 else 1.01
