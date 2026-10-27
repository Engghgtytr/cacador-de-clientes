"""Busca negócios no OpenStreetMap (grátis, sem chave), pela API Overpass.

Os dados são públicos e colaborativos: o mapa pode estar desatualizado. Por isso o painel
pede para conferir no Google Maps antes de mandar a mensagem.
Licença dos dados: © colaboradores do OpenStreetMap (ODbL).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import telefone
from .config import DADOS

URL = "https://overpass-api.de/api/interpreter"
AGENTE = "cacador-de-clientes/1.0 (projeto de estudo; uso manual, sem disparo em massa)"

FILTROS = {
    "barbearia": [
        'nwr["shop"="hairdresser"]["hairdresser"="barber"](area.c);',
        'nwr["shop"="barber"](area.c);',
        'nwr["shop"="hairdresser"]["name"~"barbearia|barber",i](area.c);',
    ],
    "restaurante": ['nwr["amenity"="restaurant"](area.c);'],
}
REDES = ("instagram.com", "facebook.com", "fb.com", "linktr.ee", "wa.me", "whatsapp.com", "ifood.com.br", "tiktok.com")


def consulta(cidade: str, ramo: str) -> str:
    if ramo not in FILTROS:
        raise ValueError(f"Ramo '{ramo}' não existe. Opções: {', '.join(FILTROS)}")
    nome = cidade.replace("\\", "").replace('"', "")
    linhas = "\n  ".join(FILTROS[ramo])
    return (
        f'[out:json][timeout:180];\n'
        f'area["name"="{nome}"]["admin_level"="8"]["boundary"="administrative"]->.c;\n'
        f"(\n  {linhas}\n);\nout tags center;"
    )


def _post(consulta_texto: str) -> dict:
    corpo = urllib.parse.urlencode({"data": consulta_texto}).encode()
    pedido = urllib.request.Request(URL, data=corpo, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=240) as resposta:
        return json.load(resposta)


def so_rede_social(url: str | None) -> bool:
    return bool(url) and any(r in url.lower() for r in REDES)


def _instagram(tags: dict) -> str | None:
    bruto = tags.get("contact:instagram") or tags.get("instagram")
    for chave in ("website", "contact:website", "url"):
        if not bruto and "instagram.com" in (tags.get(chave) or "").lower():
            bruto = tags[chave]
    if not bruto:
        return None
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", bruto)
    usuario = m.group(1) if m else bruto.strip().lstrip("@")
    return usuario if re.fullmatch(r"[A-Za-z0-9_.]{1,30}", usuario) else None


def normalizar(elemento: dict, ramo: str) -> dict | None:
    t = elemento.get("tags", {})
    nome = (t.get("name") or "").strip()
    if not nome:
        return None
    centro = elemento.get("center") or elemento
    site = next((t[k].strip() for k in ("website", "contact:website", "url") if t.get(k)), None)
    fones = []
    for chave in ("contact:whatsapp", "contact:mobile", "phone", "contact:phone", "mobile"):
        for n in telefone.todos(t.get(chave)):
            if n not in fones:
                fones.append(n)
    rua = " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
    bairro = t.get("addr:suburb") or t.get("addr:neighbourhood") or t.get("addr:district") or ""
    return {
        "id": f"{elemento['type']}/{elemento['id']}",
        "nome": nome,
        "ramo": ramo,
        "endereco": ", ".join(x for x in (rua, bairro) if x),
        "bairro": bairro,
        "cidade": t.get("addr:city") or "",
        "telefones": fones,
        "instagram": _instagram(t),
        "site": None if so_rede_social(site) else site,
        "rede_social": site if so_rede_social(site) else None,
        "cozinha": t.get("cuisine", "").replace(";", ", ").replace("_", " "),
        "lat": centro.get("lat"),
        "lon": centro.get("lon"),
    }


def buscar(cidade: str, ramos: list[str], pedir=_post) -> list[dict]:
    vistos, leads = set(), []
    for ramo in ramos:
        for el in pedir(consulta(cidade, ramo)).get("elements", []):
            lead = normalizar(el, ramo)
            if lead and lead["id"] not in vistos:
                vistos.add(lead["id"])
                leads.append(lead)
    return leads


def salvar(leads: list[dict], cidade: str, pasta: Path = DADOS) -> Path:
    """Guarda a lista nova sem perder a análise de site já feita para quem continua nela."""
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "leads.json"
    antigos = {}
    if arquivo.exists():
        antigos = {l["id"]: l for l in json.loads(arquivo.read_text(encoding="utf-8"))["leads"]}
    for lead in leads:
        velho = antigos.get(lead["id"])
        if velho and velho.get("analise") and velho.get("site") == lead["site"]:
            lead["analise"] = velho["analise"]
    corpo = {"cidade": cidade, "buscado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"), "leads": leads}
    arquivo.write_text(json.dumps(corpo, ensure_ascii=False, indent=1), encoding="utf-8")
    return arquivo


def carregar(pasta: Path = DADOS) -> dict:
    arquivo = pasta / "leads.json"
    if not arquivo.exists():
        return {"cidade": "", "buscado_em": None, "leads": []}
    return json.loads(arquivo.read_text(encoding="utf-8"))
