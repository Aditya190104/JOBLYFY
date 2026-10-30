/* Shared progressive motion. No router, hidden content or scroll animation loop. */
(() => {
    'use strict';
    const preference = matchMedia('(prefers-reduced-motion: reduce)');
    const active = new Set(), running = new WeakMap(), seen = new WeakSet(), observed = new WeakSet();
    let observer;
    const allowed = () => !preference.matches && !document.hidden;
    const stop = element => running.get(element)?.cancel();
    const animate = (element, frames, options = {}) => {
        if (!allowed() || !element?.animate) return;
        stop(element);
        const animation = element.animate(frames, {
            duration: 380, easing: 'cubic-bezier(.22,1,.36,1)', ...options
        });
        active.add(animation);
        running.set(element, animation);
        const cleanup = () => {
            active.delete(animation);
            if (running.get(element) === animation) running.delete(element);
        };
        animation.addEventListener('finish', cleanup, { once: true });
        animation.addEventListener('cancel', cleanup, { once: true });
        return animation;
    };
    const surfaces = [
        '.hero-copy > *', '.hero-opportunities', '.platform-strip > div',
        '.section-heading', '.page-banner .container', '.search-heading-copy',
        '.dashboard-heading', '.auth-form-panel', '.auth-art', '.panel',
        '.job-card', '.company-card', '.category-card', '.result-card', '.role-card',
        '.stat-grid > article', '.profile-nudge', '.steps > div', '.employer-cta',
        '.application-heading', '.application-steps', '.empty-state', '.error-page',
        '.notice', '.notification-row', '.draft-row', '.footer-top > div', '.developer-credit'
    ].join(',');
    const reveal = (element, index = 0) => {
        if (seen.has(element)) return;
        seen.add(element);
        element.dataset.motionState = 'revealed';
        // Focus and pointer input take priority over decorative movement.
        if (!element.contains(document.activeElement) && !element.matches(':hover')) {
            animate(element, [
                { opacity: .92, transform: 'translateY(12px)' },
                { opacity: 1, transform: 'translateY(0)' }
            ], { delay: Math.min(index, 4) * 35 });
        }
        element.querySelectorAll('[data-chart-bar]').forEach((bar, i) => {
            animate(bar, [{ transform: 'scaleX(.08)' }, { transform: 'scaleX(1)' }],
                { duration: 480, delay: i * 25 });
        });
    };
    const observe = (scope = document) => {
        const candidates = [...scope.querySelectorAll(surfaces)];
        if (scope instanceof Element && scope.matches(surfaces)) candidates.unshift(scope);
        candidates.forEach(element => {
            if (observed.has(element) || element.parentElement?.closest(surfaces)) return;
            observed.add(element);
            element.dataset.motionState = preference.matches ? 'static' : 'ready';
            if (observer && allowed()) observer.observe(element);
        });
    };
    if ('IntersectionObserver' in window) {
        observer = new IntersectionObserver(entries => {
            const groups = new Map();
            entries.filter(entry => entry.isIntersecting).forEach(({ target }) => {
                observer.unobserve(target);
                const parent = target.parentElement, index = groups.get(parent) || 0;
                groups.set(parent, index + 1);
                reveal(target, index);
            });
        }, { threshold: .02, rootMargin: '0px 0px 20px 0px' });
    }
    observe();
    // One short intro, no perpetual decorative loop or pause control required.
    document.querySelectorAll('.hero-glow,.hero-halo').forEach((element, index) => {
        animate(element, [
            { transform: 'translate(-12px,8px) scale(.97)', opacity: .55 },
            { transform: 'translate(0,0) scale(1)', opacity: 1 }
        ], { duration: 4200, delay: index * 120, easing: 'ease-out' });
    });
    const cancelAll = () => { active.forEach(animation => animation.cancel()); active.clear(); };
    preference.addEventListener('change', () => {
        cancelAll();
        if (preference.matches) {
            observer?.disconnect();
            document.querySelectorAll('[data-motion-state="ready"]').forEach(el => {
                el.dataset.motionState = 'static';
            });
        } else {
            document.querySelectorAll('[data-motion-state="static"]').forEach(el => {
                if (!seen.has(el)) { el.dataset.motionState = 'ready'; observer?.observe(el); }
            });
        }
    });
    document.addEventListener('visibilitychange', () => { if (document.hidden) cancelAll(); });
    window.addEventListener('pagehide', cancelAll);
    window.addEventListener('pageshow', event => { if (event.persisted) cancelAll(); });
    window.addEventListener('pageswap', event => {
        if (preference.matches || document.querySelector('[data-pending="true"]')) event.viewTransition?.skipTransition();
    });
    window.addEventListener('pagereveal', event => { if (preference.matches) event.viewTransition?.skipTransition(); });
    ['focusin', 'pointerdown'].forEach(type => document.addEventListener(type, event => {
        for (let node = event.target; node instanceof Element; node = node.parentElement) stop(node);
    }, { passive: true }));
    document.addEventListener('joblyfy:reveal', event => observe(event.detail.element));
    document.addEventListener('joblyfy:reorder', event => {
        animate(event.detail.element, [
            { opacity: .8, transform: 'translateY(' + event.detail.direction * 10 + 'px)' },
            { opacity: 1, transform: 'translateY(0)' }
        ], { duration: 220 });
    });
    document.addEventListener('joblyfy:saved', event => {
        animate(event.detail.button.querySelector('.icon'), [
            { transform: 'scale(.85)' }, { transform: 'scale(1.08)', offset: .6 }, { transform: 'scale(1)' }
        ], { duration: 240 });
    });
    document.querySelectorAll('.form-errors,.field-errors,.assessment').forEach(element => {
        animate(element, [{ opacity: .65 }, { opacity: 1 }], { duration: 240 });
    });
    document.addEventListener('invalid', event => {
        animate(event.target, [{ opacity: .7 }, { opacity: 1 }], { duration: 180 });
    }, true);
    document.querySelectorAll('input[type="file"]').forEach((input, index) => {
        const message = document.createElement('p');
        message.className = 'file-selection';
        message.id = 'selected-file-' + index;
        message.setAttribute('role', 'status');
        message.hidden = true;
        input.after(message);
        input.setAttribute('aria-describedby', ((input.getAttribute('aria-describedby') || '') + ' ' + message.id).trim());
        input.addEventListener('change', () => {
            const file = input.files[0];
            message.hidden = !file;
            message.textContent = file ? 'Selected: ' + file.name + ' · ' +
                Math.max(1, Math.round(file.size / 1024)) +
                ' KB. Uploaded and checked when you submit this form.' : '';
            if (file) animate(message, [{ opacity: .75 }, { opacity: 1 }], { duration: 180 });
        });
        input.form?.addEventListener('reset', () => { message.hidden = true; message.textContent = ''; });
    });
    document.querySelectorAll('[data-section-nav]').forEach(nav => {
        const links = [...nav.querySelectorAll('a[href^="#"]')];
        const select = hash => links.forEach(link => {
            if (link.hash === hash) link.setAttribute('aria-current', 'location');
            else link.removeAttribute('aria-current');
        });
        const sync = () => select(location.hash || links[0]?.hash);
        sync();
        window.addEventListener('hashchange', sync);
        nav.addEventListener('click', event => {
            const link = event.target.closest('a[href^="#"]');
            if (link) select(link.hash);
        });
    });
})();
