"""Servidor local do painel (só no seu PC: 127.0.0.1, nada fica aberto na rede).

Proteções: só aceita o endereço local (contra "DNS rebinding"), POST só com o cabeçalho
do próprio painel (outro site aberto no navegador não consegue mexer nos dados) e corpo
pequeno. Os arquivos servidos são uma lista fixa.
"""
from __future__ import annotations

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import buscar
from .config import DADOS, RAIZ, carregar
from .leads import ENVIOS, SP, STATUS, Status, montar

PAINEL = RAIZ / "painel"
ARQUIVOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/pacotes.html": ("pacotes.html", "text/html; charset=utf-8"),
    "/pacotes.js": ("pacotes.js", "text/javascript; charset=utf-8"),
}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def dados_do_painel(config: dict, status: Status, pasta: Path = DADOS) -> dict:
    lista = buscar.carregar(pasta)
    agora = datetime.now(SP)
    return {
        "cidade": lista.get("cidade") or config.get("cidade"),
        "buscado_em": lista.get("buscado_em"),
        "seu_nome": config.get("seu_nome", ""),
        "seu_contato": config.get("seu_contato", ""),
        "limite_por_dia": config.get("limite_por_dia", 15),
        "enviados_hoje": status.enviados_no_dia(agora.date()),
        "pacotes": config.get("pacotes", {}),
        "observacao_pacotes": config.get("observacao_pacotes", ""),
        "rotulos": STATUS,
        "leads": montar(lista["leads"], status, config, agora),
    }


def criar_servidor(porta: int = 8765, pasta: Path = DADOS, config: dict | None = None) -> ThreadingHTTPServer:
    config = config or carregar()
    status = Status(pasta / "status.json")
    hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}

    class Painel(BaseHTTPRequestHandler):
        def log_message(self, *args):  # sem poluir a janela
            pass

        def _cabecalhos_comuns(self):
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")

        def _responder(self, codigo: int, corpo: bytes, tipo: str):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self._cabecalhos_comuns()
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, codigo: int, dados: dict):
            self._responder(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in hosts

        def do_GET(self):
            if not self._host_ok():
                return self._json(403, {"erro": "endereço não permitido"})
            caminho = self.path.split("?", 1)[0]
            if caminho == "/api/dados":
                return self._json(200, dados_do_painel(config, status, pasta))
            if caminho in ARQUIVOS:
                nome, tipo = ARQUIVOS[caminho]
                return self._responder(200, (PAINEL / nome).read_bytes(), tipo)
            self._json(404, {"erro": "não encontrado"})

        def do_POST(self):
            origem = self.headers.get("Origin")
            if (not self._host_ok() or self.headers.get("X-Cacador") != "1"
                    or (origem and origem.split("://", 1)[-1] not in hosts)):
                return self._json(403, {"erro": "pedido não permitido"})
            if self.path != "/api/status":
                return self._json(404, {"erro": "não encontrado"})
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho <= 0 or tamanho > 10_000:
                return self._json(400, {"erro": "pedido inválido"})
            try:
                corpo = json.loads(self.rfile.read(tamanho))
                id_, novo, obs = corpo["id"], corpo["status"], corpo.get("obs")
                if not isinstance(id_, str) or novo not in STATUS or (obs is not None and not isinstance(obs, str)):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                return self._json(400, {"erro": "pedido inválido"})
            if id_ not in {l["id"] for l in buscar.carregar(pasta)["leads"]}:
                return self._json(404, {"erro": "empresa não encontrada"})
            limite = config.get("limite_por_dia", 15)
            if novo in ENVIOS and status.de(id_)["status"] != novo and status.enviados_no_dia(datetime.now(SP).date()) >= limite:
                return self._json(429, {"erro": f"Limite de {limite} mensagens por dia atingido. Continue amanhã."})
            s = status.marcar(id_, novo, obs)
            self._json(200, {"ok": True, "status": s["status"], "enviados_hoje": status.enviados_no_dia(datetime.now(SP).date())})

    return ThreadingHTTPServer(("127.0.0.1", porta), Painel)
