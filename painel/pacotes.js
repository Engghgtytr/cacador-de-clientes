// Tabela de preços para restaurantes, montada a partir do config.json.
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const preco = (v) => (v == null ? 'Sob consulta' : `R$ ${Number(v).toLocaleString('pt-BR')}`);

  function el(tag, cls, texto) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (texto != null) e.textContent = texto;
    return e;
  }

  fetch('/api/dados', { cache: 'no-store' })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((D) => {
      const pacotes = (D.pacotes && D.pacotes.restaurante) || [];
      const quem = [D.seu_nome, D.seu_contato].filter(Boolean).join(' · ');
      $('quem').textContent = quem ? `Proposta de ${quem}` : '';
      $('obs').textContent = D.observacao_pacotes || '';
      const grade = el('div', 'grade-pacotes');
      pacotes.forEach((p, i) => {
        const card = el('section', `pacote${i === pacotes.length - 1 ? ' pacote--completo' : ''}`);
        card.append(el('h2', null, p.nome), el('p', 'pacote__preco', preco(p.preco)));
        const ul = el('ul');
        (p.inclui || []).forEach((item) => ul.append(el('li', null, item)));
        card.append(ul);
        grade.append(card);
      });
      $('tabela').replaceChildren(grade);
    })
    .catch((e) => {
      console.error(e);
      $('tabela').replaceChildren(el('p', 'aviso aviso--erro', 'Não consegui ler os pacotes. Abra esta página pelo painel (atalho ABRIR O CAÇADOR).'));
    });
})();
