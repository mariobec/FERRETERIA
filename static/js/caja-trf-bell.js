(function () {
    'use strict';

    var wrap = document.getElementById('cajaTrfBellWrap');
    if (!wrap) return;

    var url = wrap.getAttribute('data-url');
    var btn = document.getElementById('cajaTrfBellBtn');
    var panel = document.getElementById('cajaTrfBellPanel');
    var badge = document.getElementById('cajaTrfBellBadge');
    var lineV = document.getElementById('cajaTrfBellLineVales');
    var lineC = document.getElementById('cajaTrfBellLineCorreos');
    var hint = document.getElementById('cajaTrfBellHint');
    var itemsEl = document.getElementById('cajaTrfBellItems');
    var bandajaUrl = wrap.getAttribute('data-bandaja') || '';
    var LS_KEY = 'cajaTrfLastCorreoId';
    var POLL_MS = 120000;
    var lastTotal = parseInt(wrap.getAttribute('data-inicial-total') || '0', 10) || 0;
    var lastCorreoId = 0;
    var pollReady = false;
    var toastTimer = null;

    function fmtMonto(n) {
        if (n == null || isNaN(n)) return '—';
        return '$ ' + Number(n).toLocaleString('es-CL');
    }

    function fmtFecha(iso) {
        if (!iso) return '';
        return iso.replace('T', ' ').slice(0, 16);
    }

    function escHtml(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    }

    function setVisible(show) {
        wrap.classList.toggle('d-none', !show);
    }

    function setRing(on) {
        if (btn) btn.classList.toggle('caja-trf-bell-btn--ring', !!on);
    }

    function playBellSound() {
        try {
            var Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return;
            var ctx = new Ctx();
            var t0 = ctx.currentTime;
            [880, 1175].forEach(function (freq, i) {
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.0001, t0 + i * 0.14);
                gain.gain.exponentialRampToValueAtTime(0.18, t0 + i * 0.14 + 0.02);
                gain.gain.exponentialRampToValueAtTime(0.0001, t0 + i * 0.14 + 0.35);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(t0 + i * 0.14);
                osc.stop(t0 + i * 0.14 + 0.36);
            });
            setTimeout(function () {
                try { ctx.close(); } catch (e) { /* ignore */ }
            }, 900);
        } catch (e) { /* silencioso */ }
    }

    function showToast(msg) {
        var el = document.getElementById('cajaTrfBellToast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'cajaTrfBellToast';
            el.className = 'caja-trf-bell-toast';
            el.setAttribute('role', 'status');
            document.body.appendChild(el);
        }
        el.textContent = msg;
        el.classList.add('caja-trf-bell-toast--show');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            el.classList.remove('caja-trf-bell-toast--show');
        }, 3200);
    }

    function renderItems(data) {
        if (!itemsEl) return;
        var items = (data && data.items) || [];
        if (!items.length) {
            var nV = parseInt(data.n_vales, 10) || 0;
            var nC = parseInt(data.n_correos, 10) || 0;
            if (nV + nC === 0) {
                itemsEl.innerHTML = '<div class="caja-trf-bell-panel__empty">Sin pendientes de transferencia.</div>';
            } else {
                itemsEl.innerHTML = '<div class="caja-trf-bell-panel__empty">Use la bandeja para revisar el detalle.</div>';
            }
            return;
        }
            itemsEl.innerHTML = items.map(function (it) {
                var esCorreo = it.tipo === 'correo';
                var tagClass = esCorreo ? 'caja-trf-bell-item__tag--banco' : 'caja-trf-bell-item__tag--vale';
                var tagTxt = esCorreo ? 'Banco' : 'Vale';
                var icon = esCorreo ? 'fa-envelope-open-text' : 'fa-receipt';
                var montoTxt = (it.monto != null && !isNaN(it.monto)) ? fmtMonto(it.monto) : 'Monto por revisar';
                var meta = fmtFecha(it.fecha);
                if (esCorreo && it.tiene_match && it.venta_id_sugerida) {
                    meta = (meta ? meta + ' · ' : '') + 'Match vale #' + it.venta_id_sugerida;
                } else if (!esCorreo && it.folio) {
                    meta = (meta ? meta + ' · ' : '') + it.folio;
                }
                if (it.referencia) {
                    meta = (meta ? meta + ' · ' : '') + 'Ref. ' + it.referencia;
                }
                var urlRev = it.url_revisar || bandajaUrl;
                var confirmBtn = '';
                if (it.url_confirmar) {
                    var confirmLabel = esCorreo ? 'Confirmar' : 'Confirmar abono';
                    var vidAttr = it.venta_id_sugerida ? (' data-venta-id="' + escHtml(String(it.venta_id_sugerida)) + '"') : '';
                    confirmBtn = '<button type="button" class="caja-trf-bell-item__btn-confirm" data-confirm-url="' +
                        escHtml(it.url_confirmar) + '"' + vidAttr + ' data-tipo="' + escHtml(it.tipo) + '">' +
                        escHtml(confirmLabel) + '</button>';
                }
                return '<article class="caja-trf-bell-item">' +
                    '<div class="caja-trf-bell-item__icon"><i class="fas ' + icon + '" aria-hidden="true"></i></div>' +
                    '<div class="caja-trf-bell-item__body">' +
                    '<span class="caja-trf-bell-item__tag ' + tagClass + '">' + tagTxt + '</span>' +
                    '<div class="caja-trf-bell-item__monto">' + escHtml(montoTxt) + '</div>' +
                    '<div class="caja-trf-bell-item__de" title="' + escHtml(it.de) + '">' + escHtml(it.de) + '</div>' +
                    '<div class="caja-trf-bell-item__meta">' + escHtml(meta) + '</div>' +
                    '</div>' +
                    '<div class="caja-trf-bell-item__actions">' +
                    confirmBtn +
                    '<a class="caja-trf-bell-item__btn" href="' + escHtml(urlRev) + '">Revisar</a>' +
                    '</div></article>';
            }).join('');
    }

    if (lastTotal > 0) {
        setVisible(true);
        if (badge) {
            badge.textContent = lastTotal > 99 ? '99+' : String(lastTotal);
            badge.classList.remove('d-none');
        }
    }

    function updateUi(data, opts) {
        opts = opts || {};
        if (!data || !data.ok) return;
        var total = parseInt(data.total, 10) || 0;
        var nV = parseInt(data.n_vales, 10) || 0;
        var nC = parseInt(data.n_correos, 10) || 0;
        var ultId = parseInt(data.ultimo_correo_id, 10) || 0;
        setVisible(total > 0 || nC > 0 || nV > 0);
        if (badge) {
            if (total > 0) {
                badge.textContent = total > 99 ? '99+' : String(total);
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
        }
        if (lineV) lineV.textContent = 'Vales por confirmar: ' + nV;
        if (lineC) {
            var extra = data.n_correos_con_match ? (' (' + data.n_correos_con_match + ' con match)') : '';
            lineC.textContent = 'Avisos banco: ' + nC + extra;
        }
        renderItems(data);
        if (hint && ultId && data.ultimo_correo_at) {
            hint.textContent = 'Último aviso banco: ' + fmtFecha(data.ultimo_correo_at);
        }
        var seenId = 0;
        try { seenId = parseInt(localStorage.getItem(LS_KEY) || '0', 10) || 0; } catch (e) { seenId = 0; }
        var hayNuevoCorreo = ultId > seenId && ultId > 0;
        var hayMas = total > lastTotal && pollReady;
        if (pollReady && (hayNuevoCorreo || hayMas)) {
            setRing(true);
            playBellSound();
            if (hayNuevoCorreo && !panel.classList.contains('d-none')) {
                showToast('Nuevo aviso de transferencia bancaria');
            }
        } else if (opts.ring) {
            setRing(true);
        }
        lastTotal = total;
        lastCorreoId = ultId;
    }

    function poll() {
        fetch(url, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                updateUi(data, {});
                pollReady = true;
            })
            .catch(function () { pollReady = true; });
    }

    function confirmarDesdeCampanita(confirmBtn) {
        var confirmUrl = confirmBtn.getAttribute('data-confirm-url');
        if (!confirmUrl) return;
        var tipo = confirmBtn.getAttribute('data-tipo') || '';
        var msg = tipo === 'correo'
            ? '¿Confirma abono con este aviso del banco? Se habilitará entrega del vale.'
            : '¿Confirma que el abono bancario ya está en cuenta? Se habilitará entrega.';
        if (!window.confirm(msg)) return;

        confirmBtn.disabled = true;
        var body = '{}';
        var ventaId = confirmBtn.getAttribute('data-venta-id');
        if (ventaId) {
            body = JSON.stringify({ venta_id: parseInt(ventaId, 10) });
        }

        fetch(confirmUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: body,
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
            .then(function (res) {
                confirmBtn.disabled = false;
                if (res.j && res.j.ok) {
                    showToast(res.j.mensaje || 'Transferencia confirmada.');
                    setRing(false);
                    poll();
                    if (typeof window.cajaTrfBellOnConfirm === 'function') {
                        window.cajaTrfBellOnConfirm(res.j);
                    }
                } else {
                    window.alert((res.j && res.j.error) || 'No se pudo confirmar.');
                }
            })
            .catch(function () {
                confirmBtn.disabled = false;
                window.alert('Error de red al confirmar.');
            });
    }

    if (itemsEl) {
        itemsEl.addEventListener('click', function (e) {
            var t = e.target;
            if (t && t.classList && t.classList.contains('caja-trf-bell-item__btn-confirm')) {
                e.preventDefault();
                e.stopPropagation();
                confirmarDesdeCampanita(t);
            }
        });
    }

    if (btn && panel) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var open = panel.classList.toggle('d-none');
            btn.setAttribute('aria-expanded', open ? 'false' : 'true');
            if (!open) {
                setRing(false);
                try {
                    if (lastCorreoId > 0) localStorage.setItem(LS_KEY, String(lastCorreoId));
                } catch (err) { /* ignore */ }
            }
        });
        document.addEventListener('click', function () {
            if (!panel.classList.contains('d-none')) {
                panel.classList.add('d-none');
                btn.setAttribute('aria-expanded', 'false');
            }
        });
        panel.addEventListener('click', function (e) { e.stopPropagation(); });
    }

    poll();
    setInterval(poll, POLL_MS);
})();
