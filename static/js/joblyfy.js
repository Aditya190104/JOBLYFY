/* Progressive enhancement: all important actions also work without JavaScript. */
(() => {
    const menuButton = document.querySelector('.menu-toggle');
    const menu = document.getElementById('main-navigation');
    const mobileMenu = matchMedia('(max-width: 950px)');
    if (menu) menu.inert = mobileMenu.matches;
    const closeMenu = () => {
        if (mobileMenu.matches && menu?.contains(document.activeElement)) menuButton.focus();
        if (menu) menu.inert = mobileMenu.matches;
        menu?.classList.remove('is-open');
        menuButton?.setAttribute('aria-expanded', 'false');
        menuButton?.setAttribute('aria-label', 'Open navigation');
    };
    menuButton?.addEventListener('click', () => {
        const open = menu.classList.toggle('is-open');
        menu.inert = !open && mobileMenu.matches;
        menuButton.setAttribute('aria-expanded', String(open));
        menuButton.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && menu?.classList.contains('is-open')) {
            closeMenu();
            menuButton.focus();
        }
    });
    document.addEventListener('click', (event) => {
        if (menu?.classList.contains('is-open') && !menu.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
        const dismiss = event.target.closest('[data-dismiss]');
        if (dismiss) dismiss.closest('.notice')?.remove();
    });
    mobileMenu.addEventListener('change', closeMenu);
    // One pending navigation per form, including Enter and alternate submitters.
    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (event.defaultPrevented) return;
        if (form.dataset.pending === 'true') {
            event.preventDefault();
            return;
        }
        if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
            event.preventDefault();
            return;
        }
        const button = event.submitter;
        if (!form.noValidate && !button?.formNoValidate && !form.checkValidity()) return;
        // Disabled buttons are omitted from POST. Preserve the intended action.
        if (button?.name) {
            form.querySelectorAll('[data-submit-action]').forEach(input => input.remove());
            const action = document.createElement('input');
            action.type = 'hidden';
            action.name = button.name;
            action.value = button.value;
            action.dataset.submitAction = '';
            form.append(action);
        }
        form.dataset.pending = 'true';
        form.setAttribute('aria-busy', 'true');
        // form.elements also includes filter buttons linked with form="job-search".
        [...form.elements].filter(el => el.matches('button[type="submit"],button:not([type]),input[type="submit"]') && !el.disabled).forEach(el => {
            el.dataset.pendingDisabled = '';
            el.disabled = true;
        });
        if (button) {
            button.dataset.originalLabel = button.innerHTML;
            button.setAttribute('aria-busy', 'true');
            button.textContent = form.method.toLowerCase() === 'get' ? 'Searching…' : 'Saving…';
        }
    });
    window.addEventListener('pageshow', () => {
        document.querySelectorAll('[data-submit-action]').forEach(input => input.remove());
        document.querySelectorAll('[data-pending]').forEach(form => {
            delete form.dataset.pending;
            form.removeAttribute('aria-busy');
        });
        document.querySelectorAll('[data-pending-disabled]').forEach(button => {
            button.disabled = false;
            delete button.dataset.pendingDisabled;
        });
        document.querySelectorAll('[data-original-label]').forEach(button => {
            button.innerHTML = button.dataset.originalLabel;
            button.removeAttribute('aria-busy');
            delete button.dataset.originalLabel;
        });
    });
    // Passwords stay in native form controls, never in browser storage.
    document.querySelectorAll('input[type="password"]').forEach(input => {
        const wrapper = document.createElement('div');
        wrapper.className = 'password-control';
        input.before(wrapper);
        wrapper.append(input);
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-toggle';
        toggle.textContent = 'Show';
        toggle.setAttribute('aria-controls', input.id);
        toggle.setAttribute('aria-pressed', 'false');
        const label = input.labels?.[0]?.textContent.replace('*', '').trim() || 'password';
        toggle.setAttribute('aria-label', 'Show ' + label.toLowerCase());
        toggle.addEventListener('click', () => {
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            toggle.textContent = show ? 'Hide' : 'Show';
            toggle.setAttribute('aria-pressed', String(show));
            toggle.setAttribute('aria-label', (show ? 'Hide ' : 'Show ') + label.toLowerCase());
        });
        wrapper.append(toggle);
    });
})();
