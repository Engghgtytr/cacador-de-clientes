"""Testes do Caçador de clientes (sem internet)."""
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytest

from cacador import buscar, mensagens, sites, telefone
from cacador.config import carregar
from cacador.leads import SP, Status, contato, montar, situacao
from cacador.servidor import criar_servidor

CONFIG = carregar()


# ---------- telefone ----------
@pytest.mark.parametrize("texto,esperado", [
    ("+55 11 91234-5678", "5511912345678"),
    ("(11) 3333-4444", "551133334444"),
    ("011 91234 5678", "5511912345678"),
    ("0800 123 4567", None),
    ("1234", None),
    ("11 81234-5678", None),  # 11 dígitos sem o 9: inválido
])
def test_normalizar(texto, esperado):
    assert telefone.normalizar(texto) == esperado


def test_varios_numeros_e_celular():
    nums = telefone.todos("+55 11 3333-4444; +55 11 98888-7777")
    assert nums == ["551133334444", "5511988887777"]
    assert not telefone.celular(nums[0]) and telefone.celular(nums[1])
    assert telefone.formatar(nums[1]) == "(11) 98888-7777"
    assert telefone.link_whatsapp(nums[1], "oi tudo bem?") == "https://wa.me/5511988887777?text=oi%20tudo%20bem%3F"


# ---------- busca no mapa ----------
def elemento(id_, **tags):
    return {"type": "node", "id": id_, "lat": -23.5, "lon": -46.6, "tags": tags}


def test_normalizar_elemento_do_mapa():
    lead = buscar.normalizar(elemento(
        1, name="Barbearia do Zé", phone="+55 11 98888-7777", website="https://instagram.com/barbeariadoze",
        **{"addr:street": "Rua A", "addr:housenumber": "10", "addr:suburb": "Pinheiros"}), "barbearia")
    assert lead["id"] == "node/1" and lead["bairro"] == "Pinheiros"
    assert lead["endereco"] == "Rua A 10, Pinheiros"
    assert lead["site"] is None  # Instagram não conta como site
    assert lead["rede_social"] and lead["instagram"] == "barbeariadoze"
    assert lead["telefones"] == ["5511988887777"]


def test_sem_nome_fica_de_fora_e_sem_repetidos():
    respostas = {"barbearia": [elemento(1, name="A"), elemento(2)], "restaurante": [elemento(1, name="A"), elemento(3, name="B")]}

    def pedir(consulta):
        ramo = "barbearia" if "hairdresser" in consulta else "restaurante"
        return {"elements": respostas[ramo]}

    leads = buscar.buscar("São Paulo", ["barbearia", "restaurante"], pedir=pedir)
    assert [l["id"] for l in leads] == ["node/1", "node/3"]


def test_consulta_nao_aceita_ramo_estranho_e_escapa_aspas():
    with pytest.raises(ValueError):
        buscar.consulta("São Paulo", "padaria")
    assert '"Sao"' not in buscar.consulta('Sao" Paulo', "restaurante")


def test_salvar_mantem_analise_de_site(tmp_path):
    lead = {"id": "node/1", "site": "https://x.com.br"}
    buscar.salvar([{**lead, "analise": {"no_ar": True, "problemas": []}}], "SP", tmp_path)
    buscar.salvar([dict(lead)], "SP", tmp_path)
    assert buscar.carregar(tmp_path)["leads"][0]["analise"]["no_ar"] is True


# ---------- conferência do site ----------
def abrir_falso(status=200, final="https://x.com.br", html='<meta name="viewport" content="width=device-width">', tempo=1.0):
    return lambda url: (status, final, html, tempo)


def test_site_bom():
    assert sites.analisar("x.com.br", abrir_falso()) == {"no_ar": True, "problemas": [], "url_final": "https://x.com.br", "segundos": 1.0}


def test_site_com_problemas():
    r = sites.analisar("http://x.com.br", abrir_falso(final="http://x.com.br", html="<html></html>", tempo=6.2))
    assert r["no_ar"] and len(r["problemas"]) == 3


def test_site_fora_do_ar():
    def quebra(url):
        raise urllib.error.URLError("sem resposta")
    assert sites.analisar("x.com.br", quebra)["no_ar"] is False
    assert sites.analisar("x.com.br", abrir_falso(status=500))["no_ar"] is False


# ---------- situação, contato, mensagem ----------
def test_situacao_e_contato():
    assert situacao({"site": None}) == "sem_site"
    assert situacao({"site": "a.com"}) == "nao_conferido"
    assert situacao({"site": "a.com", "analise": {"no_ar": False}}) == "site_fora"
    assert situacao({"site": "a.com", "analise": {"no_ar": True, "problemas": ["x"]}}) == "site_com_problema"
    c = contato({"telefones": ["551133334444", "5511988887777"]})
    assert c["tipo"] == "whatsapp" and c["whatsapp"] == "5511988887777"
    assert contato({"telefones": [], "instagram": "x"})["tipo"] == "instagram"


