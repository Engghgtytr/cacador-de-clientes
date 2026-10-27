# Caçador de clientes

Acha barbearias e restaurantes de uma cidade que **não têm site** (ou têm site ruim), monta uma ficha de cada um e deixa a **mensagem pronta e personalizada**. Quem envia é você, uma de cada vez: o programa não dispara nada sozinho.

## Por que não é automático

- **Lei e bom senso:** mensagem comercial em massa, sem a pessoa ter pedido, é spam e esbarra na LGPD. Aqui cada mensagem é individual, fala do negócio de verdade e oferece um jeito de parar ("é só me avisar").
- **Bloqueio:** WhatsApp e Gmail banem quem dispara em massa. O painel tem um **limite por dia** (15, no `config.json`).
- **Resultado:** mensagem pessoal tem muito mais resposta que mensagem genérica.

## Como funciona

1. **Buscar:** baixa os negócios do [OpenStreetMap](https://www.openstreetmap.org) (grátis, sem chave). O mapa é colaborativo e pode estar desatualizado.
2. **Conferir os sites:** abre a página inicial de quem tem site e anota se está fora do ar, sem cadeado (https), sem versão para celular ou lento.
3. **Priorizar:** sem site + WhatsApp vem primeiro.
4. **Painel:** ficha, botões para conferir no Google Maps, mensagem editável, botão que abre o WhatsApp com o texto pronto, status (enviada, respondeu, fechou, não quer contato) e lembrete de follow-up depois de 5 dias.
5. **Tabela de preços:** `pacotes.html`, para mandar ao restaurante (Ctrl+P → Salvar como PDF).

Antes de mandar para quem "não tem site", o painel pede para você **conferir no Google**: o mapa pode não saber do site.

## Usar (Windows)

| Atalho | O que faz |
|---|---|
| `BUSCAR EMPRESAS.bat` | Atualiza a lista e confere os sites (alguns minutos) |
| `ABRIR O CACADOR.bat` | Abre o painel no navegador (deixe a janela aberta) |

Pelo terminal: `python cacador.py buscar`, `analisar`, `painel`, `resumo`. Testes: `.venv\Scripts\python.exe -m pytest`.

Instalar do zero: `python -m venv .venv` e `.venv\Scripts\python.exe -m pip install -r requirements.txt`.

## Configurar (`config.json`)

- `cidade`, `ramos` (barbearia, restaurante), `seu_nome`, `seu_contato`
- `limite_por_dia`, `dias_para_follow_up`
- `demos`: os sites de exemplo citados na mensagem (projetos fictícios, e a mensagem diz isso)
- `pacotes`: os preços. `null` aparece como "sob consulta"

## Segurança e dados

- O painel roda só no seu PC (`127.0.0.1`), não fica aberto na rede.
- A lista de empresas e o seu histórico ficam em `dados/`, que não vai para o Git.
- Dados das empresas: © colaboradores do OpenStreetMap (licença ODbL).
