// Wspólny skrypt podstron sekcji (meetups, courses-dated, courses-free, projects, other).
// Typ wpisów bierze z <script src="assets/section.js" data-type="meetup">.
(function () {
  const TYPE_KEY = document.currentScript.dataset.type;
  const $ = id => document.getElementById(id);
  let allEntries = [], showArchive = false;

  function sortKey(e) { return e.date_start || e.added || '9999-12-31'; }

  function render() {
    const q = $('searchInput').value.toLowerCase();
    const lang = $('langFilter').value;
    const free = $('freeFilter').value;

    const entries = allEntries.filter(e => {
      if (showArchive !== isArchived(e)) return false;
      if (q && !JSON.stringify(e).toLowerCase().includes(q)) return false;
      if (lang && !(e.lang || '').includes(lang)) return false;
      if (free === 'free' && !e.free) return false;
      return true;
    }).sort((a, b) => showArchive ? sortKey(b).localeCompare(sortKey(a)) : sortKey(a).localeCompare(sortKey(b)));

    const ac = allEntries.filter(e => !isArchived(e)).length;
    $('statsLine').innerHTML = `<strong>${ac}</strong> aktywne &nbsp;·&nbsp; <strong>${allEntries.length - ac}</strong> w archiwum`;
    $('cards').innerHTML = entries.length
      ? entries.map(e => newsCard(e, { showArchivedBadge: true })).join('')
      : `<div class="empty">Brak wpisów.<br><a href="submit.html">Zgłoś pierwszy →</a></div>`;
  }

  async function init() {
    try {
      const data = await fetch('news.json?v=' + Date.now()).then(r => r.json());
      allEntries = (data.entries || []).filter(e => e.type === TYPE_KEY);
      render();
    } catch (err) {
      $('cards').innerHTML = '<div class="empty">Nie udało się wczytać danych — odśwież stronę.</div>';
      $('statsLine').textContent = '';
    }
  }

  $('searchInput').addEventListener('input', render);
  $('langFilter').addEventListener('change', render);
  $('freeFilter').addEventListener('change', render);
  $('archiveToggle').addEventListener('click', function () {
    showArchive = !showArchive;
    this.classList.toggle('on', showArchive);
    this.textContent = showArchive ? '◀ Aktualności' : '📦 Archiwum';
    render();
  });
  init();
})();
