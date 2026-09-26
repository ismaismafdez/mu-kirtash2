/* =====================================================================
   MU Kirtash · JavaScript del cliente
   Las páginas ya llegan generadas por Hugo. Este archivo solo añade:
   SEASON (filtro de versión) · SEARCH (buscador sobre /index.json)
   TOC (sección activa) · BACK (volver al catálogo) · detalles de UI
   ===================================================================== */
(() => {
'use strict';

const body = document.body;
const DEFAULT_SEASON = body.dataset.defaultSeason || 's21';
const INDEX_URL = body.dataset.index || '/index.json';
const GROUP_LIMIT = parseInt(body.dataset.groupLimit, 10) || 6;
const IS_CATALOG = body.dataset.kind === 'home' || body.dataset.kind === 'section';
const KEYS = { season: 'mukirtash:season', lastCatalog: 'mukirtash:last-catalog', restore: 'mukirtash:restore' };

const $view = document.getElementById('view');
const $searchView = document.getElementById('search-view');
const $search = document.getElementById('search');
const $clear = document.getElementById('search-clear');
const $seasonSelect = document.getElementById('season-select');
const $live = document.getElementById('live');

/* ---------- UTILS ---------- */
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);
const norm = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const tokenize = q => norm(q).split(/[\s,.;:/·—–-]+/).filter(Boolean);
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const store = (area => ({
  get: k => { try { return area().getItem(k); } catch { return null; } },
  set: (k, v) => { try { area().setItem(k, v); } catch { /* modo privado */ } }
}));
const local = store(() => window.localStorage);
const session = store(() => window.sessionStorage);

function highlight(text, terms) {
  const str = String(text ?? '');
  if (!terms.length) return esc(str);
  const chars = str.split('');
  const normChars = chars.map(norm);
  if (normChars.some(n => n.length !== 1)) return esc(str);
  const hay = normChars.join('');
  const ranges = [];
  terms.forEach(t => {
    let from = 0, i;
    while ((i = hay.indexOf(t, from)) !== -1) { ranges.push([i, i + t.length]); from = i + t.length; }
  });
  if (!ranges.length) return esc(str);
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [ranges[0].slice()];
  ranges.slice(1).forEach(r => {
    const last = merged[merged.length - 1];
    if (r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push(r.slice());
  });
  let out = '', pos = 0;
  merged.forEach(([a, b]) => { out += esc(str.slice(pos, a)) + '<mark>' + esc(str.slice(a, b)) + '</mark>'; pos = b; });
  return out + esc(str.slice(pos));
}

/* ---------- ÍNDICE (/index.json, generado por Hugo) ---------- */
let indexPromise = null;
function loadIndex() {
  if (!indexPromise) {
    indexPromise = fetch(INDEX_URL)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => {
        data.catById = new Map(data.categories.map(c => [c.id, c]));
        data.guides.forEach(g => {
          g._idx = {
            title: norm(g.title),
            tags: norm((g.tags || []).join(' ')),
            cat: norm(`${data.catById.get(g.category)?.label || ''} ${data.catById.get(g.category)?.singular || ''}`),
            desc: norm(g.description)
          };
        });
        return data;
      })
      .catch(err => { indexPromise = null; throw err; });
  }
  return indexPromise;
}

/* =====================================================================
   SEASON
   ===================================================================== */
const seasonIds = [...$seasonSelect.options].map(o => o.value);
const seasonLabel = id => [...$seasonSelect.options].find(o => o.value === id)?.textContent || id;
let season = seasonIds.includes(local.get(KEYS.season)) ? local.get(KEYS.season) : DEFAULT_SEASON;

function setSeason(id) {
  if (!seasonIds.includes(id)) return;
  season = id;
  local.set(KEYS.season, id);
  applySeason();
  if (searchOpen()) renderSearch();
}

function applySeason() {
  $seasonSelect.value = season;
  document.querySelectorAll('.season-btn').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.season === season)));
  document.querySelectorAll('[data-season-label]').forEach(el => { el.textContent = seasonLabel(season); });

  // Catálogo: ocultar tarjetas de otras Seasons y respetar el límite por grupo en portada
  const area = $view.querySelector('[data-filterable]');
  if (area) {
    const inSeason = card => card.dataset.seasons.split(' ').includes(season);
    const groups = area.querySelectorAll('[data-group]');
    if (groups.length) {
      groups.forEach(group => {
        let shown = 0;
        group.querySelectorAll('.card').forEach(card => {
          const ok = inSeason(card) && shown < GROUP_LIMIT;
          card.hidden = !ok;
          if (ok) shown++;
        });
        group.hidden = shown === 0;
      });
    } else {
      area.querySelectorAll('.card').forEach(card => { card.hidden = !inSeason(card); });
    }
    const anyVisible = !!area.querySelector('.card:not([hidden])');
    area.hidden = !anyVisible;
    const empty = $view.querySelector('[data-season-empty]');
    if (empty) empty.hidden = anyVisible;
  }

  // Guía: aviso si no aplica a la Season elegida
  const guide = $view.querySelector('[data-guide-seasons]');
  const mismatch = $view.querySelector('[data-season-mismatch]');
  if (guide && mismatch) mismatch.hidden = guide.dataset.guideSeasons.split(' ').includes(season);

  // Contadores reales por Season (necesitan el índice; si no carga, se quedan los de Hugo)
  loadIndex().then(data => {
    const counts = { all: 0 };
    data.categories.forEach(c => { counts[c.id] = 0; });
    data.guides.forEach(g => { if (g.seasons.includes(season)) { counts[g.category]++; counts.all++; } });
    document.querySelectorAll('[data-count]').forEach(el => {
      if (el.closest('#search-view')) return;
      if (el.dataset.count in counts) el.textContent = counts[el.dataset.count];
    });
    document.querySelectorAll('[data-season-count]').forEach(el => {
      el.textContent = data.guides.filter(g => g.seasons.includes(el.dataset.seasonCount)).length;
    });
  }).catch(() => {});
}