def test_mensagem_restaurante_tem_os_tres_pacotes_e_saida():
    lead = {"nome": "Cantina X", "ramo": "restaurante", "bairro": "Mooca", "telefones": []}
    msg = mensagens.primeira(lead, "sem_site", CONFIG)
    assert "Cantina X (Mooca)" in msg and "R$ 300" in msg and "R$ 800" in msg
    assert "QR code" in msg and "fictício" in msg
    assert mensagens.SAIR in msg


def test_mensagem_barbearia_com_site_ruim_cita_o_problema():
    lead = {"nome": "Barber Y", "ramo": "barbearia", "bairro": "", "telefones": [],
            "analise": {"no_ar": True, "problemas": ["o site não se adapta ao celular"]}}
    msg = mensagens.primeira(lead, "site_com_problema", CONFIG)
    assert "não se adapta ao celular" in msg and "agendamento" in msg
    assert "R$" not in msg


def test_preco_sem_valor():
    assert mensagens.preco(None) == "valor sob consulta"
    assert mensagens.preco(1500) == "R$ 1.500"


# ---------- status, limite e follow-up ----------
def test_status_conta_envios_do_dia_e_follow_up(tmp_path):
    st = Status(tmp_path / "status.json")
    ontem = datetime(2026, 10, 20, 15, 0, tzinfo=SP)
    st.marcar("node/1", "enviado", "falei com o dono", agora=ontem)
    st.marcar("node/2", "enviado", agora=ontem + timedelta(days=6))
    assert st.enviados_no_dia(ontem.date()) == 1
    with pytest.raises(ValueError):
        st.marcar("node/1", "qualquer")
    recarregado = Status(tmp_path / "status.json")
    assert recarregado.de("node/1")["obs"] == "falei com o dono"
    leads = [{"id": "node/1", "nome": "A", "ramo": "barbearia", "site": None, "telefones": [], "bairro": ""},
             {"id": "node/2", "nome": "B", "ramo": "barbearia", "site": None, "telefones": [], "bairro": ""}]
    lista = {l["id"]: l for l in montar(leads, recarregado, CONFIG, agora=ontem + timedelta(days=6))}
    assert lista["node/1"]["follow_up_vencido"] and not lista["node/2"]["follow_up_vencido"]


# ---------- servidor local ----------
@pytest.fixture
def servidor(tmp_path):
    buscar.salvar([{"id": "node/1", "nome": "A", "ramo": "barbearia", "site": None, "telefones": [], "bairro": ""}], "SP", tmp_path)
    cfg = {**CONFIG, "limite_por_dia": 1}
    srv = criar_servidor(0, tmp_path, cfg)
    porta = srv.server_address[1]
    # o servidor confere o Host com a porta configurada; com porta 0 recriamos com a porta real
    srv.server_close()
    srv = criar_servidor(porta, tmp_path, cfg)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{porta}"
    srv.shutdown()
    srv.server_close()


def pedido(url, corpo=None, cabecalhos=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, headers={"Content-Type": "application/json", **(cabecalhos or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}") if "json" in r.headers["Content-Type"] else r.read()
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_servidor_dados_e_status(servidor):
    codigo, dados = pedido(servidor + "/api/dados")
    assert codigo == 200 and dados["leads"][0]["nome"] == "A"
    assert pedido(servidor + "/api/status", {"id": "node/1", "status": "enviado"})[0] == 403  # sem o cabeçalho do painel
    ok = {"X-Cacador": "1"}
    assert pedido(servidor + "/api/status", {"id": "node/9", "status": "enviado"}, ok)[0] == 404
    assert pedido(servidor + "/api/status", {"id": "node/1", "status": "hackear"}, ok)[0] == 400
    assert pedido(servidor + "/api/status", {"id": "node/1", "status": "enviado"}, {**ok, "Origin": "https://site-malicioso.com"})[0] == 403
    codigo, r = pedido(servidor + "/api/status", {"id": "node/1", "status": "enviado"}, ok)
    assert codigo == 200 and r["enviados_hoje"] == 1


def test_servidor_so_entrega_arquivos_da_lista(servidor):
    assert pedido(servidor + "/../config.json")[0] == 404
    assert pedido(servidor + "/app.js")[0] == 200


def test_limite_por_dia(tmp_path, servidor):
    ok = {"X-Cacador": "1"}
    assert pedido(servidor + "/api/status", {"id": "node/1", "status": "enviado"}, ok)[0] == 200
    pedido(servidor + "/api/status", {"id": "node/1", "status": "novo"}, ok)
    codigo, r = pedido(servidor + "/api/status", {"id": "node/1", "status": "enviado"}, ok)
    assert codigo == 429 and "Limite" in r["erro"]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8765/api/dados", "http://localhost/", "http://192.168.0.1/", "http://10.0.0.5/",
    "http://169.254.169.254/", "file:///C:/Windows/win.ini", "ftp://exemplo.com/", "http://[::1]/",
])
def test_nao_abre_endereco_da_rede_local(url):
    with pytest.raises(sites.EnderecoProibido):
        sites.conferir_endereco(url)
    assert sites.analisar(url)["no_ar"] is False  # vira "o site não abre", sem acessar nada


def test_porta_fora_do_padrao_bloqueada():
    with pytest.raises(sites.EnderecoProibido):
        sites.conferir_endereco("http://8.8.8.8:8080/")
