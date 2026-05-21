/**
 * PWA Dueño — instalación (Android beforeinstallprompt + guía iOS).
 */
(function () {
  'use strict';

  var KEY_DISMISS = 'lhexia_owner_pwa_install_dismiss';
  var deferredPrompt = null;
  var banner = document.getElementById('ownerInstallBanner');
  var btnInstall = document.getElementById('ownerBtnInstall');
  var btnInstallToolbar = document.getElementById('ownerBtnInstallToolbar');
  if (!banner && !btnInstall && !btnInstallToolbar) return;
  var btnDismiss = document.getElementById('ownerInstallDismiss');
  var modalEl = document.getElementById('ownerInstallModal');

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

  function isAndroid() {
    return /Android/i.test(navigator.userAgent);
  }

  function showBanner() {
    if (banner) banner.classList.remove('d-none');
  }

  function hideBanner() {
    if (banner) banner.classList.add('d-none');
  }

  function showInstallButtons() {
    if (btnInstall) btnInstall.classList.remove('d-none');
    if (btnInstallToolbar) btnInstallToolbar.classList.remove('d-none');
  }

  function openGuideModal() {
    if (!modalEl || !window.bootstrap) {
      alert(
        isIOS()
          ? 'En iPhone: botón Compartir (cuadrado con flecha) → «Añadir a inicio».'
          : 'En Chrome: menú ⋮ → «Instalar aplicación» o «Añadir a pantalla de inicio».'
      );
      return;
    }
    var ios = document.getElementById('ownerInstallStepsIos');
    var android = document.getElementById('ownerInstallStepsAndroid');
    if (ios) ios.classList.toggle('d-none', !isIOS());
    if (android) android.classList.toggle('d-none', isIOS());
    new bootstrap.Modal(modalEl).show();
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

  var onHub = banner && banner.classList.contains('hub-pwa-install');

  if (localStorage.getItem(KEY_DISMISS) === '1' && !onHub) {
    showInstallButtons();
  } else {
    showBanner();
    showInstallButtons();
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showBanner();
    showInstallButtons();
  });

  if (btnInstall) btnInstall.addEventListener('click', tryNativeInstall);
  if (btnInstallToolbar) btnInstallToolbar.addEventListener('click', tryNativeInstall);

  if (btnDismiss) {
    btnDismiss.addEventListener('click', function () {
      localStorage.setItem(KEY_DISMISS, '1');
      hideBanner();
    });
  }

  if (isIOS() && !localStorage.getItem(KEY_DISMISS)) {
    showBanner();
    showInstallButtons();
  }
})();
