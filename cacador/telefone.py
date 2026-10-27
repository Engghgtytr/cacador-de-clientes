"""Telefones brasileiros: limpar, saber se é celular (WhatsApp) e montar o link."""
from __future__ import annotations

import re
from urllib.parse import quote


def normalizar(texto: str | None) -> str | None:
    """Devolve só dígitos no formato 55 + DDD + número (ex.: 5511912345678), ou None."""
    if not texto:
        return None
    d = re.sub(r"\D", "", texto)
    if d.startswith("0800") or d.startswith("800"):
        return None  # 0800 não recebe WhatsApp nem é de um negócio local
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    d = d.lstrip("0")
    if len(d) not in (10, 11):
        return None
    if len(d) == 11 and d[2] != "9":
        return None
    return "55" + d


def todos(texto: str | None) -> list[str]:
    """O mapa às vezes junta vários números com ';' ou '/'."""
    if not texto:
        return []
    numeros = []
    for parte in re.split(r"[;/,]| e ", texto):
        n = normalizar(parte)
        if n and n not in numeros:
            numeros.append(n)
    return numeros


def celular(numero: str) -> bool:
    return len(numero) == 13 and numero[4] == "9"


def formatar(numero: str) -> str:
    ddd, resto = numero[2:4], numero[4:]
    return f"({ddd}) {resto[:-4]}-{resto[-4:]}"


def link_whatsapp(numero: str, texto: str) -> str:
    return f"https://wa.me/{numero}?text={quote(texto)}"
