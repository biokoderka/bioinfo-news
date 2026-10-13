// Podstrona staze.html — wpisy typu "internship".
// Bez przycisku archiwum: programy wracają co roku, więc widać je zawsze, a o aktualności mówi status.
(function () {
  const $ = id => document.getElementById(id);
  const REGION_ORDER = { PL: 0, EU: 1, remote: 2 };
  let all = [];

  function rank(e) { return INTERN_STATUS[internStatus(e)].rank; }

  function render() {
    const q = $('searchInput').value.toLowerCase();
    const region = $('regionFilter').value;
    const status = $('statusFilter').value;

    const list = all.filter(e => {
      if (q && !JSON.stringify(e).toLowerCase().includes(q)) return false;
      if (region && e.region !== region) return false;
      if (status && internStatus(e) !== status) return false;
      return true;
    }).sort((a, b) =>
      rank(a) - rank(b) ||
      (REGION_ORDER[a.region] ?? 9) - (REGION_ORDER[b.region] ?? 9) ||
      String(a.title).localeCompare(String(b.title), 'pl'));

    const live = all.filter(e => ['open', 'rolling'].includes(internStatus(e))).length;
    $('statsLine').innerHTML = `<strong>${all.length}</strong> programów &nbsp;·&nbsp; <strong>${live}</strong> z otwartym lub ciągłym naborem`;
    $('cards').innerHTML = list.length
      ? list.map(e => newsCard(e)).join('')
      : `<div class="empty">Brak staży dla tych filtrów.<br><a href="submit.html">Znasz program? Zgłoś go →</a></div>`;
  }

  async function init() {
    try {
      const data = await fetch('news.json?v=' + Date.now()).then(r => r.json());
      all = (data.entries || []).filter(e => e.type === 'internship' && !e.archived);
      render();
    } catch (err) {
      $('cards').innerHTML = '<div class="empty">Nie udało się wczytać danych — odśwież stronę.</div>';
      $('statsLine').textContent = '';
    }
  }

  ['searchInput', 'regionFilter', 'statusFilter'].forEach(id =>
    $(id).addEventListener(id === 'searchInput' ? 'input' : 'change', render));
  init();
})();
