/**
 * Modal ficha producto (imagen + descripción) — POS carrito, Chilemat y vinculación.
 */
(function (global) {
  'use strict';

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function ensureModal() {
    let el = document.getElementById('chmFichaModal');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'chmFichaModal';
    el.className = 'modal fade';
    el.tabIndex = -1;
    el.innerHTML =
      '<div class="modal-dialog modal-lg modal-dialog-scrollable">' +
      '<div class="modal-content bg-dark text-light border-secondary">' +
      '<div class="modal-header border-secondary">' +
      '<h5 class="modal-title" id="chmFichaTitle">Ficha producto</h5>' +
      '<button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>' +
      '</div>' +
      '<div class="modal-body" id="chmFichaBody"><p class="text-muted">Cargando…</p></div>' +
      '<div class="modal-footer border-secondary">' +
      '<a href="#" id="chmFichaLink" class="btn btn-outline-info btn-sm" target="_blank" rel="noopener">Ver en chilemat.com</a>' +
      '<button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Cerrar</button>' +
      '</div></div></div>';
    document.body.appendChild(el);
    return el;
  }

  function renderFicha(data) {
    const img = data.imagen_url
      ? '<img src="' + esc(data.imagen_url) + '" alt="" class="img-fluid rounded mb-3" style="max-height:320px;object-fit:contain;background:#0f172a;width:100%">'
      : '<p class="text-muted small">Sin imagen disponible.</p>';
    const desc = data.descripcion_texto || data.descripcion_corta || '';
    const descHtml = data.descripcion_html
      ? '<div class="small border-top border-secondary pt-2 mt-2 chm-ficha-desc-html">' + data.descripcion_html + '</div>'
      : '';
    const meta =
      '<div class="small text-muted mb-2">' +
      (data.product_reference ? 'Ref: <code>' + esc(data.product_reference) + '</code> · ' : '') +
      (data.vtex_product_id ? 'VTEX ' + esc(data.vtex_product_id) + ' · ' : '') +
      (data.fuente ? esc(data.fuente) : '') +
      '</div>';
    return (
      '<div class="row g-3">' +
      '<div class="col-md-5">' +
      img +
      '</div>' +
      '<div class="col-md-7">' +
      '<h6 class="fw-bold">' +
      esc(data.nombre || 'Producto') +
      '</h6>' +
      meta +
      '<p class="small mb-0">' +
      esc(desc) +
      '</p>' +
      descHtml +
      '</div></div>'
    );
  }

  function showModal(modalEl) {
    if (global.bootstrap && global.bootstrap.Modal) {
      global.bootstrap.Modal.getOrCreateInstance(modalEl).show();
    } else {
      modalEl.style.display = 'block';
      modalEl.classList.add('show');
    }
  }

  function applyFichaToModal(data, fallback) {
    const modalEl = ensureModal();
    const body = document.getElementById('chmFichaBody');
    const title = document.getElementById('chmFichaTitle');
    const linkBtn = document.getElementById('chmFichaLink');
    const fb = fallback || {};

    if (!data || !data.ok) {
      const nombre =
        (fb.nombre || '').trim() ||
        (data && data.nombre) ||
        'Producto';
      const imgUrl = (fb.imagen_url || '').trim();
      if (imgUrl || nombre) {
        title.textContent = nombre.slice(0, 80);
        body.innerHTML = renderFicha({
          ok: true,
          nombre: nombre,
          imagen_url: imgUrl,
          descripcion_texto: fb.descripcion || nombre,
          product_reference: fb.product_reference || '',
          vtex_product_id: fb.vtex_product_id || '',
          fuente: 'carrito',
        });
        linkBtn.classList.add('d-none');
        const ext = (fb.link || fb.chm_link || '').trim();
        if (ext) {
          linkBtn.href = ext;
          linkBtn.classList.remove('d-none');
        }
        return;
      }
      body.innerHTML =
        '<p class="text-danger">' + esc((data && data.error) || 'No se pudo cargar la ficha') + '</p>';
      linkBtn.classList.add('d-none');
      return;
    }
    title.textContent = (data.nombre || 'Ficha producto').slice(0, 80);
    body.innerHTML = renderFicha(data);
    linkBtn.classList.add('d-none');
    const ext = (data.link || fb.link || fb.chm_link || '').trim();
    if (ext) {
      linkBtn.href = ext;
      linkBtn.classList.remove('d-none');
    }
  }

  function readTrigger(el) {
    if (!el || !el.getAttribute) return null;
    const host = el.closest('.pos-cart-ficha-host, .pos-cart-card, [data-producto-id]');
    const pid = (el.getAttribute('data-producto-id') || (host && host.getAttribute('data-producto-id')) || '').trim();
    const vtex = (el.getAttribute('data-vtex-id') || (host && host.getAttribute('data-vtex-id')) || '').trim();
    const img = (el.getAttribute('data-img-fallback') || (host && host.getAttribute('data-img-fallback')) || '').trim();
    const link = (el.getAttribute('data-chm-link') || (host && host.getAttribute('data-chm-link')) || '').trim();
    let nombre = '';
    const card = el.closest('.pos-cart-card');
    if (card) {
      nombre = (card.getAttribute('data-producto-nombre') || '').trim();
      if (!nombre) {
        const h = card.querySelector('.pos-cart-card__nombre');
        if (h) nombre = (h.textContent || '').trim();
      }
    }
    return { productoId: pid, vtexId: vtex, imagen_url: img, link: link, nombre: nombre };
  }

  function openFromTrigger(el) {
    const t = readTrigger(el);
    if (!t) return;
    const fallback = {
      imagen_url: t.imagen_url,
      nombre: t.nombre,
      descripcion: t.nombre,
      link: t.link,
      chm_link: t.link,
      vtex_product_id: t.vtexId,
    };
    if (t.vtexId) {
      openFicha(t.vtexId, null, fallback);
    } else if (t.productoId) {
      openProducto(t.productoId, null, fallback);
    }
  }

  function openFicha(vtexId, apiBase, fallback) {
    if (!vtexId) return;
    const modalEl = ensureModal();
    const body = document.getElementById('chmFichaBody');
    const title = document.getElementById('chmFichaTitle');
    body.innerHTML = '<p class="text-muted">Cargando ficha…</p>';
    title.textContent = 'Ficha producto';
    showModal(modalEl);

    const url =
      (apiBase || '/api/compras/chilemat/ficha/') + encodeURIComponent(vtexId) + '?refresh=0';
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        applyFichaToModal(d, fallback);
      })
      .catch(function () {
        applyFichaToModal({ ok: false, error: 'Error de red' }, fallback);
      });
  }

  function openProducto(productoId, apiBase, fallback) {
    const pid = parseInt(productoId, 10);
    if (!pid) return;
    const modalEl = ensureModal();
    const body = document.getElementById('chmFichaBody');
    const title = document.getElementById('chmFichaTitle');
    body.innerHTML = '<p class="text-muted">Cargando ficha…</p>';
    title.textContent = 'Ficha producto';
    showModal(modalEl);

    const url = (apiBase || '/api/pos/producto-ficha/') + pid + '?refresh=0';
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        applyFichaToModal(d, fallback);
      })
      .catch(function () {
        applyFichaToModal({ ok: false, error: 'Error de red' }, fallback);
      });
  }

  function isFichaTrigger(el) {
    if (!el || !el.closest) return false;
    return !!el.closest(
      '.btn-pos-ficha-modal, .pos-cart-ficha-trigger, .pos-cart-ficha-thumb, .pos-cart-ficha-host .pos-cart-ficha-btn'
    );
  }

  function onFichaClick(e) {
    const el = e.target && e.target.closest ? e.target.closest('.btn-pos-ficha-modal, .pos-cart-ficha-trigger, .pos-cart-ficha-thumb') : null;
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    openFromTrigger(el);
  }

  function bindPosCartFichaButtons(root) {
    const scope = root || document;
    if (!global.__chmFichaDelegado) {
      global.__chmFichaDelegado = true;
      document.addEventListener('click', onFichaClick, true);
    }
    scope.querySelectorAll('.btn-pos-ficha-modal, .pos-cart-ficha-trigger, .pos-cart-ficha-thumb').forEach(function (btn) {
      if (btn.dataset.chmFichaBound === '1') return;
      btn.dataset.chmFichaBound = '1';
      btn.addEventListener('click', onFichaClick);
    });
  }

  global.ChilematFicha = {
    open: openFicha,
    openProducto: openProducto,
    openFromTrigger: openFromTrigger,
    render: renderFicha,
    bindPosCart: bindPosCartFichaButtons,
    isFichaTrigger: isFichaTrigger,
  };
})(typeof window !== 'undefined' ? window : this);
