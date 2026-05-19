/**
 * Núcleo LhexIA en login — animación garantizada (requestAnimationFrame).
 */
(function () {
    'use strict';

    var root = document.getElementById('loginCoreReveal');
    if (!root) return;

    var viewport = root.querySelector('.login-core-viewport');
    var art = root.querySelector('.login-core-art');
    var orbit = root.querySelector('.login-core-orbit');
    if (!viewport || !art) return;

    var t0 = performance.now();

    function frame(now) {
        var t = (now - t0) * 0.001;
        var beat = (Math.sin(t * 2.4) + 1) * 0.5;
        var beat2 = (Math.sin(t * 2.4 + 1.1) + 1) * 0.5;
        var wave = (Math.sin(t * 1.15) + 1) * 0.5;

        var o = 0.4 + beat * 0.5 + beat2 * 0.15;
        var g = 0.3 + wave * 0.45;
        var scale = 1 + beat * 0.05;

        viewport.style.boxShadow =
            '0 0 ' + (22 + beat * 30) + 'px rgba(234,88,12,' + o + '),' +
            '0 0 ' + (38 + wave * 40) + 'px rgba(52,211,153,' + g + '),' +
            '0 12px 32px rgba(0,0,0,0.45)';
        viewport.style.transform = 'scale(' + scale + ')';

        var bright = 0.9 + beat * 0.2 + beat2 * 0.1;
        art.style.filter =
            'brightness(' + bright + ') saturate(' + (1.05 + beat * 0.22) + ') ' +
            'drop-shadow(0 0 ' + (14 + beat * 26) + 'px rgba(255,140,40,0.6))';
        art.style.transform =
            'scale(' + (1 + beat * 0.05) + ') rotateY(' + (Math.sin(t * 0.85) * 12) + 'deg)';

        if (orbit) {
            orbit.style.transform = 'rotate(' + (t * 130 % 360) + 'deg)';
        }

        requestAnimationFrame(frame);
    }

    requestAnimationFrame(frame);

    window.addEventListener('pageshow', function (ev) {
        if (ev.persisted) {
            t0 = performance.now();
        }
    });
})();
