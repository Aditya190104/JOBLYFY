/* JOBLYFY search enhancements. The normal GET search remains usable without JavaScript. */
(() => {
    'use strict';
    const catalog = JSON.parse(document.getElementById('location-catalog')?.textContent || '[]');
    const normalize = (value) => value.toLocaleLowerCase().replace(/[^\p{L}\p{N}\s]/gu, '').trim().replace(/\s+/g, ' ');
    const fallback = (query) => {
        const term = normalize(query);
        const choices = catalog.filter(city => !term || [...city.aliases, city.state, `${city.name} ${city.state}`].some(name => normalize(name).includes(term)))
            .slice(0, 7).map(city => ({
                value: city.name,
                label: `${city.name}, ${city.state}`,
                count: null
            }));
        if (!term || 'remote work from home'.includes(term)) choices.push({
            value: 'Remote',
            label: 'Remote',
            count: null
        });
        return choices.slice(0, 8);
    };
    const element = (tag, className, text) => {
        const el = document.createElement(tag);
        if (className) el.className = className;
        if (text !== undefined) el.textContent = text;
        return el;
    };
    const distance = (a, b) => {
        const rad = value => value * Math.PI / 180;
        const deltaLat = rad(b.lat - a.lat),
            deltaLon = rad(b.lon - a.lon);
        const h = Math.sin(deltaLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(deltaLon / 2) ** 2;
        return 6371.0088 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1 - h)));
    };
    document.querySelectorAll('[data-location-input]').forEach((input, index) => {
        const wrapper = element('div', 'location-combobox');
        input.before(wrapper);
        wrapper.append(input);
        const controls = element('div', 'location-controls');
        const clear = element('button', 'location-clear', '×');
        clear.type = 'button';
        clear.setAttribute('aria-label', 'Clear location');
        const current = element('button', 'location-current', '◎');
        current.type = 'button';
        current.setAttribute('aria-label', 'Use my current location');
        current.title = 'Use my current location (permission required)';
        controls.append(clear, current);
        wrapper.append(controls);
        const list = element('div', 'location-options');
        list.id = `location-options-${index}`;
        list.setAttribute('role', 'listbox');
        list.setAttribute('aria-label', 'Suggested locations');
        list.hidden = true;
        const status = element('span', 'location-status sr-only');
        status.id = `location-status-${index}`;
        status.setAttribute('role', 'status');
        const loading = element('span', 'location-loading');
        loading.hidden = true;
        loading.setAttribute('aria-hidden', 'true');
        wrapper.append(list, status, loading);
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-controls', list.id);
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-describedby', `${input.getAttribute('aria-describedby') || ''} ${status.id}`.trim());
        input.setAttribute('autocomplete', 'off');
        let options = [],
            active = -1,
            timer, controller, sequence = 0;
        const close = () => {
            sequence += 1;
            clearTimeout(timer);
            controller?.abort();
            loading.hidden = true;
            input.removeAttribute('aria-busy');
            list.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
            active = -1;
        };
        const choose = (option) => {
            input.value = option.value;
            close();
            input.focus();
            input.dispatchEvent(new Event('change', {
                bubbles: true
            }));
            status.textContent = `${option.value} selected. Press Search jobs to see matching listings.`;
        };
        const draw = (rows, offline = false) => {
            const selectedValue = options[active]?.value;
            options = rows;
            active = rows.findIndex(row => row.value === selectedValue);
            list.replaceChildren();
            input.removeAttribute('aria-activedescendant');
            rows.forEach((option, i) => {
                const item = element('div', 'location-option');
                item.id = `${list.id}-${i}`;
                item.setAttribute('role', 'option');
                item.setAttribute('aria-selected', String(i === active));
                if (i === active) input.setAttribute('aria-activedescendant', item.id);
                item.append(element('span', '', option.label));
                if (Number.isInteger(option.count)) item.append(element('small', '', `${option.count} open`));
                item.addEventListener('pointerdown', event => event.preventDefault());
                item.addEventListener('click', () => choose(option));
                list.append(item);
            });
            list.hidden = rows.length === 0;
            input.setAttribute('aria-expanded', String(rows.length > 0));
            status.textContent = rows.length ? `${rows.length} suggestions. Use up and down arrows to choose.${offline ? ' Offline city suggestions; live counts unavailable.' : ''}` : 'No suggestions. You can still search any city or state by typing its name.';
        };
        const suggest = async () => {
            const run = ++sequence;
            controller?.abort();
            controller = new AbortController();
            const requestController = controller;
            const timeout = setTimeout(() => requestController.abort(), 5000);
            loading.hidden = false;
            input.setAttribute('aria-busy', 'true');
            status.textContent = 'Finding locations…';
            // Immediate offline catalog makes the control useful even when the endpoint is unavailable.
            draw(fallback(input.value), true);
            try {
                const response = await fetch(`/locations/suggest/?q=${encodeURIComponent(input.value)}`, {
                    signal: controller.signal,
                    headers: {
                        'Accept': 'application/json'
                    }
                });
                if (!response.ok) throw new Error('Suggestions unavailable');
                const result = await response.json();
                if (run === sequence && document.activeElement === input) draw(result.results);
            } catch (error) {
                if (run === sequence && document.activeElement === input) draw(fallback(input.value), true);
            } finally {
                clearTimeout(timeout);
                if (run === sequence) {
                    loading.hidden = true;
                    input.removeAttribute('aria-busy');
                }
            }
        };
        input.addEventListener('focus', () => {
            status.classList.add('sr-only');
            suggest();
        });
        input.addEventListener('input', () => {
            status.classList.add('sr-only');
            close();
            timer = setTimeout(suggest, 160);
        });
        input.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                close();
                return;
            }
            if (event.key === 'Tab') {
                close();
                return;
            }
            if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
                event.preventDefault();
                if (list.hidden) draw(fallback(input.value), true);
                if (!options.length) return;
                active = (active + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
                [...list.children].forEach((item, i) => item.setAttribute('aria-selected', String(i === active)));
                const chosen = list.children[active];
                input.setAttribute('aria-activedescendant', chosen.id);
                chosen.scrollIntoView({
                    block: 'nearest'
                });
            } else if (event.key === 'Enter' && !list.hidden && active >= 0) {
                event.preventDefault();
                choose(options[active]);
            }
        });
        document.addEventListener('pointerdown', event => {
            if (!wrapper.contains(event.target)) close();
        });
        input.addEventListener('blur', () => setTimeout(() => {
            if (!wrapper.contains(document.activeElement)) close();
        }, 0));
        clear.addEventListener('click', () => {
            input.value = '';
            if (input.form?.elements.radius) input.form.elements.radius.value = '';
            status.classList.add('sr-only');
            close();
            input.focus();
            status.textContent = 'Location cleared. Search across all locations.';
            input.dispatchEvent(new Event('change', {
                bubbles: true
            }));
        });
        current.addEventListener('click', () => {
            close();
            status.classList.remove('sr-only');
            if (!navigator.geolocation || !window.isSecureContext) {
                status.textContent = 'Current location needs HTTPS or localhost. Enter a city instead.';
                return;
            }
            current.disabled = true;
            status.textContent = 'Waiting for location permission…';
            navigator.geolocation.getCurrentPosition(position => {
                current.disabled = false;
                const nearby = catalog.map(city => ({
                    ...city,
                    km: distance({
                        lat: position.coords.latitude,
                        lon: position.coords.longitude
                    }, city)
                })).sort((a, b) => a.km - b.km)[0];
                if (!nearby || nearby.km > 50) {
                    status.textContent = 'Your location is outside our supported city centers. Enter your city manually.';
                    return;
                }
                // Precise coordinates never leave the browser and are never saved to recent searches.
                input.value = nearby.name;
                input.dispatchEvent(new Event('change', {
                    bubbles: true
                }));
                status.textContent = `Using nearby ${nearby.name}. Check the city, then search. Your precise location stays on this device.`;
            }, () => {
                current.disabled = false;
                status.textContent = 'Location could not be accessed. You can enter a city or choose Remote.';
            }, {
                enableHighAccuracy: false,
                timeout: 10000,
                maximumAge: 300000
            });
        });
    });
    // Optional recent searches are local to this browser and can be cleared at any time.
    const historyKey = 'joblyfy.recent-searches.v1';
    const readHistory = () => {
        try {
            const value = JSON.parse(localStorage.getItem(historyKey) || '[]');
            return Array.isArray(value) ? value.filter(item => typeof item?.search === 'string' && typeof item?.location === 'string').slice(0, 4) : [];
        } catch {
            return [];
        }
    };
    const drawHistory = () => document.querySelectorAll('[data-recent-searches]').forEach(container => {
        const recent = readHistory();
        container.replaceChildren();
        if (!recent.length) return;
        container.append(element('span', '', 'Recent'));
        recent.forEach(item => {
            const link = element('a', '', [item.search, item.location].filter(Boolean).join(' · '));
            link.href = `/jobs/?${new URLSearchParams({search: item.search.slice(0, 150), location: item.location.slice(0, 100)})}`;
            container.append(link);
        });
        const clear = element('button', 'text-button', 'Clear history');
        clear.type = 'button';
        clear.addEventListener('click', () => {
            try {
                localStorage.removeItem(historyKey);
            } catch {
                /* Storage is optional. */ }
            drawHistory();
        });
        container.append(clear);
    });
    drawHistory();
    document.querySelectorAll('[data-job-search]').forEach(form => {
        const keyword = form.querySelector('[name="search"]');
        if (keyword) {
            const wrap = element('div', 'keyword-control');
            keyword.before(wrap);
            wrap.append(keyword);
            const clear = element('button', 'keyword-clear', '×');
            clear.type = 'button';
            clear.setAttribute('aria-label', 'Clear keyword');
            clear.addEventListener('click', () => {
                keyword.value = '';
                keyword.focus();
            });
            wrap.append(clear);
        }
        form.addEventListener('submit', () => {
            const item = {
                search: form.elements.search?.value.trim() || '',
                location: form.elements.location?.value.trim() || ''
            };
            if (item.search || item.location) {
                const recent = [item, ...readHistory().filter(old => old.search !== item.search || old.location !== item.location)].slice(0, 4);
                try {
                    localStorage.setItem(historyKey, JSON.stringify(recent));
                } catch {
                    /* Search works with storage disabled. */ }
            }
            form.setAttribute('aria-busy', 'true');
            // Normal GET navigation uses the submit button's actual busy state.
        });
    });
    // One actual filter form, displayed as an accessible modal drawer on smaller screens.
    const filters = document.getElementById('search-filters');
    const openFilters = document.querySelector('[data-filter-open]');
    const closeFilters = document.querySelector('[data-filter-close]');
    const backdrop = document.querySelector('[data-filter-backdrop]');
    const mobile = window.matchMedia('(max-width: 900px)');
    if (filters && openFilters) {
        document.documentElement.classList.add('enhanced-filters');
        openFilters.hidden = false;
        closeFilters.hidden = false;
        let inertNodes = [];
        const close = (restore = true) => {
            const hadFocus = filters.contains(document.activeElement);
            const closeHadFocus = document.activeElement === closeFilters;
            filters.inert = mobile.matches;
            filters.classList.remove('drawer-open');
            filters.removeAttribute('role');
            filters.removeAttribute('aria-modal');
            openFilters.setAttribute('aria-expanded', 'false');
            backdrop.hidden = true;
            document.body.classList.remove('drawer-active');
            inertNodes.forEach(node => {
                node.inert = false;
            });
            inertNodes = [];
            if (mobile.matches && (restore || hadFocus)) openFilters.focus();
            else if (!mobile.matches && closeHadFocus) filters.querySelector('input, select')?.focus();
        };
        const open = () => {
            if (!mobile.matches) return;
            filters.inert = false;
            filters.classList.add('drawer-open');
            filters.setAttribute('role', 'dialog');
            filters.setAttribute('aria-modal', 'true');
            openFilters.setAttribute('aria-expanded', 'true');
            backdrop.hidden = false;
            document.body.classList.add('drawer-active');
            // Isolate every sibling on the path to body, including notices and banners.
            inertNodes = [];
            for (let node = filters; node.parentElement && node !== document.body; node = node.parentElement) {
                [...node.parentElement.children].filter(sibling => sibling !== node && sibling !== backdrop && !sibling.inert)
                    .forEach(sibling => inertNodes.push(sibling));
            }
            inertNodes.forEach(node => {
                node.inert = true;
            });
            closeFilters.focus();
        };
        filters.inert = mobile.matches;
        openFilters.addEventListener('click', open);
        closeFilters.addEventListener('click', () => close());
        backdrop.addEventListener('click', () => close());
        mobile.addEventListener('change', () => close(false));
        filters.addEventListener('keydown', event => {
            if (!filters.classList.contains('drawer-open')) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                close();
            }
            if (event.key === 'Tab') {
                const nodes = [...filters.querySelectorAll('a[href], button:not([disabled]), input, select, textarea')].filter(node => node.getClientRects().length > 0);
                const first = nodes[0],
                    last = nodes[nodes.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                }
                if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }
        });
        if (filters.querySelector('.field-errors') && mobile.matches) open();
    }
    document.querySelectorAll('[data-load-map]').forEach(button => button.addEventListener('click', () => {
        const frame = document.createElement('iframe');
        frame.title = 'Workplace location on OpenStreetMap';
        frame.src = button.dataset.loadMap;
        frame.loading = 'lazy';
        frame.referrerPolicy = 'strict-origin-when-cross-origin';
        frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-popups');
        button.closest('[data-map]').querySelector('[data-map-frame]').replaceChildren(frame);
        button.hidden = true;
    }));
    document.querySelectorAll('[data-job-card]').forEach(card => card.addEventListener('click', event => {
        if (!event.target.closest('a, button, input, form, select') && !window.getSelection()?.toString()) {
            const link = card.querySelector('[data-job-link]');
            if (link) window.location.assign(link.href);
        }
    }));
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('[data-job-search]').forEach(form => form.removeAttribute('aria-busy'));
        document.querySelector('.search-results')?.classList.remove('is-loading');
    });
})();