/* =====================================================================
   SEARCH
   Puntuación: título > tags > categoría > descripción (todos los términos deben aparecer).
   ===================================================================== */
let searchCat = 'all';

function scoreGuide(g, terms) {
  let score = 0;
  for (const t of terms) {
    let s = 0;
    const inTitle = g._idx.title.includes(t);
    if (g._idx.title === t) s += 40;
    if (g._idx.title.startsWith(t)) s += 16;
    if (inTitle) s += 10 + 8 * t.length / g._idx.title.length;
    if (g._idx.tags.includes(t)) s += 6;
    if (g._idx.cat.includes(t)) s += 4;
    if (!inTitle && g._idx.desc.includes(t)) s += 2;
    if (!s) return 0;
    score += s;
  }
  return score;
}
const searchGuides = (terms, list) => list
  .map(g => ({ g, s: scoreGuide(g, terms) }))
  .filter(r => r.s > 0)
  .sort((a, b) => b.s - a.s || a.g.title.localeCompare(b.g.title))
  .map(r => r.g);

function Card(g, c, terms) {
  const seasons = g.seasons.map(s => `<span class="tag">${esc(s === 'archivo' ? 'Archivo' : s.toUpperCase())}</span>`).join('');
  return `
    <a class="card" href="${esc(g.url)}" style="--cat:${esc(c.color)}">
      <span class="card-top"><span class="card-icon">${c.icon}</span><span class="card-cat">${esc(c.singular)}</span></span>
      <h3 class="card-title">${highlight(g.title, terms)}</h3>
      <p class="card-desc">${highlight(g.description, terms)}</p>
      <span class="card-foot">${seasons}${g.status === 'demo' ? '<span class="tag tag-demo">Ejemplo</span>' : ''}</span>
    </a>`;
}
function Empty(title, text, actions = '') {
  return `<div class="empty"><h2>${esc(title)}</h2><p>${text}</p>${actions ? `<div class="empty-actions">${actions}</div>` : ''}</div>`;
}

