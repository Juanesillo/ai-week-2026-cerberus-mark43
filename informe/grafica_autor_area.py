"""Distribución del corpus por autor (órgano que expide el documento) y por área, frente al banco de preguntas.

    python3 informe/grafica_autor_area.py      # → informe/corpus_autor_area.png y tablas en la terminal

Autor: el campo `organo_emisor` del inventario cuando existe (14 mil documentos); si falta (el corpus ampliado), se
deduce de la fuente y del tipo: sentencias y autos por la corte de la fuente, leyes y actos legislativos → Congreso,
decretos → Presidencia, Constitución → Asamblea Nacional Constituyente, conceptos y resoluciones → la entidad de la
fuente. Un documento con varias áreas cuenta en cada una. El banco es el de la tabla del enunciado (§4.2, 1.042 ítems).
"""
import collections
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
INVENTARIO = RAIZ / "data/processed/corpus_final/documentos.jsonl"
SALIDA = RAIZ / "informe/corpus_autor_area.png"

AREAS = ["constitucional", "administrativo", "penal", "procesal", "comercial", "civil", "familia", "tributario",
         "laboral", "mercados"]
NOMBRE = {"constitucional": "Constitucional", "administrativo": "Administrativo", "penal": "Penal",
          "procesal": "Procesal", "comercial": "Comercial y sociedades", "civil": "Civil", "familia": "Familia",
          "tributario": "Tributario", "laboral": "Laboral", "mercados": "Mercados (comp., cons., datos, PI)"}
# Enunciado §4.2: cerradas, semiabiertas, abiertas por área (1.042 ítems).
BANCO = {"constitucional": (39, 86, 9), "administrativo": (53, 63, 8), "penal": (26, 93, 4), "procesal": (37, 71, 3),
         "comercial": (26, 70, 8), "civil": (27, 70, 5), "familia": (32, 59, 2), "tributario": (22, 66, 4),
         "laboral": (23, 58, 6), "mercados": (20, 46, 6)}
AUTORES = ["Corte Constitucional", "Congreso de la República", "Presidencia de la República", "Corte Suprema de Justicia",
           "Consejo de Estado", "DIAN", "Superintendencias", "Otros"]
COLOR = {"Corte Constitucional": "#f2a81d", "Congreso de la República": "#1f6fb4", "Presidencia de la República": "#6aaed6",
         "Corte Suprema de Justicia": "#d95f02", "Consejo de Estado": "#7570b3", "DIAN": "#2a9d8f",
         "Superintendencias": "#9e9e9e", "Otros": "#d0d0d0"}


def autor(d):
    organo = (d.get("organo_emisor") or "").strip()
    fuente = (d.get("fuente") or "").lower()
    tipo = d.get("tipo") or ""
    if organo:
        base = organo
    elif tipo in ("sentencia", "auto", "compendio"):
        base = ("Corte Constitucional" if "constitucional" in fuente else "Corte Suprema de Justicia" if "suprema" in fuente
                else "Consejo de Estado" if "consejo de estado" in fuente else "Superintendencia" if "superintendencia" in fuente
                else "Rama Judicial")
    elif tipo in ("ley", "acto_legislativo"):
        base = "Congreso de la República"
    elif tipo == "decreto":
        base = "Presidencia de la República"
    elif tipo == "constitucion":
        base = "Asamblea Nacional Constituyente"
    elif "dian" in fuente:
        base = "DIAN"
    elif "superintendencia" in fuente or "superservicios" in fuente:
        base = "Superintendencia"
    else:
        base = d.get("fuente") or "Sin dato"
    if base.startswith("Superintendencia"):
        return "Superintendencias"
    return base if base in AUTORES else "Otros"


def main():
    por_area = {a: collections.Counter() for a in AREAS}
    por_autor = collections.Counter()
    for linea in open(INVENTARIO, encoding="utf-8"):
        d = json.loads(linea)
        quien = autor(d)
        por_autor[quien] += 1
        areas = d.get("areas") or []
        for a in ([areas] if isinstance(areas, str) else areas):
            if a in por_area:
                por_area[a][quien] += 1
    total_docs = sum(por_autor.values())
    total_banco = sum(sum(v) for v in BANCO.values())
    total_asig = sum(sum(c.values()) for c in por_area.values())

    print("DOCUMENTOS POR AUTOR")
    for a in AUTORES:
        print(f"  {a:30s} {por_autor[a]:6d}  {100 * por_autor[a] / total_docs:5.1f} %")
    print(f"  {'Total':30s} {total_docs:6d}\n")
    cab = "".join(f"{a.split()[0][:9]:>10}" for a in AUTORES)
    print(f"DOCUMENTOS POR ÁREA Y AUTOR{'':16s}{cab}{'Total':>8}{'% corp':>8}{'Banco':>7}{'% banco':>8}")
    for a in AREAS:
        fila = "".join(f"{por_area[a][x]:10d}" for x in AUTORES)
        tot = sum(por_area[a].values())
        print(f"  {NOMBRE[a]:40s}{fila}{tot:8d}{100 * tot / total_asig:7.1f}%{sum(BANCO[a]):7d}{100 * sum(BANCO[a]) / total_banco:7.1f}%")

    fig, (ax_c, ax_b) = plt.subplots(1, 2, figsize=(17, 6.2), sharey=True, gridspec_kw={"width_ratios": [1.6, 1]})
    y = list(range(len(AREAS)))[::-1]
    izq = [0] * len(AREAS)
    for quien in AUTORES:
        v = [por_area[a][quien] for a in AREAS]
        ax_c.barh(y, v, left=izq, color=COLOR[quien], label=quien, height=0.62)
        izq = [i + x for i, x in zip(izq, v)]
    for yy, tot in zip(y, izq):
        ax_c.text(tot + max(izq) * 0.01, yy, f"{tot:,}".replace(",", "."), va="center", fontsize=8, color="#444")
    ax_c.set_yticks(y, [NOMBRE[a] for a in AREAS], fontsize=9)
    ax_c.set_xlabel("Documentos del corpus (uno con varias áreas cuenta en cada una)", fontsize=9)
    ax_c.set_title(f"Corpus: {total_docs:,} documentos por área y autor".replace(",", "."), fontsize=11, loc="left")
    ax_c.legend(fontsize=8, frameon=False, loc="lower right")
    ax_c.spines[["top", "right"]].set_visible(False)

    izq = [0] * len(AREAS)
    for k, (nombre, color) in enumerate((("Cerradas", "#1f6fb4"), ("Semiabiertas", "#f2a81d"), ("Abiertas", "#2a9d8f"))):
        v = [BANCO[a][k] for a in AREAS]
        ax_b.barh(y, v, left=izq, color=color, label=nombre, height=0.62)
        izq = [i + x for i, x in zip(izq, v)]
    for yy, a, tot in zip(y, AREAS, izq):
        pc = 100 * sum(por_area[a].values()) / total_asig
        ax_b.text(tot + 1.5, yy, f"{tot}  (banco {100 * tot / total_banco:.1f} % · corpus {pc:.1f} %)", va="center",
                  fontsize=8, color="#444")
    ax_b.set_xlabel("Preguntas del banco (enunciado §4.2)", fontsize=9)
    ax_b.set_title("Banco: 1.042 preguntas por área y formato", fontsize=11, loc="left")
    ax_b.set_xlim(0, 230)
    ax_b.legend(fontsize=8, frameon=False, loc="lower right")
    ax_b.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(SALIDA, dpi=160)
    print(f"\n{SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
