"""Convierte el REPORTE_AVANCE.md (plantilla oficial del viernes, llenada) en REPORTE_AVANCE.pdf, tal cual el Markdown.

    pip install markdown        # una vez, en cualquier entorno (no hace falta el del sistema)
    python3 informe/generar_reporte_avance.py data/oficial/entregables/viernes/REPORTE_AVANCE.md

Markdown estándar (con tablas) → HTML con estilo mínimo → PDF con LibreOffice en modo headless. La entrega exige
una sola página: el script informa cuántas resultaron.
"""
import re
import subprocess
import sys
from pathlib import Path

import markdown

CSS = ("body{font-family:Arial,sans-serif;font-size:9pt} h1{font-size:15pt;margin:0 0 4pt} h2{font-size:11pt;margin:8pt 0 3pt} "
       "p{margin:3pt 0} table{border-collapse:collapse;margin:2pt 0} th,td{border:1px solid #000;padding:1px 5px} "
       "td p,th p{margin:0} ol{margin:2pt 0} li{margin:1pt 0} hr{margin:4pt 0}")


def main():
    md = Path(sys.argv[1]).resolve()
    html, pdf = md.with_suffix(".html"), md.with_suffix(".pdf")
    cuerpo = markdown.markdown(md.read_text(encoding="utf-8"), extensions=["tables"])
    html.write_text(f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Reporte de avance</title>"
                    f"<style>{CSS}</style></head><body>{cuerpo}</body></html>", encoding="utf-8")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf:writer_web_pdf_Export", "--outdir", str(md.parent),
                    str(html)], check=True, capture_output=True, timeout=180)
    html.unlink()
    paginas = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
    print(f"{pdf}: {paginas} página(s)" + ("" if paginas == 1 else "  ← la entrega exige una sola"))


if __name__ == "__main__":
    main()