const searchOpen = () => !$searchView.hidden;
function showSearchView(html) {
  $searchView.innerHTML = html;
  if (!searchOpen()) {
    $searchView.hidden = false;
    $view.hidden = true;
    window.scrollTo({ top: 0 });
  }
}
function closeSearch() {
  $searchView.hidden = true;
  $searchView.innerHTML = '';
  $view.hidden = false;
  searchCat = 'all';
}
function syncUrl(q) {
  try {
    const url = new URL(location.href);
    if (q) url.searchParams.set('q', q); else url.searchParams.delete('q');
    history.replaceState(history.state, '', url);
  } catch { /* file:// */ }
}

function renderSearch() {
  const q = $search.value;
  const terms = tokenize(q);
  $clear.hidden = !q;
  syncUrl(q.trim());
  if (!terms.length) { closeSearch(); return; }

  loadIndex().then(data => {
    if ($search.value !== q) return; // respuesta antigua
    const matched = searchGuides(terms, data.guides.filter(g => g.seasons.includes(season)));
    const counts = { all: matched.length };
    matched.forEach(g => { counts[g.category] = (counts[g.category] || 0) + 1; });
    if (searchCat !== 'all' && !counts[searchCat]) searchCat = 'all';
    const results = searchCat === 'all' ? matched : matched.filter(g => g.category === searchCat);

    const chipIds = ['all', ...data.categories.map(c => c.id).filter(id => counts[id])];
    const chips = `<div class="chips" role="group" aria-label="Filtrar resultados">${chipIds.map(id => `
      <button type="button" class="chip" data-search-cat="${id}" aria-pressed="${searchCat === id}">
        ${esc(id === 'all' ? 'Todo' : data.catById.get(id).label)} <span class="chip-count">${counts[id]}</span></button>`).join('')}</div>`;

    let html = `
      <header class="results-head">
        <h1 class="results-title"><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><span>Resultados para «${esc(q.trim())}»</span></h1>
        <p class="results-meta">${results.length} ${results.length === 1 ? 'guía' : 'guías'} · ${esc(seasonLabel(season))}
          <button type="button" class="btn btn-small" data-clear-search>Borrar búsqueda</button></p>
        ${matched.length ? chips : ''}
      </header>`;

    if (results.length) {
      html += `<div class="grid">${results.map(g => Card(g, data.catById.get(g.category), terms)).join('')}</div>`;
    } else {
      const others = seasonIds.filter(id => id !== season)
        .map(id => ({ id, n: searchGuides(terms, data.guides.filter(g => g.seasons.includes(id))).length }))
        .filter(x => x.n);
      html += Empty('No hay guías que coincidan',
        `No encontramos resultados para «${esc(q.trim())}» en ${esc(seasonLabel(season))}. Prueba con otro nombre o un alias, por ejemplo «BC» o «DK».`,
        `<button type="button" class="btn btn-primary" data-clear-search>Borrar búsqueda</button>` +
        others.map(x => `<button type="button" class="btn" data-set-season="${x.id}">Ver ${x.n} en ${esc(seasonLabel(x.id))}</button>`).join(''));
    }
    showSearchView(html);
    $live.textContent = `${results.length} ${results.length === 1 ? 'resultado' : 'resultados'}`;
  }).catch(() => {
    showSearchView(Empty('El buscador no está disponible',
      'No se pudo cargar el índice de búsqueda. Si estás en local, arranca el sitio con <code>hugo server</code> en lugar de abrir los archivos directamente.'));
  });
}

function clearSearch() {
  $search.value = '';
  renderSearch();
  $search.focus();
}

/* =====================================================================
   TOC: resalta la sección visible
   ===================================================================== */
