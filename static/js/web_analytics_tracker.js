(function () {
    const cfg = window.LhexiaWebAnalyticsConfig || {};
    if (!cfg.trackUrl || cfg.enabled === false) return;

    const VISITOR_KEY = 'lhexia_web_visitor_key';
    const SESSION_KEY = 'lhexia_web_session_key';
    const SCROLL_KEY = 'lhexia_web_scroll_marks';
    const TRACKABLE_CLICK_SELECTORS = [
        '.btn',
        '[data-open-ai-demo]',
        '[data-ai-whatsapp]',
        '.landing-nav a',
        '.faq-card a',
        'a[href*="wa.me"]',
        'a[href*="whatsapp"]'
    ];

    function createId(prefix, includeTs) {
        const ts = Date.now().toString(36);
        let token = '';
        if (window.crypto && window.crypto.randomUUID) {
            token = window.crypto.randomUUID().replace(/-/g, '').slice(0, 24);
        } else {
            token = Math.random().toString(36).slice(2) + Date.now().toString(36);
        }
        return includeTs ? (prefix + '_' + ts + '_' + token) : (prefix + '_' + token);
    }

    function getOrCreate(key, storage, prefix, includeTs) {
        try {
            let value = storage.getItem(key);
            if (!value) {
                value = createId(prefix, includeTs);
                storage.setItem(key, value);
            }
            return value;
        } catch (e) {
            return createId(prefix, includeTs);
        }
    }

    const visitorKey = getOrCreate(VISITOR_KEY, window.localStorage, 'liz_v', true);
    const sessionKey = getOrCreate(SESSION_KEY, window.sessionStorage, 'liz_s', true);
    const pageviewKey = createId('liz_p', false);

    function getUtm(name) {
        try {
            return new URLSearchParams(window.location.search).get(name) || '';
        } catch (e) {
            return '';
        }
    }

    function getSourceTuple() {
        const utmSource = getUtm('utm_source');
        const utmMedium = getUtm('utm_medium');
        const utmCampaign = getUtm('utm_campaign');
        const referrer = document.referrer || '';
        let source = '';
        let medium = '';

        if (utmSource || utmMedium || utmCampaign) {
            source = utmSource || 'campaign';
            medium = utmMedium || 'campaign';
        } else if (!referrer) {
            source = 'direct';
            medium = 'direct';
        } else {
            let domain = '';
            try {
                domain = new URL(referrer).hostname.toLowerCase();
            } catch (e) {}
            if (/google\.|bing\.|yahoo\.|duckduckgo\.|ecosia\.|brave\./.test(domain)) {
                source = domain;
                medium = 'organic';
            } else if (/facebook\.|instagram\.|linkedin\.|x\.com|twitter\.|t\.co|youtube\.|tiktok\./.test(domain)) {
                source = domain;
                medium = 'social';
            } else if (/wa\.me|whatsapp\./.test(domain)) {
                source = domain;
                medium = 'whatsapp';
            } else {
                source = domain || 'referral';
                medium = 'referral';
            }
        }
        return {
            utm_source: utmSource,
            utm_medium: utmMedium,
            utm_campaign: utmCampaign,
            source: source,
            medium: medium
        };
    }

    const baseSource = getSourceTuple();
    const queue = [];
    let flushTimer = null;
    let activeSecondsBuffer = 0;
    let lastActiveTs = Date.now();
    let maxScrollDepth = 0;
    let sentScrollMarks = {};
    try {
        sentScrollMarks = JSON.parse(window.sessionStorage.getItem(SCROLL_KEY) || '{}') || {};
    } catch (e) {
        sentScrollMarks = {};
    }

    function slugify(value, limit) {
        const normalized = (value || '')
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-zA-Z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .replace(/_+/g, '_')
            .toLowerCase();
        return normalized.slice(0, limit || 80);
    }

    function pageFamily(pathname) {
        const path = pathname || '/';
        if (path === '/') return 'home';
        if (path === '/erp-ferreterias' || path === '/erp-retail-especializado') return 'money_page';
        if (path === '/lhexia-vs-defontana' || path === '/alternativa-a-defontana') return 'comparison';
        if (path === '/erp-con-bodega-por-voz' || path === '/como-reducir-quiebres-de-stock-en-ferreterias') return 'content_cluster';
        if (path === '/fundador' || path === '/mensaje-del-fundador') return 'founder';
        if (path === '/quienes-somos' || path === '/sobre-nosotros') return 'about';
        if (path.indexOf('/login') === 0 || path.indexOf('/acceso') === 0) return 'login';
        return 'other';
    }

    const currentPageFamily = pageFamily(window.location.pathname || '/');

    function basePayload() {
        return {
            visitor_key: visitorKey,
            session_id: sessionKey,
            session_key: sessionKey,
            pageview_key: pageviewKey,
            path: window.location.pathname || '/',
            full_url: window.location.href,
            page_title: document.title || '',
            referrer: document.referrer || '',
            source: baseSource.source,
            medium: baseSource.medium,
            utm_source: baseSource.utm_source,
            utm_medium: baseSource.utm_medium,
            utm_campaign: baseSource.utm_campaign
        };
    }

    function enqueue(eventName, payload) {
        queue.push(Object.assign(basePayload(), { event_name: eventName }, payload || {}));
        scheduleFlush();
    }

    function flush(useBeacon) {
        if (!queue.length) return;
        const batch = queue.splice(0, queue.length);
        const body = JSON.stringify({ events: batch });
        if (useBeacon && navigator.sendBeacon) {
            try {
                const blob = new Blob([body], { type: 'application/json' });
                navigator.sendBeacon(cfg.trackUrl, blob);
                return;
            } catch (e) {}
        }
        fetch(cfg.trackUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            keepalive: true,
            body: body
        }).catch(function () {});
    }

    function scheduleFlush() {
        if (queue.length >= 5) {
            flush(false);
            return;
        }
        if (flushTimer) return;
        flushTimer = window.setTimeout(function () {
            flushTimer = null;
            flush(false);
        }, 3500);
    }

    function syncHeartbeat(force) {
        const now = Date.now();
        if (!document.hidden) {
            const delta = Math.max(0, Math.round((now - lastActiveTs) / 1000));
            activeSecondsBuffer += Math.min(delta, 30);
        }
        lastActiveTs = now;
        if (activeSecondsBuffer >= 10 || force) {
            const deltaOut = activeSecondsBuffer;
            activeSecondsBuffer = 0;
            if (deltaOut > 0) {
                enqueue('heartbeat', { active_seconds: deltaOut });
            }
        }
    }

    function saveScrollMarks() {
        try {
            window.sessionStorage.setItem(SCROLL_KEY, JSON.stringify(sentScrollMarks));
        } catch (e) {}
    }

    function detectScrollDepth() {
        const doc = document.documentElement;
        const body = document.body;
        const height = Math.max(doc.scrollHeight, body.scrollHeight, doc.clientHeight);
        const viewport = window.innerHeight || doc.clientHeight || 1;
        const scrollTop = window.scrollY || doc.scrollTop || body.scrollTop || 0;
        const pct = Math.max(0, Math.min(100, Math.round(((scrollTop + viewport) / Math.max(height, 1)) * 100)));
        maxScrollDepth = Math.max(maxScrollDepth, pct);

        [25, 50, 75, 90].forEach(function (mark) {
            const key = window.location.pathname + ':' + mark;
            if (pct >= mark && !sentScrollMarks[key]) {
                sentScrollMarks[key] = true;
                saveScrollMarks();
                enqueue('scroll_depth', { scroll_depth: mark });
            }
        });
    }

    function describeTarget(el) {
        if (!el) return { label: '', target: '', ctaId: '', ctaGroup: '', ctaSurface: '', ctaText: '' };
        const text = (el.dataset.analyticsLabel || el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ');
        const label = text.slice(0, 160);
        const href = (el.getAttribute('href') || '').trim();
        const target = (href || el.id || el.name || '').slice(0, 300);
        const rawId = el.dataset.analyticsId || el.dataset.ctaId || '';
        const rawGroup = el.dataset.analyticsGroup || '';
        const rawSurface = el.dataset.analyticsSurface || '';
        const haystack = (label + ' ' + target).toLowerCase();

        let ctaId = slugify(rawId, 80);
        let ctaGroup = slugify(rawGroup, 40);
        let ctaSurface = slugify(rawSurface, 40) || currentPageFamily;

        const navMap = {
            '/erp-ferreterias': 'nav_erp_ferreterias',
            '/erp-retail-especializado': 'nav_erp_retail_especializado',
            '/lhexia-vs-defontana': 'nav_lhexia_vs_defontana',
            '/alternativa-a-defontana': 'nav_alternativa_defontana',
            '/erp-con-bodega-por-voz': 'nav_bodega_voz',
            '/como-reducir-quiebres-de-stock-en-ferreterias': 'nav_quiebres_stock',
            '/fundador': 'nav_fundador',
            '/quienes-somos': 'nav_quienes_somos',
            '/sobre-nosotros': 'nav_quienes_somos',
            '/login': 'acceso_privado'
        };

        if (!ctaId) {
            Object.keys(navMap).some(function (pathKey) {
                if (target.indexOf(pathKey) === 0 || target.indexOf(pathKey) !== -1) {
                    ctaId = navMap[pathKey];
                    ctaGroup = ctaGroup || (ctaId.indexOf('nav_') === 0 ? 'navigation' : 'login');
                    return true;
                }
                return false;
            });
        }

        if (!ctaId && (haystack.indexOf('whatsapp') !== -1 || haystack.indexOf('wa.me') !== -1)) {
            ctaId = haystack.indexOf('diagnostico') !== -1 ? 'whatsapp_diagnostico' : 'whatsapp_contacto';
            ctaGroup = ctaGroup || 'whatsapp';
        }
        if (!ctaId && haystack.indexOf('diagnostico') !== -1) {
            ctaId = 'diagnostico_ia';
            ctaGroup = ctaGroup || 'lead_capture';
        }
        if (!ctaId && (haystack.indexOf('login') !== -1 || haystack.indexOf('acceso privado') !== -1)) {
            ctaId = 'acceso_privado';
            ctaGroup = ctaGroup || 'login';
        }
        if (!ctaId && target.indexOf('#') === 0) {
            ctaId = 'anchor_' + (slugify(target.slice(1), 40) || 'cta');
            ctaGroup = ctaGroup || 'navigation';
        }
        if (!ctaId) {
            const base = slugify(label || target || currentPageFamily || 'cta', 60) || 'cta';
            ctaId = base.indexOf('cta_') === 0 || base.indexOf('nav_') === 0 ? base : ('cta_' + base);
            ctaGroup = ctaGroup || 'generic';
        }

        return {
            label: label,
            target: target,
            ctaId: ctaId,
            ctaGroup: ctaGroup || 'generic',
            ctaSurface: ctaSurface,
            ctaText: label
        };
    }

    document.addEventListener('click', function (ev) {
        const el = ev.target && ev.target.closest ? ev.target.closest('a,button') : null;
        if (!el) return;
        const shouldTrack = TRACKABLE_CLICK_SELECTORS.some(function (selector) {
            try { return el.matches(selector); } catch (e) { return false; }
        });
        if (!shouldTrack) return;

        const meta = describeTarget(el);
        enqueue('cta_click', {
            label: meta.label,
            target: meta.target,
            meta: {
                cta_id: meta.ctaId,
                cta_group: meta.ctaGroup,
                cta_surface: meta.ctaSurface,
                cta_text: meta.ctaText,
                page_family: currentPageFamily,
                tag: (el.tagName || '').toLowerCase(),
                id: (el.id || '').slice(0, 80),
                classes: (el.className || '').toString().slice(0, 180)
            }
        });

        const href = (el.getAttribute('href') || '').toLowerCase();
        if (el.hasAttribute('data-ai-whatsapp') || href.includes('wa.me') || href.includes('whatsapp')) {
            enqueue('conversion', {
                conversion_type: 'whatsapp_click',
                label: meta.label,
                target: meta.target,
                meta: {
                    origin: 'cta',
                    cta_id: meta.ctaId,
                    cta_group: meta.ctaGroup,
                    cta_surface: meta.ctaSurface,
                    cta_text: meta.ctaText,
                    page_family: currentPageFamily
                }
            });
        }
    }, { passive: true });

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            syncHeartbeat(true);
            flush(true);
        } else {
            lastActiveTs = Date.now();
        }
    });

    window.addEventListener('beforeunload', function () {
        syncHeartbeat(true);
        flush(true);
    });

    window.addEventListener('scroll', detectScrollDepth, { passive: true });
    window.setInterval(function () {
        if (!document.hidden) syncHeartbeat(false);
    }, 15000);

    enqueue('page_view', { scroll_depth: 0 });
    detectScrollDepth();

    window.LhexiaWebAnalytics = {
        getContext: function () {
            return Object.assign(basePayload(), {
                source: baseSource.source,
                medium: baseSource.medium,
                campaign: baseSource.utm_campaign
            });
        },
        track: function (eventName, payload) {
            enqueue(eventName, payload || {});
        },
        trackConversion: function (conversionType, payload) {
            enqueue('conversion', Object.assign({ conversion_type: conversionType }, payload || {}));
        },
        flush: function () {
            syncHeartbeat(true);
            flush(false);
        }
    };
})();
