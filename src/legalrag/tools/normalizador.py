"""Agente normalizador de citas: avisa cuando la pregunta o una opción cita una norma con el año equivocado.

El banco trae errores de digitación en las normas: la respuesta correcta de la pregunta 58 es «Ley 1564 de
2002» (la Ley 1564 es de 2012, el Código General del Proceso), y la lista oficial de normas del banco
(seed_targets.json) incluye «Ley 1150 de 2005» (es de 2007) o «Ley 964 de 2006» (es de 2005). El modelo
descarta la opción porque el año no cuadra con la evidencia. Si una ley o decreto citado no existe en el
corpus con ese año pero sí con el mismo número y otro año, se agrega al prompt una nota como

    Opción A: «Ley 1564 de 2002» no está con ese año; la Ley 1564 es de 2012 (Código General del Proceso).
    Puede ser un error de digitación de esa misma norma.

Es una herramienta determinista sobre el inventario; no usa modelo y no cambia la evidencia.
"""
import re
from collections import defaultdict

_CITA = re.compile(r"\b(ley|decreto)\s+(?:no\.?\s*)?(\d{1,5})\s+de\s+(\d{4})\b", re.I)


class NormalizadorCitas:
    def __init__(self, documentos):
        """documentos: registros del inventario (tipo, numero, anio, titulo)."""
        self.por_numero = defaultdict(list)
        for doc in documentos:
            tipo = str(doc.get("tipo") or "").lower()
            if tipo in ("ley", "decreto") and doc.get("numero") and doc.get("anio"):
                numero = str(doc["numero"]).lstrip("0") or "0"
                self.por_numero[(tipo, numero)].append((int(doc["anio"]), doc.get("titulo") or ""))

    def avisos(self, texto):
        """[(cita escrita, año real, título)] para las citas cuyo año no existe pero el número sí."""
        resultado = []
        for m in _CITA.finditer(texto or ""):
            tipo, numero, anio = m.group(1).lower(), m.group(2).lstrip("0") or "0", int(m.group(3))
            existentes = self.por_numero.get((tipo, numero), [])
            if not existentes or any(a == anio for a, _ in existentes):
                continue
            anios = {a for a, _ in existentes}
            if len(anios) == 1:  # solo si no hay ambigüedad sobre a qué norma se refiere
                real, titulo = existentes[0]
                resultado.append((m.group(0), real, titulo))
        return resultado

    def nota(self, entrada, directo=False):
        """`directo` (Mark 44): pide evaluar la opción con el año corregido. Con la nota informativa, el modelo
        razonaba «esa ley no existe» y descartaba justo la opción correcta (pregunta 58)."""
        lineas = []
        partes = [("La pregunta", entrada.get("pregunta") or "")] + \
                 [(f"Opción {letra}", texto) for letra, texto in (entrada.get("opciones") or {}).items()]
        for donde, texto in partes:
            for escrita, real, titulo in self.avisos(texto):
                tipo, numero = escrita.split()[0].capitalize(), re.search(r"\d+", escrita).group()
                nombre = f" ({titulo})" if titulo and not titulo.lower().startswith(tipo.lower()) else ""
                # Si otra parte ya cita la misma norma con el año real, el año errado puede ser un distractor
                # deliberado: entonces solo se informa, sin pedir que se evalúe como la norma correcta.
                correcta = re.compile(rf"\b{tipo}\s+{numero}\s+de\s+{real}\b", re.IGNORECASE)
                distractor = any(correcta.search(otro) for d, otro in partes if d != donde)
                if directo and not distractor:
                    lineas.append(f"- {donde}: «{escrita}» es un error de digitación de la {tipo} {numero} de "
                                  f"{real}{nombre}. Evalúala como si dijera «{tipo} {numero} de {real}»; no la "
                                  "descartes por el año.")
                else:
                    lineas.append(f"- {donde}: «{escrita}» no existe con ese año; la {tipo} {numero} es de {real}{nombre}. "
                                  "Puede ser un error de digitación de esa misma norma.")
        if not lineas:
            return None
        return "NOTA SOBRE LAS NORMAS CITADAS (comprobado contra el inventario del corpus)\n" + "\n".join(lineas)


_NORMALIZADOR = {}


def normalizador_del_corpus(config):
    """NormalizadorCitas sobre el inventario del corpus (se carga una vez). Si no lo encuentra, avisa una vez y
    devuelve None: la corrida sigue sin el normalizador en vez de detenerse."""
    import json

    clave = str(config.root)
    if clave not in _NORMALIZADOR:
        candidatos = [config.root / "corpus_manifest.json", config.root / "data/raw/base_manifest.json"]
        ruta = next((c for c in candidatos if c.is_file()), None)
        if ruta is None:
            print("  AVISO: no está corpus_manifest.json en la raíz del proyecto; el normalizador de citas queda "
                  "desactivado en esta corrida (cópienlo desde la carpeta del índice).", flush=True)
            _NORMALIZADOR[clave] = None
        else:
            manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
            documentos = manifiesto if isinstance(manifiesto, list) else \
                manifiesto.get("documentos") or manifiesto.get("documents") or []
            _NORMALIZADOR[clave] = NormalizadorCitas(documentos)
    return _NORMALIZADOR[clave]