function setupToc() {
  const links = [...document.querySelectorAll('.toc a[href^="#"]')];
  const headings = links.map(a => document.getElementById(decodeURIComponent(a.hash.slice(1)))).filter(Boolean);
  if (!headings.length) return;
  let current = null;
  const setActive = link => {
    if (link === current) return;
    current = link;
    links.forEach(a => a.classList.toggle('is-active', a === link));
    const ul = link.closest('ul');
    if (ul && ul.scrollWidth > ul.clientWidth) {
      ul.scrollTo({ left: link.parentElement.offsetLeft - ul.offsetLeft - 8, behavior: reducedMotion() ? 'auto' : 'smooth' });
    }
  };
  // Sección activa = último encabezado que ya ha pasado el tercio superior de la pantalla
  const update = () => {
    const line = window.innerHeight * 0.3;
    let idx = 0;
    headings.forEach((h, i) => { if (h.getBoundingClientRect().top <= line) idx = i; });
    const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
    setActive(links[atBottom ? headings.length - 1 : idx]);
  };
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) { ticking = true; requestAnimationFrame(() => { ticking = false; update(); }); }
  }, { passive: true });
  update();
}

/* =====================================================================
   BACK: "Volver al catálogo" regresa a la última lista o búsqueda,
   en la misma posición de scroll
   ===================================================================== */
function rememberCatalog() {
  if (IS_CATALOG || searchOpen()) {
    session.set(KEYS.lastCatalog, JSON.stringify({ url: location.href, y: window.scrollY }));
  }
}
function setupBack() {
  const back = document.querySelector('[data-back]');
  let last = null;
  try { last = JSON.parse(session.get(KEYS.lastCatalog)); } catch { /* vacío */ }
  if (back && last && new URL(last.url).origin === location.origin) {
    back.href = last.url;
    back.addEventListener('click', () => session.set(KEYS.restore, JSON.stringify(last)));
  }
  // Al volver: restaurar el scroll guardado
  try {
    const r = JSON.parse(session.get(KEYS.restore));
    if (r && r.url === location.href) {
      session.set(KEYS.restore, '');
      requestAnimationFrame(() => window.scrollTo({ top: r.y, behavior: 'auto' }));
    }
  } catch { /* vacío */ }
}

/* =====================================================================
   EVENTS
   ===================================================================== */
$search.addEventListener('input', renderSearch);
$search.addEventListener('keydown', e => {
  if (e.key === 'Escape') { if ($search.value) clearSearch(); else $search.blur(); }
  if (e.key === 'Enter') {
    const first = $searchView.querySelector('.grid .card');
    if (first) { e.preventDefault(); first.focus(); }
  }
});
$clear.addEventListener('click', clearSearch);

document.addEventListener('keydown', e => {
  const tag = (e.target.tagName || '').toLowerCase();
  if (e.key === '/' && !e.metaKey && !e.ctrlKey && !e.altKey && !['input', 'textarea', 'select'].includes(tag)) {
    e.preventDefault(); $search.focus(); $search.select();
  }
});

$seasonSelect.addEventListener('change', () => setSeason($seasonSelect.value));
document.addEventListener('click', e => {
  const seasonBtn = e.target.closest('[data-season], [data-set-season]');
  if (seasonBtn) { setSeason(seasonBtn.dataset.season || seasonBtn.dataset.setSeason); return; }
  if (e.target.closest('[data-clear-search]')) { clearSearch(); return; }
  const chip = e.target.closest('[data-search-cat]');
  if (chip) { searchCat = chip.dataset.searchCat; renderSearch(); }
});

// Imagen rota: se vuelve al placeholder
document.querySelectorAll('img[data-fallback]').forEach(img => {
  img.addEventListener('error', () => { img.closest('.media')?.classList.remove('has-image'); img.remove(); }, { once: true });
});

// Menú móvil: la categoría activa siempre visible
const activeMobile = document.querySelector('.mobile-nav .is-active');
if (activeMobile) {
  const ul = activeMobile.closest('ul');
  const li = activeMobile.parentElement;
  if (li.offsetLeft + li.offsetWidth > ul.clientWidth) ul.scrollLeft = li.offsetLeft - 16;
}

window.addEventListener('pagehide', rememberCatalog);

/* ---------- INIT ---------- */
applySeason();
setupToc();
setupBack();
const initialQuery = new URLSearchParams(location.search).get('q');
if (initialQuery) { $search.value = initialQuery; renderSearch(); }
})();
