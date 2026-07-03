/**

 * Mentor Coach — chat IA en /academy

 */

(function () {

  'use strict';



  var THINKING_LINES = [

    'Maylén está pensando',

    'Analizando tu consulta',

    'Conectando con LhexIA',

    'Escribiendo respuesta',

  ];



  function escHtml(s) {

    return String(s || '')

      .replace(/&/g, '&amp;')

      .replace(/</g, '&lt;')

      .replace(/>/g, '&gt;')

      .replace(/"/g, '&quot;');

  }



  function mdLite(text) {

    var t = escHtml(text || '');

    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    t = t.replace(/\n/g, '<br>');

    return t;

  }



  document.addEventListener('DOMContentLoaded', function () {

    var cfgEl = document.getElementById('lhexia-academy-coach-config');

    var form = document.getElementById('lhexiaAcademyCoachForm');

    var input = document.getElementById('lhexiaAcademyCoachInput');

    var thread = document.getElementById('lhexiaAcademyCoachOut');

    var chips = document.getElementById('lhexiaAcademyCoachChips');

    if (!cfgEl || !form || !input || !thread) return;



    var cfg = {};

    try {

      cfg = JSON.parse(cfgEl.textContent || '{}');

    } catch (e) {

      return;

    }

    var apiUrl = cfg.pregunta_url || '';

    var maylenAvatarUrl = cfg.maylen_avatar_url || '/static/img/maylen_avatar_cutout.png?v=7';

    var thinkingTimer = null;

    var thinkingIdx = 0;

    var historyHtml = '';



    function maylenAvatarHtml() {

      return (

        '<div class="lhexia-coach-msg__avatar maylen-mentor-avatar maylen-mentor-avatar--sm">' +

        '<img src="' +

        escHtml(maylenAvatarUrl) +

        '" alt="" class="maylen-mentor-avatar__photo">' +

        '</div>'

      );

    }



    function typingDotsHtml() {

      return (

        '<span class="lhexia-coach-typing" aria-hidden="true">' +

        '<span></span><span></span><span></span></span>'

      );

    }



    function botBubbleHtml(inner) {

      return (

        '<div class="lhexia-coach-msg lhexia-coach-msg--bot">' +

        maylenAvatarHtml() +

        '<div class="lhexia-coach-msg__bubble">' +

        inner +

        '</div></div>'

      );

    }



    function userBubbleHtml(text) {

      return (

        '<div class="lhexia-coach-msg lhexia-coach-msg--user">' +

        '<div class="lhexia-coach-msg__bubble">' +

        escHtml(text) +

        '</div></div>'

      );

    }



    function thinkingBubbleHtml(line) {

      return botBubbleHtml(

        '<span class="lhexia-coach-thinking-text">' +

          escHtml(line) +

          '…</span>' +

          typingDotsHtml()

      );

    }



    function renderThread(extraHtml) {

      thread.innerHTML = historyHtml + (extraHtml || '');

      thread.scrollTop = thread.scrollHeight;

    }



    function stopThinkingCycle() {

      if (thinkingTimer) {

        clearInterval(thinkingTimer);

        thinkingTimer = null;

      }

    }



    function startThinkingCycle() {

      stopThinkingCycle();

      thinkingIdx = 0;

      renderThread(

        '<div class="lhexia-coach-msg lhexia-coach-msg--bot lhexia-coach-msg--thinking" id="lhexiaCoachThinking">' +

          maylenAvatarHtml() +

          '<div class="lhexia-coach-msg__bubble">' +

          '<span class="lhexia-coach-thinking-text">' +

          escHtml(THINKING_LINES[0]) +

          '…</span>' +

          typingDotsHtml() +

          '</div></div>'

      );

      thinkingTimer = window.setInterval(function () {

        thinkingIdx = (thinkingIdx + 1) % THINKING_LINES.length;

        var el = document.getElementById('lhexiaCoachThinking');

        if (!el) return;

        var txt = el.querySelector('.lhexia-coach-thinking-text');

        if (txt) txt.textContent = THINKING_LINES[thinkingIdx] + '…';

      }, 2000);

    }



    function fuenteMeta(data) {

      if (data.fuente === 'ollama') {

        return '<div class="lhexia-coach-msg__meta"><i class="fas fa-wand-magic-sparkles me-1"></i>Generado con IA local</div>';

      }

      if (data.fuente === 'kb') {

        return '<div class="lhexia-coach-msg__meta"><i class="fas fa-bolt me-1"></i>Respuesta instantánea · LhexIA</div>';

      }

      return '';

    }



    function renderRespuesta(data) {

      stopThinkingCycle();

      if (!data || !data.ok) {

        renderThread(

          botBubbleHtml(

            escHtml((data && data.mensaje) || 'No pude procesar tu consulta. Intentá de nuevo.')

          )

        );

        historyHtml = thread.innerHTML;

        return;

      }



      var tail =

        botBubbleHtml(mdLite(data.respuesta || '') + fuenteMeta(data));



      if (data.articulo && data.articulo.launch_interactivo_href) {

        tail +=

          '<div class="lhexia-coach-actions">' +

          '<a class="btn btn-success btn-sm fw-semibold" href="' +

          escHtml(data.articulo.launch_interactivo_href) +

          '"><i class="fas fa-play me-1"></i>Guía interactiva</a>' +

          '<a class="btn btn-outline-secondary btn-sm" href="' +

          escHtml(data.articulo.practicar_href || '/academy') +

          '"><i class="fas fa-external-link-alt me-1"></i>Ver módulo</a>' +

          '</div>';

      }

      if (data.alternativas && data.alternativas.length) {

        tail += '<div class="lhexia-coach-alts"><div class="small text-muted mb-1">Temas relacionados</div>';

        data.alternativas.forEach(function (a) {

          if (!a || !a.title) return;

          tail +=

            '<button type="button" class="btn btn-sm btn-outline-primary me-1 mb-1 lhexia-coach-alt" data-q="' +

            escHtml(a.title) +

            '">' +

            escHtml(a.title) +

            '</button>';

        });

        tail += '</div>';

      }



      renderThread(tail);

      historyHtml = thread.innerHTML;



      thread.querySelectorAll('.lhexia-coach-alt').forEach(function (btn) {

        btn.addEventListener('click', function () {

          input.value = btn.getAttribute('data-q') || '';

          form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));

        });

      });



      if (window.playMaylenAcademyWave) window.playMaylenAcademyWave();

    }



    function enviarPregunta(q) {

      if (!apiUrl || !q || q.length < 3) return;

      historyHtml += userBubbleHtml(q);

      startThinkingCycle();

      if (window.playMaylenAcademyWave) window.playMaylenAcademyWave();



      fetch(apiUrl, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        credentials: 'same-origin',

        body: JSON.stringify({ pregunta: q, usar_ia: true }),

      })

        .then(function (r) {

          return r.json();

        })

        .then(renderRespuesta)

        .catch(function () {

          renderRespuesta({ ok: false, mensaje: 'Sin conexión. Verificá la red e intentá otra vez.' });

        });

    }



    historyHtml = botBubbleHtml(
      '¡Hola! Soy <strong>Maylén</strong>, tu <strong>profesora IA</strong> del ERP. ' +
        'Preguntame sobre POS, caja o bodega y te guío a la pantalla exacta.'
    );

    renderThread('');



    form.addEventListener('submit', function (e) {

      e.preventDefault();

      var q = (input.value || '').trim();

      if (q.length < 3) return;

      input.value = '';

      enviarPregunta(q);

    });



    if (chips) {

      chips.querySelectorAll('[data-coach-q]').forEach(function (chip) {

        chip.addEventListener('click', function () {

          var q = chip.getAttribute('data-coach-q') || '';

          input.value = q;

          enviarPregunta(q);

        });

      });

    }

  });

})();


