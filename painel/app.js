// Painel do Caçador de clientes. Lê /api/dados e grava o status em /api/status.
// Todo texto entra por textContent: nada vindo do mapa vira HTML.
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  function h(tag, props, ...filhos) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'style') el.style.cssText = v; // via CSSOM: permitido pela CSP (atributo style não é)
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const f of filhos.flat()) if (f != null && f !== false) el.append(f instanceof Node ? f : document.createTextNode(String(f)));
    return el;
  }

  const SITUACAO = {
    sem_site: ['Sem site', 'etiqueta--forte'],
    site_fora: ['Site fora do ar', 'etiqueta--erro'],
    site_com_problema: ['Site com problema', 'etiqueta--alerta'],
    nao_conferido: ['Site não conferido', ''],
    site_ok: ['Site ok', 'etiqueta--ok'],
  };
  const CONTATO = { whatsapp: 'WhatsApp', telefone: 'Telefone fixo', instagram: 'Instagram', procurar: 'Contato a procurar' };
  const RAMO = { barbearia: 'Barbearia', restaurante: 'Restaurante' };
  const ETAPAS = {
    fila: { nome: 'Fila', filtro: (l) => l.status === 'novo' && l.situacao !== 'site_ok' },
    follow: { nome: 'Follow-up', filtro: (l) => l.follow_up_vencido },
    enviadas: { nome: 'Enviadas', filtro: (l) => l.status === 'enviado' || l.status === 'follow_up' },
    conversa: { nome: 'Responderam', filtro: (l) => l.status === 'respondeu' || l.status === 'fechou' },
    arquivo: { nome: 'Arquivo', filtro: (l) => l.status === 'nao_quer' || l.status === 'descartado' || (l.status === 'novo' && l.situacao === 'site_ok') },
  };
  const POR_PAGINA = 60;

  let D = null;
  let etapa = 'fila';
  let ramo = 'todos';
  let busca = '';
  let mostrando = POR_PAGINA;
  let atual = null;

  // ---------- dados ----------
  async function carregar() {
    try {
      const r = await fetch('/api/dados', { cache: 'no-store' });
      if (!r.ok) throw new Error(r.status);
      D = await r.json();
    } catch (e) {
      console.error(e);
      $('origem').textContent = 'Não consegui ler os dados. O painel está aberto pelo atalho ABRIR O CAÇADOR?';
      return;
    }
    $('origem').textContent = D.leads.length
      ? `${D.leads.length} negócios em ${D.cidade} · lista do mapa de ${new Date(D.buscado_em).toLocaleDateString('pt-BR')}`
      : 'Nenhuma empresa ainda';
    montarFiltros();
    desenhar();
  }

  async function marcar(lead, status, obs) {
    const r = await fetch('/api/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Cacador': '1' },
      body: JSON.stringify({ id: lead.id, status, obs }),
    });
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(corpo.erro || 'Não consegui salvar. Tente de novo.');
    lead.status = corpo.status;
    if (obs != null) lead.obs = obs;
    lead.historico = (lead.historico || []).concat({ status: corpo.status, quando: new Date().toISOString() });
    lead.follow_up_vencido = false;
    D.enviados_hoje = corpo.enviados_hoje;
  }

  // ---------- topo e filtros ----------
  function cota() {
    const usados = D.enviados_hoje;
    const limite = D.limite_por_dia;
    const cheia = usados >= limite;
    $('cota').replaceChildren(
      h('p', null, 'Mensagens hoje: ', h('strong', { text: `${usados} de ${limite}` }), cheia ? ' · limite do dia atingido' : ''),
      h('div', { class: `barra${cheia ? ' barra--cheia' : ''}`, role: 'presentation' },
        h('span', { style: `transform: scaleX(${Math.min(usados / limite, 1)})` })),
    );
  }

  function montarFiltros() {
    const ramos = ['todos', ...new Set(D.leads.map((l) => l.ramo))];
    $('ramos').replaceChildren(...ramos.map((r) => h('button', {
      class: 'chip', type: 'button', 'aria-pressed': String(r === ramo),
      text: r === 'todos' ? 'Todos' : `${RAMO[r] || r}s`,
      onclick: () => { ramo = r; mostrando = POR_PAGINA; montarFiltros(); desenhar(); },
    })));
  }

  function abas(base) {
    $('abas').replaceChildren(...Object.entries(ETAPAS).map(([id, e]) => h('button', {
      class: 'aba', type: 'button', role: 'tab', 'aria-selected': String(id === etapa),
      onclick: () => { etapa = id; mostrando = POR_PAGINA; atual = null; desenhar(); },
    }, e.nome, h('span', { class: 'n', text: base.filter(e.filtro).length }))));
  }

  // ---------- lista ----------
  function filtrados() {
    const termo = busca.trim().toLowerCase();
    const base = D.leads.filter((l) => (ramo === 'todos' || l.ramo === ramo)
      && (!termo || `${l.nome} ${l.bairro} ${l.endereco}`.toLowerCase().includes(termo)));
    return { base, lista: base.filter(ETAPAS[etapa].filtro) };
  }

  function etiquetas(l) {
    const [txt, cls] = SITUACAO[l.situacao];
    return h('span', { class: 'etiquetas' },
      h('span', { class: `etiqueta ${cls}`, text: txt }),
      h('span', { class: 'etiqueta', text: CONTATO[l.contato.tipo] }),
      l.follow_up_vencido ? h('span', { class: 'etiqueta etiqueta--alerta', text: 'Hora do follow-up' }) : null);
  }

  function desenhar() {
    cota();
    const { base, lista } = filtrados();
    abas(base);
    $('contagem').textContent = lista.length
      ? `${lista.length} ${lista.length === 1 ? 'empresa' : 'empresas'}${etapa === 'fila' ? ', das mais promissoras para as menos' : ''}`
      : '';
    const ul = $('lista');
    if (!lista.length) {
      ul.replaceChildren(h('li', { class: 'vazio' }, h('strong', { text: 'Nada por aqui.' }),
        etapa === 'fila' ? 'Troque o filtro ou rode "BUSCAR EMPRESAS" para atualizar a lista.' : 'Quando você mudar o status de uma empresa, ela aparece aqui.'));
      $('mais').hidden = true;
      if (!atual || !lista.includes(atual)) ficha(null);
      return;
    }
    ul.replaceChildren(...lista.slice(0, mostrando).map((l) => h('li', null, h('button', {
      class: 'item', type: 'button', 'aria-current': String(l === atual),
      onclick: () => { atual = l; desenhar(); ficha(l, true); },
    },
    h('span', { class: 'item__nome', text: l.nome }),
    h('span', { class: 'item__meta', text: [RAMO[l.ramo], l.bairro || l.endereco].filter(Boolean).join(' · ') }),
    etiquetas(l)))));
    $('mais').hidden = lista.length <= mostrando;
    $('mais').textContent = `Mostrar mais (${lista.length - mostrando} restantes)`;
    if (!atual || !lista.includes(atual)) {
      atual = window.matchMedia('(max-width: 860px)').matches ? null : lista[0];
      if (atual) ul.querySelector('.item').setAttribute('aria-current', 'true');
    }
    ficha(atual);
  }

  // ---------- ficha ----------
  // replaceChildren escreveria "null" na tela: aqui os vazios são ignorados.
  const colocar = (alvo, ...itens) => alvo.replaceChildren(...itens.flat(Infinity).filter((x) => x != null && x !== false));
  const chaveRascunho = (l, tipo) => `rascunho:${tipo}:${l.id}`;
  function lerRascunho(l, tipo, padrao) {
    try { return sessionStorage.getItem(chaveRascunho(l, tipo)) ?? padrao; } catch (e) { return padrao; }
  }
  function gravarRascunho(l, tipo, texto) {
    try { sessionStorage.setItem(chaveRascunho(l, tipo), texto); } catch (e) { /* sem armazenamento: tudo bem */ }
  }

  function linkMaps(l) {
    const q = l.lat && l.lon ? `${l.nome} ${l.endereco || ''}`.trim() : `${l.nome} ${D.cidade}`;
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
  }
  function linkGoogle(l) {
    return `https://www.google.com/search?q=${encodeURIComponent(`${l.nome} ${l.bairro || ''} ${D.cidade} site`)}`;
  }

  function ficha(l, focar) {
    const area = document.querySelector('.area');
    const el = $('ficha');
    if (!l) {
      area.classList.remove('mostrando-ficha');
      el.replaceChildren(h('div', { class: 'vazio' }, h('strong', { text: 'Escolha uma empresa na lista.' }), 'A ficha mostra o que achamos, o contato e a mensagem pronta.'));
      return;
    }
    area.classList.add('mostrando-ficha');
    const followUp = l.follow_up_vencido;
    const tipoMsg = followUp ? 'follow' : 'primeira';
    const texto = h('textarea', { id: 'mensagem', 'aria-describedby': 'dica-msg' });
    texto.value = lerRascunho(l, tipoMsg, followUp ? l.mensagem_follow_up : l.mensagem);
    texto.addEventListener('input', () => { gravarRascunho(l, tipoMsg, texto.value); atualizarZap(); });

    const aviso = h('div', { role: 'status', 'aria-live': 'polite' });
    const mostrarAviso = (msg, tipo) => aviso.replaceChildren(msg ? h('p', { class: `aviso aviso--${tipo}`, text: msg }) : '');

    // Conferência antes de mandar: o mapa pode estar desatualizado.
    const precisaConferir = l.status === 'novo' && (l.situacao === 'sem_site' || l.situacao === 'nao_conferido');
    const conferi = h('input', { type: 'checkbox', id: 'conferi' });
    conferi.addEventListener('change', atualizarZap);

    const zap = h('a', { class: 'botao botao--primario', target: '_blank', rel: 'noopener' }, 'Abrir no WhatsApp');
    function atualizarZap() {
      const bloqueado = (precisaConferir && !conferi.checked) || D.enviados_hoje >= D.limite_por_dia;
      if (!l.contato.whatsapp) return;
      zap.href = bloqueado ? '' : `https://wa.me/${l.contato.whatsapp}?text=${encodeURIComponent(texto.value)}`;
      if (bloqueado) zap.removeAttribute('href');
      zap.setAttribute('aria-disabled', String(bloqueado));
    }
    zap.addEventListener('click', (ev) => {
      if (zap.getAttribute('aria-disabled') === 'true') {
        ev.preventDefault();
        mostrarAviso(D.enviados_hoje >= D.limite_por_dia ? 'Limite do dia atingido. Continue amanhã.' : 'Antes, confira no Google se eles realmente não têm site e marque a caixa.', 'erro');
      } else {
        mostrarAviso('Mandou? Clique em "Marcar como enviada" para guardar.', 'ok');
      }
    });

    const copiar = h('button', { class: 'botao botao--secundario', type: 'button' }, 'Copiar mensagem');
    copiar.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(texto.value); mostrarAviso('Mensagem copiada.', 'ok'); }
      catch (e) { texto.select(); mostrarAviso('Não consegui copiar sozinho: o texto ficou selecionado, use Ctrl+C.', 'erro'); }
    });

    const obs = h('textarea', { id: 'obs', class: 'obs' });
    obs.value = l.obs || '';

    function botaoStatus(rotulo, status, primario) {
      const b = h('button', { class: `botao ${primario ? 'botao--primario' : 'botao--secundario'}`, type: 'button' }, rotulo);
      b.addEventListener('click', async () => {
        if (status === 'nao_quer' && !confirm(`${l.nome} não vai mais aparecer na fila. Confirmar?`)) return;
        const todos = el.querySelectorAll('.acoes--status .botao');
        todos.forEach((x) => { x.disabled = true; });
        b.textContent = 'Salvando…';
        try {
          await marcar(l, status, obs.value);
          mostrarAviso(`Salvo: ${D.rotulos[status]}.`, 'ok');
          const anterior = atual;
          atual = null;
          desenhar();
          if (anterior && !ETAPAS[etapa].filtro(anterior)) $('ficha').focus({ preventScroll: true });
        } catch (e) {
          mostrarAviso(e.message, 'erro');
          todos.forEach((x) => { x.disabled = false; });
          b.textContent = rotulo;
        }
      });
      return b;
    }

    const a = l.analise;
    const achado = l.situacao === 'sem_site'
      ? [h('p', { text: l.rede_social ? 'No mapa só aparece uma rede social, sem site próprio.' : 'No mapa não aparece site.' })]
      : l.situacao === 'nao_conferido'
        ? [h('p', null, 'Tem site no mapa, mas ainda não foi conferido: ', h('a', { href: l.site, target: '_blank', rel: 'noopener', text: l.site }))]
        : [h('p', null, 'Site: ', h('a', { href: l.site, target: '_blank', rel: 'noopener', text: l.site })),
          a && a.problemas.length ? h('ul', null, a.problemas.map((p) => h('li', { text: p }))) : h('p', { text: 'Não achamos problema no site.' })];

    const contatos = h('div', { class: 'contatos' },
      h('a', { class: 'botao botao--secundario', href: linkMaps(l), target: '_blank', rel: 'noopener' }, 'Conferir no Google Maps'),
      h('a', { class: 'botao botao--secundario', href: linkGoogle(l), target: '_blank', rel: 'noopener' }, 'Procurar site no Google'),
      l.contato.telefones.map((t) => h('a', { class: 'botao botao--secundario', href: `tel:+${t.numero}` }, `Ligar ${t.texto}`)),
      l.contato.instagram ? h('a', { class: 'botao botao--secundario', href: `https://www.instagram.com/${encodeURIComponent(l.contato.instagram)}/`, target: '_blank', rel: 'noopener' }, `Instagram @${l.contato.instagram}`) : null);

    const enviar = h('div', { class: 'acoes' },
      l.contato.whatsapp ? zap : null,
      copiar);

    const statusBtns = followUp || l.status === 'enviado' || l.status === 'follow_up'
      ? [followUp ? botaoStatus('Marcar follow-up como enviado', 'follow_up', true) : null,
        botaoStatus('Respondeu', 'respondeu'), botaoStatus('Não quer contato', 'nao_quer'), botaoStatus('Descartar', 'descartado')]
      : l.status === 'respondeu'
        ? [botaoStatus('Fechou negócio', 'fechou', true), botaoStatus('Não quer contato', 'nao_quer'), botaoStatus('Descartar', 'descartado')]
        : l.status === 'novo'
          ? [botaoStatus('Marcar como enviada', 'enviado', true), botaoStatus('Já tem site / descartar', 'descartado'), botaoStatus('Não quer contato', 'nao_quer')]
          : [botaoStatus('Voltar para a fila', 'novo')];

    colocar(el,
      h('button', { class: 'botao botao--secundario voltar', type: 'button', onclick: () => { atual = null; desenhar(); window.scrollTo(0, 0); } }, 'Voltar à lista'),
      h('h2', { text: l.nome }),
      h('p', { class: 'meta', text: [RAMO[l.ramo], l.cozinha, l.endereco].filter(Boolean).join(' · ') }),
      h('p', { class: 'meta', text: `Situação: ${D.rotulos[l.status]}` }),
      h('div', { class: 'achado' }, h('strong', { text: 'O que encontramos' }), ...achado),
      h('h3', { text: 'Contato' }),
      l.contato.tipo === 'procurar' ? h('p', { class: 'dica', text: 'O mapa não tem telefone nem Instagram. Procure no Google Maps: muitas vezes o número está lá.' }) : null,
      contatos,
      h('h3', null, h('label', { for: 'mensagem', text: followUp ? 'Mensagem de follow-up' : 'Mensagem (pode editar)' })),
      texto,
      h('p', { class: 'dica', id: 'dica-msg', text: l.contato.whatsapp ? 'O WhatsApp abre com o texto pronto: você confere e aperta enviar.' : 'Sem celular no mapa: copie a mensagem e mande pelo Instagram, ou ligue.' }),
      precisaConferir ? h('label', { class: 'conferir' }, conferi, 'Conferi no Google que eles realmente não têm site') : null,
      enviar,
      aviso,
      h('h3', null, h('label', { for: 'obs', text: 'Anotações' })),
      obs,
      h('div', { class: 'acoes acoes--status' }, statusBtns),
      l.historico && l.historico.length ? [h('h3', { text: 'Histórico' }), h('ul', { class: 'historico' },
        l.historico.slice().reverse().map((x) => h('li', { text: `${new Date(x.quando).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })} · ${D.rotulos[x.status]}` })))] : null,
    );
    atualizarZap();
    if (focar) el.focus({ preventScroll: !window.matchMedia('(max-width: 860px)').matches });
    if (focar && window.matchMedia('(max-width: 860px)').matches) window.scrollTo(0, 0);
  }

  // ---------- eventos ----------
  let espera;
  $('busca').addEventListener('input', (e) => {
    clearTimeout(espera);
    espera = setTimeout(() => { busca = e.target.value; mostrando = POR_PAGINA; desenhar(); }, 150);
  });
  $('mais').addEventListener('click', () => { mostrando += POR_PAGINA * 2; desenhar(); });

  carregar();
})();
