(function () {
    function initLandingNav() {
        var nav = document.querySelector('header.landing-nav');
        if (!nav) {
            return;
        }
        var links = nav.querySelector('.landing-nav-links');
        if (!links || nav.querySelector('.landing-nav-toggle')) {
            return;
        }

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'landing-nav-toggle';
        btn.setAttribute('aria-expanded', 'false');
        btn.setAttribute('aria-controls', 'landing-nav-menu');
        btn.setAttribute('aria-label', 'Abrir menú de navegación');
        links.id = 'landing-nav-menu';
        btn.innerHTML =
            '<i class="bi bi-list" aria-hidden="true"></i>' +
            '<i class="bi bi-x-lg" aria-hidden="true"></i>';
        nav.insertBefore(btn, links);

        function setOpen(open) {
            nav.classList.toggle('is-open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            btn.setAttribute('aria-label', open ? 'Cerrar menú de navegación' : 'Abrir menú de navegación');
        }

        btn.addEventListener('click', function () {
            setOpen(!nav.classList.contains('is-open'));
        });

        links.querySelectorAll('a').forEach(function (anchor) {
            anchor.addEventListener('click', function () {
                setOpen(false);
            });
        });

        window.addEventListener('resize', function () {
            if (window.matchMedia('(min-width: 721px)').matches) {
                setOpen(false);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLandingNav);
    } else {
        initLandingNav();
    }
})();
