const state = { runId: null, results: [], generationPosition: null, generationTotal: 0 };

const el = (id) => document.getElementById(id);
const number = (value) => new Intl.NumberFormat('pt-BR').format(Number(value || 0));
const dateTime = (value) => new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Não foi possível concluir a operação.');
  return data;
}

function showMessage(text, isError = false) {
  const box = el('message');
  box.textContent = text;
  box.className = `message visible${isError ? ' error' : ''}`;
}

function clearMessage() {
  el('message').className = 'message';
}

async function loadHealth() {
  try {
    const data = await api('/api/health');
    el('status-dot').className = 'status-dot ok';
    el('status-text').textContent = 'Corpus disponível';
    el('documents-count').textContent = number(data.documents);
    el('chunks-count').textContent = number(data.chunks);
    el('embeddings-count').textContent = number(data.embeddings);
    el('graph-entities-count').textContent = number(data.graph_entities);
    el('graph-relations-count').textContent = number(data.graph_relations);
  } catch (error) {
    el('status-dot').className = 'status-dot error';
    el('status-text').textContent = 'Banco indisponível';
  }
}

function judgmentPayload(card, label) {
  return {
    run_id: state.runId,
    rank: Number(card.dataset.rank),
    chunk_id: card.dataset.chunkId,
    label,
    notes: card.querySelector('.note-input').value,
  };
}

async function saveJudgment(card, label) {
  const status = card.querySelector('.save-status');
  status.textContent = 'Salvando…';
  try {
    await api('/api/judgments', { method: 'PUT', body: JSON.stringify(judgmentPayload(card, label)) });
    card.dataset.label = label;
    card.querySelectorAll('.judgment-buttons button').forEach(button => {
      button.classList.toggle('selected', button.dataset.label === label);
    });
    card.querySelector('.note-row').classList.remove('hidden');
    status.textContent = 'Julgamento registrado.';
  } catch (error) {
    status.textContent = error.message;
  }
}

function renderResults(data) {
  state.runId = data.run_id;
  state.results = data.results;
  const list = el('results');
  list.innerHTML = '';
  const template = el('result-template');
  data.results.forEach(result => {
    const fragment = template.content.cloneNode(true);
    const card = fragment.querySelector('.result-card');
    card.dataset.rank = result.rank;
    card.dataset.chunkId = result.chunk_id.trim();
    if (result.label) card.dataset.label = result.label;
    card.querySelector('.result-rank').textContent = result.rank;
    card.querySelector('.result-meta').textContent = `Edição ${result.edition} · página ${result.page_number} · fragmento ${result.chunk_index}`;
    card.querySelector('.result-person').textContent = result.participant_name;
    card.querySelector('.result-text').textContent = result.chunk_text;
    card.querySelector('.score-box strong').textContent = `${(result.similarity * 100).toFixed(1)}%`;
    card.querySelector('.chunk-id').textContent = result.chunk_id.slice(0, 10);
    card.querySelector('.pdf-link').href = result.pdf_url;
    card.querySelector('.copy-button').addEventListener('click', async event => {
      await navigator.clipboard.writeText(result.chunk_text);
      event.currentTarget.textContent = 'Copiado';
      setTimeout(() => { event.currentTarget.textContent = 'Copiar trecho'; }, 1200);
    });
    card.querySelectorAll('.judgment-buttons button').forEach(button => {
      button.addEventListener('click', () => saveJudgment(card, button.dataset.label));
    });
    card.querySelector('.save-note').addEventListener('click', () => {
      if (!card.dataset.label) {
        card.querySelector('.save-status').textContent = 'Selecione primeiro um julgamento.';
        return;
      }
      saveJudgment(card, card.dataset.label);
    });
    if (result.label) {
      card.querySelectorAll('.judgment-buttons button').forEach(button => {
        button.classList.toggle('selected', button.dataset.label === result.label);
      });
      card.querySelector('.note-row').classList.remove('hidden');
      card.querySelector('.note-input').value = result.notes || '';
      card.querySelector('.save-status').textContent = 'Julgamento registrado.';
    }
    list.appendChild(fragment);
  });
  el('results-header').classList.remove('hidden');
  el('results-title').textContent = `${data.results.length} fragmentos para a consulta #${data.run_id}`;
  el('timing').textContent = `vetorização ${data.embedding_duration_ms} ms · busca ${data.retrieval_duration_ms} ms`;
}

