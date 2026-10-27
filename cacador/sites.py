"""Confere o site de quem já tem: está no ar? tem cadeado? funciona no celular? é rápido?

Só abre a página inicial, uma vez, como um visitante comum.
"""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

AGENTE = "Mozilla/5.0 (compatible; cacador-de-clientes/1.0; conferencia de site)"
LENTO_SEGUNDOS = 4.0


class EnderecoProibido(Exception):
    pass


def conferir_endereco(url: str) -> None:
    """Os sites vêm do mapa, que qualquer um edita: só abre endereço público da internet.

    Bloqueia o próprio PC (127.0.0.1, o painel), a rede de casa (roteador, 192.168…)
    e portas fora do padrão, também em cada redirecionamento.
    """
    partes = urllib.parse.urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise EnderecoProibido(url)
    if partes.port not in (None, 80, 443):
        raise EnderecoProibido(url)
    try:
        enderecos = {info[4][0] for info in socket.getaddrinfo(partes.hostname, None)}
    except socket.gaierror as erro:
        raise EnderecoProibido(url) from erro
    for ip in enderecos:
        if not ipaddress.ip_address(ip.split("%")[0]).is_global:
            raise EnderecoProibido(url)


class _RedirecionaComCuidado(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        conferir_endereco(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _conferir_conexao(conexao) -> None:
    # Confere o IP em que a conexão realmente entrou: o nome pode ter mudado de IP
    # entre a conferência e a conexão (o truque do "DNS rebinding").
    ip = conexao.sock.getpeername()[0]
    if not ipaddress.ip_address(ip.split("%")[0]).is_global:
        conexao.close()
        raise EnderecoProibido(ip)


class _HTTPConferido(http.client.HTTPConnection):
    def connect(self):
        super().connect()
        _conferir_conexao(self)


class _HTTPSConferido(http.client.HTTPSConnection):
    def connect(self):
        super().connect()
        _conferir_conexao(self)


class _AbreHTTP(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HTTPConferido, req)


class _AbreHTTPS(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HTTPSConferido, req, context=self._context)


_ABRIDOR = urllib.request.build_opener(urllib.request.ProxyHandler({}), _AbreHTTP, _AbreHTTPS, _RedirecionaComCuidado)


def _abrir(url: str):
    conferir_endereco(url)
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    inicio = time.monotonic()
    with _ABRIDOR.open(pedido, timeout=12) as r:
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
