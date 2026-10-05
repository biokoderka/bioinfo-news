// BioInfoNews — wspólne funkcje dla wszystkich podstron.
// Każda wartość z JSON-a przechodzi przez esc() / safeUrl() zanim trafi do innerHTML.

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
}
function safeUrl(u) {
  return /^https?:\/\/[^\s"'<>]+$/i.test(u || '') ? u : null;
}

// Data "dzisiaj" w lokalnej strefie jako YYYY-MM-DD. Porównujemy stringi, bo
// new Date('2026-10-07') to północ UTC — wpis znikał już w swoim ostatnim dniu.
function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function isArchived(e) {
  if (e.archived) return true;
  return !!e.date_end && e.date_end < todayLocal();   // aktywny do końca dnia date_end
}
function parseDay(s) {                       // 'YYYY-MM-DD' jako data lokalna
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || '');
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(s);
}
function fmtDate(s, month = 'long') {
  if (!s) return '';
  return parseDay(s).toLocaleDateString('pl-PL', { day: 'numeric', month, year: 'numeric' });
}
// "8–10 października 2026", "30 września – 2 października 2026"
function fmtRange(a, b) {
  if (!b || b === a) return fmtDate(a);
  const A = parseDay(a), B = parseDay(b);
  const month = d => d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long' }).replace(/^\d+\s*/, '');
  if (A.getFullYear() !== B.getFullYear()) return `${fmtDate(a)} – ${fmtDate(b)}`;
  if (A.getMonth() !== B.getMonth()) return `${A.getDate()} ${month(A)} – ${B.getDate()} ${month(B)} ${B.getFullYear()}`;
  return `${A.getDate()}–${B.getDate()} ${month(B)} ${B.getFullYear()}`;
}
function timeAgo(s) {
  if (!s) return '';
  const days = Math.round((parseDay(todayLocal()) - parseDay(s)) / 86400000);
  if (days <= 0) return 'dziś';
  if (days === 1) return 'wczoraj';
  return `${days} dni temu`;
}

const TYPE_META = {
  'project':      { label: '🌿 Projekt',         cls: 'project' },
  'course-free':  { label: '📚 Kurs stały',       cls: 'course-free' },
  'course-dated': { label: '🗓️ Kurs z terminem',  cls: 'course-dated' },
  'meetup':       { label: '🤝 Meetup',           cls: 'meetup' },
  'other':        { label: '✦ Inne',              cls: 'other' },
};
const RESEARCH_TYPE_META = {
  'research':  { label: '📄 Artykuł',   cls: 'research' },
  'narzedzie': { label: '🔧 Narzędzie', cls: 'narzedzie' },
  'grant':     { label: '💰 Grant',     cls: 'grant' },
};
const ARTICLE_TYPE_META = {
  'przeglad':        { label: '📖 przeglądowy',     cls: 'art-przeglad' },
  'eksperymentalne': { label: '🧪 eksperymentalny', cls: 'art-eksperymentalne' },
  'narzedzie-art':   { label: '🔧 opis narzędzia',  cls: 'art-narzedzie-art' },
  'benchmark':       { label: '📊 benchmark',       cls: 'art-benchmark' },
  'protokol':        { label: '🧾 protokół',        cls: 'art-protokol' },
};
const TAG_LABELS = {
  'genomika': 'genomika', 'single-cell': 'single-cell', 'transkryptomika': 'transkryptomika',
  'proteomika': 'proteomika', 'mikrobiom': 'mikrobiom', 'ai-ml': 'AI / ML', 'struktury': 'struktury',
  'leki': 'leki', 'epidemiologia': 'epidemiologia', 'ewolucja': 'ewolucja', 'narzedzia': 'narzędzia',
  'bazy-danych': 'bazy danych', 'immunoinformatyka': 'immunoinformatyka', 'sieci-systemy': 'sieci i systemy',
  'wielo-omika': 'multi-omika', 'tekst-i-nlp': 'text mining / NLP', 'neuronauka': 'neuronauka',
  'modelowanie': 'modelowanie', 'kliniczne': 'medycyna / kliniczne', 'inne': 'inne',
  'polska': '🇵🇱 polskie źródło', 'granty': '💰 granty',
};
const tagClass = t => String(t).replace(/[^a-z0-9-]/gi, '');

function newsCard(e, { showArchivedBadge = false } = {}) {
  const tm = TYPE_META[e.type] || TYPE_META.other;
  const archived = showArchivedBadge && isArchived(e);
  let pills = '';
  if (e.free)       pills += `<span class="pill free">✓ bezpłatne</span>`;
  if (e.lang)       pills += `<span class="pill lang">${esc(e.lang)}</span>`;
  if (e.date_start) pills += `<span class="pill date">📅 ${esc(fmtRange(e.date_start, e.date_end))}</span>`;
  if (e.deadline)   pills += `<span class="pill deadline">⏰ do ${esc(fmtDate(e.deadline))}</span>`;
  if (e.location)   pills += `<span class="pill loc">📍 ${esc(e.location)}</span>`;
  const url = safeUrl(e.url);
  return `<article class="card${archived ? ' archived' : ''}">
    ${archived ? '<span class="archived-badge">ARCHIWUM</span>' : ''}
    <div class="card-header">
      <span class="type-pill ${tm.cls}">${tm.label}</span>
      <div class="card-title">${esc(e.title)}</div>
    </div>
    ${e.org ? `<div class="card-org">${esc(e.org)}</div>` : ''}
    <div class="card-desc">${esc(e.description)}</div>
    ${pills ? `<div class="card-meta">${pills}</div>` : ''}
    ${url ? `<a class="card-link" href="${esc(url)}" target="_blank" rel="noopener">Więcej info →</a>` : ''}
  </article>`;
}

function researchCard(e, { maxTags = 99 } = {}) {
  const tm = RESEARCH_TYPE_META[e.type] || RESEARCH_TYPE_META.research;
  const at = ARTICLE_TYPE_META[e.article_type];
  const tags = (e.tags || []).slice(0, maxTags)
    .map(t => `<span class="pill ${tagClass(t)}">${esc(TAG_LABELS[t] || t)}</span>`).join('');
  const url = safeUrl(e.url);
  return `<article class="card">
    <div class="card-header">
      <span class="type-pill ${tm.cls}">${tm.label}</span>
      ${at ? `<span class="pill ${at.cls}">${at.label}</span>` : ''}
      <div class="card-title">${esc(e.title)}</div>
    </div>
    ${e.source ? `<div class="card-org">${esc(e.source)}</div>` : ''}
    ${e.description ? `<div class="card-desc">${esc(e.description)}</div>` : ''}
    <div class="card-meta">${tags}<span class="pill date">🕐 ${esc(timeAgo(e.date))}</span></div>
    ${url ? `<a class="card-link" href="${esc(url)}" target="_blank" rel="noopener">Czytaj więcej →</a>` : ''}
  </article>`;
}
