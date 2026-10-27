"""Confere o site de quem já tem: está no ar? tem cadeado? funciona no celular? é rápido?

Só abre a página inicial, uma vez, como um visitante comum.
"""
from __future__ import annotations

import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

AGENTE = "Mozilla/5.0 (compatible; cacador-de-clientes/1.0; conferencia de site)"
LENTO_SEGUNDOS = 4.0


def _abrir(url: str):
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    inicio = time.monotonic()
    with urllib.request.urlopen(pedido, timeout=12) as r:
        html = r.read(400_000).decode("utf-8", errors="ignore")
        return r.status, r.geturl(), html, time.monotonic() - inicio


def analisar(url: str, abrir=_abrir) -> dict:
    if not re.match(r"https?://", url, re.I):
        url = "http://" + url
    try:
        status, final, html, tempo = abrir(url)
    except Exception:
        return {"no_ar": False, "problemas": ["o site não abre"], "url_final": None}
    if status >= 400:
        return {"no_ar": False, "problemas": [f"o site não abre (erro {status})"], "url_final": final}
    problemas = []
    if not final.lower().startswith("https://"):
        problemas.append("o site não tem cadeado de segurança (https)")
    if not re.search(r"<meta[^>]+name=[\"']?viewport", html, re.I):
        problemas.append("o site não se adapta ao celular")
    if tempo > LENTO_SEGUNDOS:
        problemas.append(f"o site demorou {tempo:.0f} segundos para abrir")
    return {"no_ar": True, "problemas": problemas, "url_final": final, "segundos": round(tempo, 1)}


def analisar_todos(leads: list[dict], abrir=_abrir, simultaneos: int = 8, so_novos: bool = True) -> int:
    alvo = [l for l in leads if l.get("site") and not (so_novos and l.get("analise"))]
    with ThreadPoolExecutor(max_workers=simultaneos) as ex:
        for lead, resultado in zip(alvo, ex.map(lambda l: analisar(l["site"], abrir), alvo)):
            lead["analise"] = resultado
    return len(alvo)
