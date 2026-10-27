"""Linha de comando do Caçador de clientes.

    python cacador.py buscar      # baixa barbearias e restaurantes do mapa (OpenStreetMap)
    python cacador.py analisar    # confere os sites de quem já tem
    python cacador.py painel      # abre o painel no navegador (http://127.0.0.1:8765)
    python cacador.py resumo      # números no terminal

Nada aqui manda mensagem sozinho: o painel prepara, você revisa e envia.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from cacador import buscar, sites
from cacador.config import carregar
from cacador.leads import Status, montar


def cmd_buscar(config):
    print(f"Buscando {', '.join(config['ramos'])} em {config['cidade']} no OpenStreetMap (pode levar 1 a 2 minutos)…")
    leads = buscar.buscar(config["cidade"], config["ramos"])
    arquivo = buscar.salvar(leads, config["cidade"])
    contagem = Counter(l["ramo"] for l in leads)
    print(f"{len(leads)} negócios com nome: " + ", ".join(f"{n} {r}s" for r, n in contagem.items()))
    print(f"Salvo em {arquivo}. Próximo passo: python cacador.py analisar")


def cmd_analisar(config, args):
    lista = buscar.carregar()
    if not lista["leads"]:
        sys.exit("Ainda não há empresas. Rode primeiro: python cacador.py buscar")
    n = sum(1 for l in lista["leads"] if l.get("site") and (args.de_novo or not l.get("analise")))
    print(f"Conferindo {n} sites (só a página inicial de cada um)…")
    sites.analisar_todos(lista["leads"], so_novos=not args.de_novo)
    buscar.salvar(lista["leads"], lista["cidade"] or config["cidade"])
    cmd_resumo(config)


def cmd_resumo(config):
    lista = montar(buscar.carregar()["leads"], Status(), config)
    if not lista:
        sys.exit("Ainda não há empresas. Rode primeiro: python cacador.py buscar")
    for ramo in config["ramos"]:
        doramo = [l for l in lista if l["ramo"] == ramo]
        sit = Counter(l["situacao"] for l in doramo)
        cont = Counter(l["contato"]["tipo"] for l in doramo)
        print(f"\n{ramo}: {len(doramo)}")
        print(f"  sem site {sit['sem_site']} · site fora do ar {sit['site_fora']} · site com problema {sit['site_com_problema']}"
              f" · site ok {sit['site_ok']} · não conferido {sit['nao_conferido']}")
        print(f"  contato: WhatsApp {cont['whatsapp']} · telefone fixo {cont['telefone']} · Instagram {cont['instagram']}"
              f" · procurar no Google {cont['procurar']}")


def cmd_painel(args):
    import webbrowser

    from cacador.servidor import criar_servidor

    servidor = criar_servidor(args.porta)
    url = f"http://127.0.0.1:{args.porta}/"
    print(f"Painel em {url} (deixe esta janela aberta; Ctrl+C para fechar)")
    if not args.nao_abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("Painel fechado.")


def main(argv=None):
    p = argparse.ArgumentParser(description="Caçador de clientes (sem disparo em massa)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("buscar", help="baixa as empresas do mapa")
    a = sub.add_parser("analisar", help="confere os sites de quem já tem")
    a.add_argument("--de-novo", action="store_true", help="confere de novo até os já conferidos")
    pn = sub.add_parser("painel", help="abre o painel")
    pn.add_argument("--porta", type=int, default=8765)
    pn.add_argument("--nao-abrir", action="store_true")
    sub.add_parser("resumo", help="mostra os números")
    args = p.parse_args(argv)
    config = carregar()
    {
        "buscar": lambda: cmd_buscar(config),
        "analisar": lambda: cmd_analisar(config, args),
        "painel": lambda: cmd_painel(args),
        "resumo": lambda: cmd_resumo(config),
    }[args.cmd]()


if __name__ == "__main__":
    main()
