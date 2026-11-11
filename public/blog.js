document.querySelector('.nav-menu-toggle')?.addEventListener('click', function () {
  const open = this.getAttribute('aria-expanded') !== 'true';
  this.setAttribute('aria-expanded', String(open));
  document.querySelector('.nav').classList.toggle('menu-open', open);
});

const archive = document.querySelector('[data-blog-archive]');
if (archive) {
  const cards = [...archive.querySelectorAll('[data-blog-card]')];
  const search = archive.querySelector('#blog-search');
  const year = archive.querySelector('#blog-year');
  const count = archive.querySelector('[data-blog-count]');
  const pagination = archive.querySelector('[data-blog-pagination]');
  const previous = pagination.querySelector('[data-previous]');
  const next = pagination.querySelector('[data-next]');
  const params = new URLSearchParams(location.search);
  const perPage = 12;
  let page = Math.max(1, Number.parseInt(params.get('page'), 10) || 1);
  search.value = params.get('q') || '';
  if ([...year.options].some(option => option.value === params.get('year'))) year.value = params.get('year');
  pagination.hidden = false;

  function render(scroll = false, updateUrl = true) {
    const term = search.value.trim().toLocaleLowerCase();
    const matching = cards.filter(card => (!year.value || card.dataset.year === year.value) && (!term || card.dataset.search.includes(term)));
    const totalPages = Math.max(1, Math.ceil(matching.length / perPage));
    page = Math.min(page, totalPages);
    cards.forEach(card => { card.hidden = true; });
    matching.slice((page - 1) * perPage, page * perPage).forEach(card => { card.hidden = false; });
    count.textContent = matching.length ? `${(page - 1) * perPage + 1}–${Math.min(page * perPage, matching.length)} of ${matching.length} ${matching.length === 1 ? 'article' : 'articles'}` : 'No articles found';
    archive.querySelector('[data-blog-empty]').hidden = matching.length !== 0;
    pagination.querySelector('[data-page-label]').textContent = `Page ${page} of ${totalPages}`;
    previous.disabled = page <= 1;
    next.disabled = page >= totalPages;
    pagination.hidden = matching.length === 0;
    if (updateUrl) {
      const url = new URL(location.href);
      for (const [key, value] of [['q', search.value.trim()], ['year', year.value], ['page', page > 1 ? String(page) : '']]) {
        if (value) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      }
      history.replaceState(null, '', url);
    }
    if (scroll) {
      archive.querySelector('#all-articles').scrollIntoView({ behavior: 'instant', block: 'start' });
      count.focus({ preventScroll: true });
    }
  }

  search.addEventListener('input', () => { page = 1; render(); });
  year.addEventListener('change', () => { page = 1; render(); });
  previous.addEventListener('click', () => { page -= 1; render(true); });
  next.addEventListener('click', () => { page += 1; render(true); });
  // Back from an article restores the archive page and its filters via the URL.
  render(false, false);
}
