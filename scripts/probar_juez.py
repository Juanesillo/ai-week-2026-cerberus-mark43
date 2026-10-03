"""Diagnóstico del juez de texto libre (OpenRouter) antes de gastar una corrida completa de RAGAS.

    export OPENROUTER_API_KEY=...
    python3 scripts/probar_juez.py

1. Consumo y límite de la llave (GET /api/v1/key): cuánto se ha gastado en dólares.
2. Una sola llamada mínima al modelo juez del evaluador, con los mismos parámetros (temperatura 0 y
   reasoning «minimal»), mostrando el código HTTP y el error si lo hay. Cuesta una fracción de centavo.

No imprime la llave.
"""
import json
import os
import sys

import requests

MODELO = "z-ai/glm-5.3-flash"
BASE = "https://openrouter.ai/api/v1"

llave = os.environ.get("OPENROUTER_API_KEY", "").strip()
if not llave:
    sys.exit("Falta OPENROUTER_API_KEY en esta terminal (export OPENROUTER_API_KEY=...).")
cabeceras = {"Authorization": f"Bearer {llave}"}
print(f"Llave: {llave[:8]}… ({len(llave)} caracteres)\n")

r = requests.get(f"{BASE}/key", headers=cabeceras, timeout=30)
print(f"[1] Consumo de la llave (HTTP {r.status_code})")
if r.ok:
    datos = r.json().get("data", {})
    for campo in ("label", "usage", "usage_daily", "usage_weekly", "usage_monthly", "limit", "limit_remaining",
                  "is_free_tier"):
        if campo in datos:
            print(f"    {campo}: {datos[campo]}")
    print("    (usage y limit en dólares)")
else:
    print("   ", r.text[:500])

print(f"\n[2] Llamada mínima a {MODELO}")
cuerpo = {"model": MODELO, "temperature": 0, "max_tokens": 32, "reasoning": {"effort": "minimal"},
          "messages": [{"role": "user", "content": "Responde solo: OK"}]}
r = requests.post(f"{BASE}/chat/completions", headers=cabeceras, json=cuerpo, timeout=120)
print(f"    HTTP {r.status_code}")
try:
    respuesta = r.json()
except ValueError:
    print("   ", r.text[:800])
    sys.exit(1)
if "error" in respuesta:
    print("    ERROR:", json.dumps(respuesta["error"], ensure_ascii=False)[:800])
else:
    mensaje = respuesta["choices"][0]["message"]
    print("    contenido:", repr(mensaje.get("content")))
    print("    uso:", respuesta.get("usage"))
    print("    El juez responde: RAGAS debería funcionar.")
