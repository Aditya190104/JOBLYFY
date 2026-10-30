/* Same CSRF-protected endpoint; ordinary POST forms work without this script. */
(() => {
    'use strict';
    if (!window.fetch || !window.AbortController) return;
    const pending = new Set(), feedback = document.querySelector('[data-action-feedback]');
    if (!feedback) return;
    const message = feedback.querySelector('[data-action-message]');
    const link = feedback.querySelector('[data-action-link]'), savedUrl = link.href;
    let lastButton;
    const show = (text, error = false, href = savedUrl, label = 'View saved jobs') => {
        feedback.hidden = false;
        feedback.classList.toggle('is-error', error);
        message.textContent = text;
        link.href = href;
        link.textContent = label;
    };
    feedback.querySelector('[data-action-dismiss]').addEventListener('click', () => {
        if (lastButton?.isConnected) {
            const target = !lastButton.disabled ? lastButton
                : lastButton.closest('[data-job-card]')?.querySelector('[data-job-link]')
                    || lastButton.closest('section[tabindex="-1"]') || document.getElementById('main');
            target?.focus({ preventScroll: true });
        }
        feedback.hidden = true;
    });
    document.addEventListener('submit', async event => {
        const form = event.target;
        if (!form.matches('[data-save-job]')) return;
        event.preventDefault();
        const id = form.dataset.saveJob;
        if (pending.has(id)) return;
        const button = event.submitter || form.querySelector('button[type="submit"]');
        lastButton = button;
        const payload = new FormData(form), intent = payload.get('intent');
        if (!['save', 'remove'].includes(intent)) return;
        pending.add(id);
        const related = [...document.querySelectorAll('[data-save-job]')].filter(el => el.dataset.saveJob === id);
        related.forEach(el => {
            el.setAttribute('aria-busy', 'true');
            el.querySelector('button[type="submit"]').disabled = true;
        });
        const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 12000);
        show(intent === 'save' ? 'Saving this opportunity…' : 'Removing saved opportunity…');
        try {
            const response = await fetch(form.action, {
                method: 'POST', body: payload, credentials: 'same-origin',
                headers: { Accept: 'application/json' }, signal: controller.signal
            });
            if (response.redirected) {
                const target = new URL(response.url);
                if (target.origin === location.origin && target.pathname === '/accounts/login/') {
                    show('Your session has ended. Sign in before saving this job.', true,
                        '/accounts/login/?next=' + encodeURIComponent(location.pathname + location.search), 'Sign in');
                    return;
                }
                throw new Error('unexpected-response');
            }
            if (response.status === 403) {
                show('This update was not authorized. Refresh and sign in with your job seeker account.',
                    true, location.href, 'Refresh page');
                return;
            }
            if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw new Error('unexpected-response');
            const data = await response.json();
            if (!response.ok) {
                show(data.error || 'This job could not be updated. Refresh for its latest status.', true, location.href, 'Refresh page');
                return;
            }
            if (String(data.job_id) !== id || typeof data.saved !== 'boolean') throw new Error('unexpected-response');
            related.forEach(el => {
                el.elements.intent.value = data.saved ? 'remove' : 'save';
                const control = el.querySelector('button[type="submit"]');
                control.classList.toggle('is-saved', data.saved);
                control.setAttribute('aria-pressed', String(data.saved));
                const label = control.querySelector('[data-save-label]');
                if (label) label.textContent = data.saved ? 'Remove saved job' : 'Save for later';
                else control.setAttribute('aria-label', (data.saved ? 'Unsave ' : 'Save ') + el.dataset.jobTitle);
            });
            show(data.message);
            document.dispatchEvent(new CustomEvent('joblyfy:saved', { detail: { button } }));
        } catch {
            // No blind retry: a dropped response can follow a committed write.
            // The explicit intent makes a user's retry safe and idempotent.
            show('Could not confirm the update. Check your connection, then retry or refresh to see the saved state.',
                true, location.href, 'Refresh saved state');
        } finally {
            clearTimeout(timeout);
            pending.delete(id);
            related.forEach(el => {
                el.removeAttribute('aria-busy');
                el.querySelector('button[type="submit"]').disabled = false;
            });
        }
    }, true);
})();
