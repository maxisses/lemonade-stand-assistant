(() => {
  'use strict';
  const config = window.LEMONADE_DECK;
  const slides = Array.from(document.querySelectorAll('.slide'));
  const stage = document.getElementById('stage');
  const picker = document.getElementById('slide-picker');
  const notes = document.getElementById('notes-panel');
  const notesToggle = document.getElementById('notes-toggle');
  let current = 0;
  function resize() {
    const scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = `translate(-50%, -50%) scale(${scale})`;
  }
  slides.forEach((slide, i) => {
    const option = document.createElement('option');
    option.value = i;
    option.textContent = `${String(i + 1).padStart(2, '0')} · ${slide.dataset.title}`;
    picker.append(option);
    // Marker IDs are unique across diagrams for reliable rendering and printing.
    slide.querySelectorAll('marker').forEach(marker => {
      const oldId = marker.id;
      marker.id = `${oldId}-${i}`;
      slide.querySelectorAll(`path.line`).forEach(path => {
        const isRed = path.classList.contains('red-line');
        if ((oldId === 'arrowRed') === isRed) path.style.markerEnd = `url(#${marker.id})`;
      });
    });
  });
  function updateNotes() {
    document.getElementById('notes-heading').textContent = `${current + 1} · ${slides[current].dataset.title}`;
    document.getElementById('notes-body').textContent = slides[current].querySelector('.notes').textContent;
  }
  function show(index, updateHash = true) {
    current = Math.max(0, Math.min(slides.length - 1, index));
    slides.forEach((slide, i) => {
      slide.classList.toggle('active', i === current);
      slide.setAttribute('aria-hidden', String(i !== current));
      slide.inert = i !== current;
    });
    picker.value = current;
    document.getElementById('counter').textContent = `${current + 1} / ${slides.length}`;
    document.title = `${current + 1} · ${slides[current].dataset.title} | Lemonade`;
    updateNotes();
    if (updateHash) history.replaceState(null, '', `#${current + 1}`);
  }
  function readHash() {
    const value = Number(location.hash.slice(1));
    show(Number.isFinite(value) && value >= 1 ? value - 1 : 0, false);
  }
  function toggleNotes() {
    const visible = !notes.classList.contains('visible');
    notes.classList.toggle('visible', visible);
    document.body.classList.toggle('notes-open', visible);
    notesToggle.setAttribute('aria-expanded', String(visible));
  }
  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) { document.getElementById('fullscreen').textContent = 'Use browser fullscreen'; }
  }
  document.querySelectorAll('[data-customer]').forEach(el => { el.textContent = config.customer; });
  document.querySelectorAll('[data-presenter]').forEach(el => { el.textContent = config.presenter; });
  document.querySelectorAll('[data-event-date]').forEach(el => { el.textContent = config.eventDate; });
  document.querySelectorAll('[data-link]').forEach(el => {
    const url = new URL(config.links[el.dataset.link]);
    if (url.protocol !== 'https:') throw new Error('Live links must use HTTPS.');
    el.href = url.href;
  });
  // Verify the locally generated QR is still consistent with the configured URL.
  fetch('assets/audience-qr.json').then(r => r.json()).then(data => {
    if (data.url !== config.links.audience) {
      document.getElementById('audience-qr').hidden = true;
      document.getElementById('audience-qr').style.display = 'none';
      document.getElementById('qr-warning').style.display = 'block';
    }
  }).catch(() => { /* file:// browsing remains usable; use HTTP for the QR consistency check. */ });
  document.getElementById('previous').onclick = () => show(current - 1);
  document.getElementById('next').onclick = () => show(current + 1);
  picker.onchange = () => show(Number(picker.value));
  notesToggle.onclick = toggleNotes;
  document.getElementById('fullscreen').onclick = fullscreen;
  document.getElementById('print').onclick = () => window.print();
  window.addEventListener('resize', resize);
  window.addEventListener('hashchange', readHash);
  document.addEventListener('keydown', e => {
    if (e.target.closest('input,textarea,select,button,a')) return;
    if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); show(current + 1); }
    else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); show(current - 1); }
    else if (e.key === 'Home') { e.preventDefault(); show(0); }
    else if (e.key === 'End') { e.preventDefault(); show(slides.length - 1); }
    else if (e.key.toLowerCase() === 'n') toggleNotes();
    else if (e.key.toLowerCase() === 'f') fullscreen();
    else if (e.key === 'Escape' && notes.classList.contains('visible')) toggleNotes();
  });
  resize();
  readHash();
})();
