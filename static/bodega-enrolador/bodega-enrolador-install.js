/**
 * PWA Enrolador Bodega — instalación en tablet (Android / iOS).
 */
(function () {
  'use strict';

  var KEY_DISMISS = 'lhexia_bodega_enrolador_install_dismiss';
  var deferredPrompt = null;
  var banner = document.getElementById('bodegaEnrolInstallBanner');
  var btnInstall = document.getElementById('bodegaEnrolBtnInstall');
  if (!banner && !btnInstall) return;
  var btnDismiss = document.getElementById('bodegaEnrolInstallDismiss');

  function isStandalone() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: fullscreen)').matches ||
      window.navigator.standalone === true
    );
  }

  function isIOS() {
    return (
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
    );
  }

  function showBanner() {
    if (banner) banner.classList.remove('d-none');
  }

  function hideBanner() {
    if (banner) banner.classList.add('d-none');
  }

  function openGuideModal() {
    var msg = isIOS()
      ? 'En iPhone/iPad: botón Compartir → «Añadir a pantalla de inicio».'
      : 'En Chrome Android: menú ⋮ → «Instalar aplicación» o «Agregar a pantalla de inicio».';
    alert(msg);
  }

  function tryNativeInstall() {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function () {
        deferredPrompt = null;
        hideBanner();
      });
      return;
    }
    openGuideModal();
  }

  if (isStandalone()) {
    hideBanner();
    return;
  }

  if (localStorage.getItem(KEY_DISMISS) !== '1') {
    showBanner();
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showBanner();
  });

  if (btnInstall) btnInstall.addEventListener('click', tryNativeInstall);

  if (btnDismiss) {
    btnDismiss.addEventListener('click', function () {
      localStorage.setItem(KEY_DISMISS, '1');
      hideBanner();
    });
  }

  if (isIOS() && !localStorage.getItem(KEY_DISMISS)) {
    showBanner();
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/bodega-enrolador/sw.js', { scope: '/' }).catch(function () {});
  }
})();