function activateSection(sectionId) {
  document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.section === sectionId));
  document.querySelectorAll('.page-section').forEach(section => section.classList.toggle('active', section.id === sectionId));
}

async function loadRun(runId, jumpToPending = true) {
  clearMessage();
  try {
    const data = await api(`/api/runs/${runId}`);
    el('query').value = data.query;
    el('top-k').value = String(data.top_k);
    el('answer-panel').classList.add('hidden');
    renderResults(data);
    activateSection('search-section');
    showMessage(`Consulta #${runId} reaberta. Os julgamentos existentes foram preservados.`);
    if (jumpToPending) {
      requestAnimationFrame(() => {
        const pending = document.querySelector('.result-card:not([data-label])');
        if (pending) pending.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  } catch (error) {
    showMessage(error.message, true);
  }
}

function renderAnswer(answer, route) {
  el('answer-panel').classList.remove('hidden');
  const answerTitles = { semantic: 'Resposta do RAG', structural: 'Resposta do grafo', hybrid: 'Resposta híbrida' };
  el('answer-title').textContent = answerTitles[route.route] || 'Resposta do sistema';
  el('answer-model').textContent = `${answer.provider} · ${answer.model}`;
  el('answer-text').innerHTML = formatAnswer(answer.text);
  el('answer-sources').innerHTML = answer.sources.map(source => `
    <div class="answer-source">
      <strong>[${route.route === 'structural' ? 'D' : 'F'}${source.source_number}]</strong>
      <span>${escapeHtml(source.document_title || 'Trabalho recuperado')} · ${escapeHtml(source.participant_name)} · edição ${source.edition}</span>
      <a href="${source.pdf_url}" target="_blank" rel="noopener">abrir PDF</a>
    </div>`).join('');
  const routeNames = { semantic: 'RAG semântico', structural: 'consulta estrutural', hybrid: 'grafo + RAG' };
  el('route-summary').innerHTML = `
    <p><strong>Rota:</strong> ${escapeHtml(routeNames[route.route] || route.route)}</p>
    <p><strong>Motivo:</strong> ${escapeHtml(route.explanation)}</p>
    <p><strong>Consulta:</strong> <code>${escapeHtml(route.query_identifier)}</code></p>
    ${route.scope_documents !== null && route.scope_documents !== undefined ? `<p><strong>Documentos no filtro:</strong> ${number(route.scope_documents)}</p>` : ''}
    <p><strong>Registro de auditoria:</strong> #${route.route_run_id}</p>`;
  const sql = el('route-sql');
  if (route.sql) {
    sql.textContent = route.sql;
    sql.classList.remove('hidden');
  } else {
    sql.textContent = '';
    sql.classList.add('hidden');
  }
  const answerIdentifier = answer.answer_id ? `resposta #${answer.answer_id}` : `roteamento #${route.route_run_id}`;
  el('answer-meta').textContent = `${answerIdentifier} · método ${answer.prompt_version} · processamento ${answer.generation_duration_ms} ms`;
}

function formatAnswer(text) {
  return escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/^\* /gm, '• ')
    .replace(/\n/g, '<br>');
}

async function search() {
  const query = el('query').value.trim();
  if (query.length < 3) {
    showMessage('Escreva uma pergunta com pelo menos três caracteres.', true);
    return;
  }
  const button = el('search-button');
  button.disabled = true;
  button.classList.add('loading');
  clearMessage();
  el('answer-panel').classList.add('hidden');
  el('results-header').classList.add('hidden');
  el('results').innerHTML = '';
  try {
    const data = await api('/api/answer', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: Number(el('top-k').value) }),
    });
    renderAnswer(data.answer, data.route);
    if (data.run_id && data.results.length) {
      renderResults(data);
    } else {
      el('results-header').classList.add('hidden');
      el('results').innerHTML = '';
    }
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    button.disabled = false;
    button.classList.remove('loading');
  }
}

