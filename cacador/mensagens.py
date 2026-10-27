"""Mensagens prontas e personalizadas. A pessoa sempre pode editar antes de enviar.

Regras: falar a verdade (o que achamos no mapa e no site), deixar claro que o exemplo é
fictício, oferecer sem pressão e dizer como parar de receber mensagens.
"""
from __future__ import annotations

SAIR = "Se preferir não receber mensagem, é só me avisar que eu não chamo mais."


def preco(valor) -> str:
    if valor is None:
        return "valor sob consulta"
    return f"R$ {valor:,.0f}".replace(",", ".")


def _local(lead: dict) -> str:
    return f" ({lead['bairro']})" if lead.get("bairro") else ""


def _problemas(lead: dict) -> str:
    probs = (lead.get("analise") or {}).get("problemas", [])[:2]
    return " e ".join(probs)


def _lista_pacotes(config: dict) -> str:
    linhas = []
    descricao = {
        0: "Site com cardápio",
        1: "Site + app para controlar o custo dos pratos",
        2: "Completo, com pedido por QR code que vai direto para a tela do garçom",
    }
    for i, p in enumerate(config.get("pacotes", {}).get("restaurante", [])):
        linhas.append(f"• {descricao.get(i, p['nome'])}: {preco(p.get('preco'))}")
    return "\n".join(linhas)


def primeira(lead: dict, situacao: str, config: dict) -> str:
    nome, cidade, eu = lead["nome"], config.get("cidade", ""), config.get("seu_nome", "")
    demo = config.get("demos", {}).get(lead["ramo"], "")
    ola = f"Oi, tudo bem? Aqui é o {eu}. Faço sites para {'restaurantes' if lead['ramo'] == 'restaurante' else 'barbearias'} de {cidade}."

    if situacao in ("site_fora", "site_com_problema"):
        achado = (f"Encontrei {nome}{_local(lead)} e dei uma olhada no site de vocês: {_problemas(lead)}. "
                  "Isso faz muita gente desistir antes de entrar em contato.")
    elif lead.get("rede_social") or lead.get("instagram"):
        achado = f"Encontrei {nome}{_local(lead)} pelo mapa e vi que vocês divulgam pelas redes, mas não achei um site próprio."
    else:
        achado = f"Encontrei {nome}{_local(lead)} pelo mapa e não achei um site de vocês."

    if lead["ramo"] == "barbearia":
        oferta = ("Um site com agendamento online deixa o cliente escolher o horário sozinho, a qualquer hora, "
                  f"sem ficar trocando mensagem. Montei um exemplo com uma barbearia fictícia para mostrar como fica: {demo}\n\n"
                  "Se fizer sentido, te mando uma proposta, sem compromisso.")
    else:
        oferta = (f"Montei um exemplo de cardápio digital com um restaurante fictício: {demo}\n\n"
                  f"Tenho três opções:\n{_lista_pacotes(config)}\n\n"
                  "Se quiser, te mando os detalhes de cada uma.")
    return f"{ola}\n\n{achado} {oferta}\n\n{SAIR}"


def follow_up(lead: dict, config: dict) -> str:
    return (f"Oi, tudo bem? Aqui é o {config.get('seu_nome', '')} de novo. Passando só para saber se você viu "
            f"a mensagem sobre o site d{'o' if lead['ramo'] == 'restaurante' else 'a'} {lead['nome']}. "
            "Se não for o momento, sem problema: não chamo mais.")
