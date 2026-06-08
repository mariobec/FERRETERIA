/**
 * Hub módulos — altura uniforme + flyout "Más accesos".
 * Clic en móvil; hover en desktop (pointer fine).
 */
(function () {
  'use strict';

  function closeAll(except) {
    document.querySelectorAll('[data-hub-more].is-open').forEach(function (wrap) {
      if (wrap === except) return;
      wrap.classList.remove('is-open');
      var btn = wrap.querySelector('.hub-atajos-more');
      if (btn) btn.setAttribute('aria-expanded', 'false');
      var card = wrap.closest('.hub-card');
      if (card) card.classList.remove('is-expanded');
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    document.querySelectorAll('[data-hub-more]').forEach(function (wrap) {
      var btn = wrap.querySelector('.hub-atajos-more');
      var card = wrap.closest('.hub-card');
      if (!btn || !card) return;

      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var open = wrap.classList.toggle('is-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        card.classList.toggle('is-expanded', open);
        if (open) closeAll(wrap);
      });

      var flyout = wrap.querySelector('.hub-atajos-flyout');
      if (flyout) {
        flyout.addEventListener('click', function (e) {
          e.stopPropagation();
        });
      }

      if (canHover) {
        wrap.addEventListener('mouseenter', function () {
          wrap.classList.add('is-hover');
        });
        wrap.addEventListener('mouseleave', function () {
          wrap.classList.remove('is-hover');
        });
      }
    });

    document.addEventListener('click', function () {
      closeAll(null);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAll(null);
    });
  });
})();
