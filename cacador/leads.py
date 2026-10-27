"""Junta tudo: situação do site, melhor contato, prioridade, mensagem e o que já foi feito.

O que você faz com cada empresa (enviada, respondeu, não quer contato...) fica em
dados/status.json, separado da lista: buscar de novo não apaga nada disso.
"""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import mensagens, telefone
from .config import DADOS

SP = ZoneInfo("America/Sao_Paulo")
STATUS = {
    "novo": "Na fila",
    "enviado": "Mensagem enviada",
    "follow_up": "Follow-up enviado",
    "respondeu": "Respondeu",
    "fechou": "Fechou negócio",
    "nao_quer": "Não quer contato",
    "descartado": "Descartado",
}
ENVIOS = ("enviado", "follow_up")
PONTOS_SITUACAO = {"sem_site": 3, "site_fora": 3, "site_com_problema": 2, "nao_conferido": 1, "site_ok": 0}
PONTOS_CONTATO = {"whatsapp": 2, "telefone": 1, "instagram": 1, "procurar": 0}


def situacao(lead: dict) -> str:
    if not lead.get("site"):
        return "sem_site"
    a = lead.get("analise")
    if not a:
        return "nao_conferido"
    if not a.get("no_ar"):
        return "site_fora"
    return "site_com_problema" if a.get("problemas") else "site_ok"


def contato(lead: dict) -> dict:
    celulares = [n for n in lead.get("telefones", []) if telefone.celular(n)]
    fixos = [n for n in lead.get("telefones", []) if not telefone.celular(n)]
    if celulares:
        tipo = "whatsapp"
    elif fixos:
        tipo = "telefone"
    elif lead.get("instagram"):
        tipo = "instagram"
    else:
        tipo = "procurar"
    return {
        "tipo": tipo,
        "whatsapp": celulares[0] if celulares else None,
        "telefones": [{"numero": n, "texto": telefone.formatar(n)} for n in lead.get("telefones", [])],
        "instagram": lead.get("instagram"),
    }


class Status:
    """Status de cada empresa, salvo em JSON. Um lock evita duas gravações ao mesmo tempo."""

    def __init__(self, arquivo: Path = DADOS / "status.json"):
        self.arquivo = arquivo
        self._lock = threading.Lock()
        self.dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}

    def de(self, id_: str) -> dict:
        return self.dados.get(id_, {"status": "novo", "historico": [], "obs": ""})

    def enviados_no_dia(self, dia: date) -> int:
        return sum(
            1 for s in self.dados.values() for h in s.get("historico", [])
            if h["status"] in ENVIOS and datetime.fromisoformat(h["quando"]).astimezone(SP).date() == dia
        )

    def marcar(self, id_: str, novo: str, obs: str | None = None, agora: datetime | None = None) -> dict:
        if novo not in STATUS:
            raise ValueError("status inválido")
        agora = agora or datetime.now(SP)
        with self._lock:
            s = self.dados.setdefault(id_, {"status": "novo", "historico": [], "obs": ""})
            s["status"] = novo
            s["historico"].append({"status": novo, "quando": agora.isoformat(timespec="seconds")})
            if obs is not None:
                s["obs"] = obs[:1000]
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            temporario = self.arquivo.with_suffix(".tmp")
            temporario.write_text(json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8")
            temporario.replace(self.arquivo)
            return s


def montar(leads: list[dict], status: Status, config: dict, agora: datetime | None = None) -> list[dict]:
    agora = agora or datetime.now(SP)
    prazo = timedelta(days=config.get("dias_para_follow_up", 5))
    saida = []
    for lead in leads:
        sit = situacao(lead)
        cont = contato(lead)
        st = status.de(lead["id"])
        ultimo_envio = next((h["quando"] for h in reversed(st["historico"]) if h["status"] in ENVIOS), None)
        vencido = (
            st["status"] == "enviado" and ultimo_envio is not None
            and agora - datetime.fromisoformat(ultimo_envio) >= prazo
        )
        saida.append({
            **lead,
            "situacao": sit,
            "contato": cont,
            "prioridade": PONTOS_SITUACAO[sit] + PONTOS_CONTATO[cont["tipo"]],
            "status": st["status"],
            "obs": st.get("obs", ""),
            "historico": st["historico"],
            "follow_up_vencido": vencido,
            "mensagem": mensagens.primeira(lead, sit, config),
            "mensagem_follow_up": mensagens.follow_up(lead, config),
        })
    saida.sort(key=lambda l: (-l["prioridade"], l["nome"].lower()))
    return saida