async function loadHistory() {
  const list = el('history-list');
  list.innerHTML = '<div class="empty">Carregando histórico…</div>';
  try {
    const data = await api('/api/runs?limit=50');
    if (!data.runs.length) {
      list.innerHTML = '<div class="empty">Nenhuma consulta registrada ainda.</div>';
      return;
    }
    list.innerHTML = data.runs.map(run => `
      <button type="button" class="history-row" data-run-id="${run.run_id}">
        <span class="history-id">#${run.run_id}</span>
        <span class="history-query" title="${escapeHtml(run.query_text)}">${escapeHtml(run.query_text)}</span>
        <span class="history-progress">${run.answer_id ? 'RAG respondido' : `${run.judged_count}/${run.top_k} avaliados`}</span>
        <span class="history-date">${dateTime(run.created_at)}</span>
      </button>`).join('');
    list.querySelectorAll('.history-row').forEach(row => {
      row.addEventListener('click', () => loadRun(Number(row.dataset.runId)));
    });
  } catch (error) {
    list.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

async function loadMetrics() {
  const cards = el('metric-cards');
  cards.innerHTML = '<div class="empty">Carregando métricas…</div>';
  try {
    const data = await api('/api/stats');
    const labels = data.labels || {};
    cards.innerHTML = [
      ['Consultas', data.runs],
      ['Respostas do RAG', data.answers],
      ['Resultados recuperados', data.retrieved_results],
      ['Julgamentos realizados', data.judgments],
      ['Respostas avaliadas', data.generation_judgments || 0],
      ['Relevantes', labels.relevant || 0],
      ['Parcialmente relevantes', labels.partial || 0],
      ['Não relevantes', labels.not_relevant || 0],
    ].map(([label, value]) => `<div class="metric-card"><strong>${number(value)}</strong><span>${label}</span></div>`).join('');
  } catch (error) {
    cards.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

function showGenerationMessage(text, isError = false) {
  const box = el('generation-message');
  box.textContent = text;
  box.className = `message visible${isError ? ' error' : ''}`;
}

function clearGenerationMessage() {
  el('generation-message').className = 'message';
}

async function loadGenerationEvaluation(openPending = true) {
  const list = el('generation-items');
  list.innerHTML = '<div class="empty">Carregando protocolo…</div>';
  clearGenerationMessage();
  try {
    const data = await api('/api/generation-evaluation');
    state.generationTotal = data.total;
    el('generation-progress').textContent = `${data.judged}/${data.total} respostas avaliadas`;
    list.innerHTML = data.items.map(item => `
      <button type="button" class="generation-item${item.judged_at ? ' judged' : ''}${state.generationPosition === item.position ? ' active' : ''}" data-position="${item.position}" title="${escapeHtml(item.query_text)}">
        ${item.position}
      </button>`).join('');
    list.querySelectorAll('.generation-item').forEach(button => {
      button.addEventListener('click', () => openGenerationItem(Number(button.dataset.position)));
    });
    if (openPending) {
      const pending = data.items.find(item => !item.judged_at);
      const target = pending || data.items[0];
      if (target) await openGenerationItem(target.position);
    }
  } catch (error) {
    list.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderGenerationSources(sources) {
  el('generation-sources').innerHTML = sources.map((source, index) => {
    const advisors = (source.advisor_names || []).join(', ') || 'não identificado';
    return `
      <details class="generation-source"${index === 0 ? ' open' : ''}>
        <summary><strong>[F${source.source_number}]</strong> ${escapeHtml(source.document_title)} · ${escapeHtml(source.participant_name)}</summary>
        <div class="generation-source-body">
          <p>Edição ${source.edition} · página ${source.page_number} · orientador: ${escapeHtml(advisors)}</p>
          <a href="${source.pdf_url}" target="_blank" rel="noopener">Abrir PDF original</a>
          <pre>${escapeHtml(source.page_text || source.chunk_text)}</pre>
        </div>
      </details>`;
  }).join('');
}

async function openGenerationItem(position) {
  clearGenerationMessage();
  try {
    const data = await api(`/api/generation-evaluation/items/${position}`);
    state.generationPosition = position;
    document.querySelectorAll('.generation-item').forEach(button => {
      button.classList.toggle('active', Number(button.dataset.position) === position);
    });
    el('generation-evaluation-card').classList.remove('hidden');
    el('generation-position').textContent = `${position} DE ${state.generationTotal}`;
    el('generation-query').textContent = data.query_text;
    el('generation-answer-meta').textContent = `resposta #${data.answer_id} · ${data.generator_provider} ${data.generator_model} · prompt ${data.prompt_version}`;
    el('generation-answer-text').innerHTML = formatAnswer(data.answer_text);
    renderGenerationSources(data.sources);
    el('score-faithfulness').value = data.faithfulness ?? '';
    el('score-citations').value = data.citation_correctness ?? '';
    el('score-completeness').value = data.completeness ?? '';
    el('score-separation').value = data.source_separation ?? '';
    el('score-refusal').value = data.refusal_appropriateness ?? '';
    el('generation-notes').value = data.notes || '';
    el('generation-save-status').textContent = data.judged_at ? 'Avaliação já registrada; você pode revisá-la.' : '';
    el('generation-previous').disabled = position <= 1;
    requestAnimationFrame(() => el('generation-evaluation-card').scrollIntoView({ behavior: 'smooth', block: 'start' }));
  } catch (error) {
    showGenerationMessage(error.message, true);
  }
}

async function saveGenerationJudgment() {
  const fields = [
    el('score-faithfulness'), el('score-citations'), el('score-completeness'),
    el('score-separation'), el('score-refusal'),
  ];
  if (fields.some(field => field.value === '')) {
    el('generation-save-status').textContent = 'Preencha todos os critérios antes de salvar.';
    return;
  }
  const position = state.generationPosition;
  const button = el('generation-save');
  button.disabled = true;
  el('generation-save-status').textContent = 'Salvando…';
  try {
    await api(`/api/generation-evaluation/items/${position}/judgment`, {
      method: 'PUT',
      body: JSON.stringify({
        faithfulness: Number(el('score-faithfulness').value),
        citation_correctness: Number(el('score-citations').value),
        completeness: Number(el('score-completeness').value),
        source_separation: Number(el('score-separation').value),
        refusal_appropriateness: el('score-refusal').value,
        notes: el('generation-notes').value,
      }),
    });
    el('generation-save-status').textContent = 'Avaliação registrada.';
    await loadGenerationEvaluation(false);
    if (position < state.generationTotal) {
      await openGenerationItem(position + 1);
    } else {
      showGenerationMessage('As dez respostas foram avaliadas.');
    }
  } catch (error) {
    el('generation-save-status').textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
}

document.querySelectorAll('.nav-item').forEach(button => {
  button.addEventListener('click', () => {
    activateSection(button.dataset.section);
    if (button.dataset.section === 'history-section') loadHistory();
    if (button.dataset.section === 'generation-evaluation-section') loadGenerationEvaluation();
    if (button.dataset.section === 'metrics-section') loadMetrics();
  });
});

el('search-button').addEventListener('click', search);
el('query').addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) search();
});
el('refresh-history').addEventListener('click', loadHistory);
el('refresh-metrics').addEventListener('click', loadMetrics);
el('generation-save').addEventListener('click', saveGenerationJudgment);
el('generation-previous').addEventListener('click', () => {
  if (state.generationPosition > 1) openGenerationItem(state.generationPosition - 1);
});
loadHealth();
const requestedRun = Number(new URLSearchParams(window.location.search).get('run'));
if (requestedRun > 0) loadRun(requestedRun);

