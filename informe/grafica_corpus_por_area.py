"""Composición del corpus por área del derecho y tipo de fuente, frente al peso de cada área en el banco.

    python3 informe/grafica_corpus_por_area.py     # → informe/corpus_por_area.png y tabla en la terminal

Cuenta los documentos del inventario congelado (data/processed/corpus_final/documentos.jsonl) por cada área del
temario (§4.2) que tienen asignada; un documento con varias áreas cuenta en cada una. El tipo de fuente se agrupa en
normativa (Constitución, actos legislativos, leyes, decretos, resoluciones), jurisprudencia (sentencias y autos) y
doctrina (conceptos, compendios, circulares). El peso en el banco es el de la tabla del enunciado (1.042 ítems).
"""
import collections
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
INVENTARIO = RAIZ / "data/processed/corpus_final/documentos.jsonl"
SALIDA = RAIZ / "informe/corpus_por_area.png"

# Enunciado §4.2: ítems del banco completo (1.042) por área.
BANCO = {"constitucional": 134, "administrativo": 124, "penal": 123, "procesal": 111, "comercial": 104,
         "civil": 102, "familia": 93, "tributario": 92, "laboral": 87, "mercados": 72}
NOMBRE = {"constitucional": "Constitucional", "administrativo": "Administrativo", "penal": "Penal",
          "procesal": "Procesal", "comercial": "Comercial y sociedades", "civil": "Civil", "familia": "Familia",
          "tributario": "Tributario", "laboral": "Laboral",
          "mercados": "Mercados (competencia, consumidor, datos, PI)"}
GRUPO = {"constitucion": "Normativa", "acto_legislativo": "Normativa", "ley": "Normativa", "decreto": "Normativa",
         "resolucion": "Normativa", "decision": "Normativa", "acuerdo": "Normativa",
         "sentencia": "Jurisprudencia", "auto": "Jurisprudencia",
         "concepto": "Doctrina", "compendio": "Doctrina", "circular": "Doctrina", "memorando": "Doctrina"}
COLORES = {"Normativa": "#1f6fb4", "Jurisprudencia": "#f2a81d", "Doctrina": "#2a9d8f"}


def main():
    conteo = {a: collections.Counter() for a in BANCO}
    for linea in open(INVENTARIO, encoding="utf-8"):
        d = json.loads(linea)
        areas = d.get("areas") or []
        for a in ([areas] if isinstance(areas, str) else areas):
            if a in conteo:
                conteo[a][GRUPO.get(d.get("tipo"), "Doctrina")] += 1
    total_asig = sum(sum(c.values()) for c in conteo.values())
    total_banco = sum(BANCO.values())
    orden = list(BANCO)  # orden del enunciado (de más a menos ítems en el banco)

    print(f"{'Área':46s} {'Normativa':>9} {'Jurisprud.':>10} {'Doctrina':>9} {'Total':>7} {'% corpus':>9} {'% banco':>8}")
    for a in orden:
        c = conteo[a]
        tot = sum(c.values())
        print(f"{NOMBRE[a]:46s} {c['Normativa']:9d} {c['Jurisprudencia']:10d} {c['Doctrina']:9d} {tot:7d} "
              f"{100 * tot / total_asig:8.1f}% {100 * BANCO[a] / total_banco:7.1f}%")

    fig, (ax_t, ax_g) = plt.subplots(1, 2, figsize=(17, 5.2), gridspec_kw={"width_ratios": [1.15, 1]})
    ax_t.axis("off")
    filas = [[NOMBRE[a], f"{conteo[a]['Normativa']:,}".replace(",", "."),
              f"{conteo[a]['Jurisprudencia']:,}".replace(",", "."), f"{conteo[a]['Doctrina']:,}".replace(",", "."),
              f"{sum(conteo[a].values()):,}".replace(",", "."),
              f"{100 * sum(conteo[a].values()) / total_asig:.1f} %", f"{100 * BANCO[a] / total_banco:.1f} %"]
             for a in orden]
    tabla = ax_t.table(cellText=filas, colLabels=["Área", "Normativa", "Jurisprudencia", "Doctrina", "Total",
                                                  "% corpus", "% banco"],
                       loc="center", cellLoc="right", colLoc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(8.5)
    tabla.scale(1, 1.35)
    for (fila, col), celda in tabla.get_celld().items():
        celda.set_edgecolor("#bbbbbb")
        if col == 0:
            celda.set_text_props(ha="left")
            celda._loc = "left"
        if fila == 0:
            celda.set_text_props(weight="bold")
            celda.set_facecolor("#e8edf3")
    tabla.auto_set_column_width(list(range(7)))
    ax_t.set_title("Corpus por área (documentos; uno con varias áreas cuenta en cada una)", fontsize=10, loc="left")

    y = list(range(len(orden)))[::-1]
    izquierda = [0] * len(orden)
    for grupo in ("Normativa", "Jurisprudencia", "Doctrina"):
        valores = [conteo[a][grupo] for a in orden]
        ax_g.barh(y, valores, left=izquierda, color=COLORES[grupo], label=grupo, height=0.62)
        izquierda = [i + v for i, v in zip(izquierda, valores)]
    for yy, a, tot in zip(y, orden, izquierda):
        ax_g.text(tot + max(izquierda) * 0.01, yy, f"{tot:,}".replace(",", "."), va="center", fontsize=8,
                  color="#444444")
    ax_g.set_yticks(y, [NOMBRE[a] for a in orden], fontsize=8.5)
    ax_g.set_xlabel("Documentos del corpus", fontsize=9)
    ax_g.legend(loc="lower right", fontsize=8, frameon=False)
    ax_g.spines[["top", "right"]].set_visible(False)
    ax_g.set_title("Documentos por área y tipo de fuente", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(SALIDA, dpi=170)
    print(f"\n{SALIDA.relative_to(RAIZ)} ({total_asig:,} asignaciones de área sobre 32.617 documentos)".replace(",", "."))


if __name__ == "__main__":
    main()
