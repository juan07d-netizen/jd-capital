const $ = id => document.getElementById(id);
const money = value => 'USD ' + Number(value || 0).toFixed(2);

function esc(value) {
  return String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

async function json(url, options) {
  const response = await fetch(url, options);
  let data = {};
  try { data = await response.json(); } catch {}
  if (!response.ok) throw new Error(data.detail || 'Error inesperado');
  return data;
}

async function load() {
  try {
    const metrics = await json('/api/metrics');
    $('balance').textContent = money(metrics.balance);
    $('income').textContent = money(metrics.income);
    $('expense').textContent = money(metrics.expense);
    $('net').textContent = money(metrics.net);
    const transactions = await json('/api/transactions');
    $('txs').innerHTML = transactions.transactions.length ? transactions.transactions.map(item => `<div class="row"><b>${esc(item.kind)}</b> ${money(item.amount)}<br><span class="muted">${esc(item.note)}</span></div>`).join('') : '<p class="muted">Sin movimientos.</p>';
    const opportunities = await json('/api/opportunities');
    $('opps').innerHTML = opportunities.opportunities.length ? opportunities.opportunities.map(item => `<div class="row"><b>${esc(item.name)}</b> <span class="tag">${esc(item.status)}</span><br>${esc(item.platform || '')}<br><span class="muted">${esc(item.note || '')}</span>${item.source_url ? `<br><a href="${esc(item.source_url)}" target="_blank" rel="noreferrer noopener">Fuente</a>` : ''}</div>`).join('') : '<p class="muted">Sin oportunidades.</p>';
    const runs = await json('/api/runs');
    $('hist').innerHTML = runs.runs.length ? runs.runs.map(item => `<div class="row"><b>${esc(item.status)}</b> · ${esc(item.created_at)}<br>${item.status === 'success' ? '<details><summary>Ver investigación</summary><div class="ok">' + esc(item.result || '') + '</div></details>' : '<span class="muted">' + esc(item.result || '') + '</span>'}</div>`).join('') : '<p class="muted">Sin investigaciones.</p>';
    const settings = await json('/api/settings');
    $('keyStatus').textContent = settings.configured ? 'Configurada en el almacén seguro del sistema' : 'Falta configurar una clave de OpenAI';
  } catch (error) { console.error(error); }
}

async function withButton(button, operation) {
  if (button.disabled) return;
  button.disabled = true;
  try { await operation(); } catch (error) { alert(error.message); }
  finally { button.disabled = false; }
}

async function tx() {
  const button = $('saveTransactionButton');
  await withButton(button, async () => {
    const idempotencyKey = crypto.randomUUID();
    await json('/api/transactions', {method: 'POST', headers: {'content-type': 'application/json', 'idempotency-key': idempotencyKey}, body: JSON.stringify({kind: $('kind').value, amount: $('amount').value, note: $('note').value})});
    $('amount').value = ''; $('note').value = ''; await load();
  });
}

async function opp() {
  await withButton($('saveOpportunityButton'), async () => {
    await json('/api/opportunities', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({name: $('oname').value, platform: $('platform').value, status: $('ostatus').value, expected_usd: $('expected').value, note: $('onote').value, source_url: $('source_url').value})});
    ['oname', 'platform', 'expected', 'onote', 'source_url'].forEach(id => $(id).value = ''); await load();
  });
}

async function saveKey() {
  const key = $('apiKey').value.trim();
  if (!key) { alert('Pegá una clave para guardar.'); return; }
  await withButton($('saveKeyButton'), async () => {
    await json('/api/settings', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({api_key: key})});
    $('apiKey').value = ''; alert('Clave guardada de forma segura.'); await load();
  });
}

async function removeKey() {
  await withButton($('removeKeyButton'), async () => {
    await json('/api/settings', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({api_key: ''})}); await load();
  });
}

async function runMission() {
  const out = $('out'); out.className = 'status'; out.textContent = 'Creando investigación...';
  await withButton($('runMissionButton'), async () => {
    const data = await json('/api/mission', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({mission: $('mission').value})});
    out.textContent = 'Investigando en la web...'; let tries = 0;
    const timer = setInterval(async () => {
      tries++;
      try {
        const job = await json('/api/jobs/' + data.job_id);
        if (job.status === 'success') { clearInterval(timer); out.className = 'ok'; out.textContent = job.result; await load(); }
        else if (job.status === 'error') { clearInterval(timer); out.className = 'err'; out.textContent = 'La investigación terminó con un error controlado.\n' + (job.error || ''); await load(); }
        else if (tries > 900) { clearInterval(timer); out.className = 'err'; out.textContent = 'La investigación sigue en curso. Podés cerrar el navegador; el trabajo queda guardado.'; await load(); }
      } catch {}
    }, 1000);
  });
}

$('saveTransactionButton').addEventListener('click', tx);
$('saveOpportunityButton').addEventListener('click', opp);
$('saveKeyButton').addEventListener('click', saveKey);
$('removeKeyButton').addEventListener('click', removeKey);
$('runMissionButton').addEventListener('click', runMission);
load();
