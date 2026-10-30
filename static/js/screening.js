/* Progressive enhancement only; all answer and rule validation is server-side. */
(() => {
    document.documentElement.classList.add('js-screening');
    const editor = document.querySelector('[data-question-editor]');
    if (!editor) return;
    const rows = editor.querySelector('[data-question-rows]');
    const total = editor.querySelector('[name="questions-TOTAL_FORMS"]');
    const status = editor.querySelector('[data-question-status]');
    const activeRows = () => [...rows.children].filter(row => !row.querySelector('[name$="-DELETE"]')?.checked);
    const renumber = () => activeRows().forEach((row, index) => {
        row.querySelector('[name$="-position"]').value = index + 1;
        row.querySelector('h2').textContent = `Question ${index + 1}`;
    });
    editor.addEventListener('click', event => {
        if (event.target.closest('[data-add-question]')) {
            if (activeRows().length >= 20 || Number(total.value) >= 40) {
                status.textContent = 'Up to 20 active questions. Save deletions before adding more.';
                return;
            }
            rows.insertAdjacentHTML('beforeend', editor.querySelector('#empty-question').innerHTML.replaceAll('__prefix__', total.value));
            total.value = Number(total.value) + 1;
            renumber();
            document.dispatchEvent(new CustomEvent('joblyfy:reveal', { detail: { element: rows.lastElementChild } }));
            rows.lastElementChild.querySelector('[name$="-prompt"]').focus();
            status.textContent = 'Question added. Save questions to keep your changes.';
            return;
        }
        const up = event.target.closest('[data-question-up]'),
            down = event.target.closest('[data-question-down]');
        const button = up || down;
        if (!button) return;
        const row = button.closest('[data-question-row]');
        if (up && row.previousElementSibling) rows.insertBefore(row, row.previousElementSibling);
        if (down && row.nextElementSibling) rows.insertBefore(row.nextElementSibling, row);
        renumber();
        button.focus();
        document.dispatchEvent(new CustomEvent('joblyfy:reorder', { detail: { element: row, direction: up ? -1 : 1 } }));
        status.textContent = 'Order changed. Save questions to keep it.';
    });
    editor.addEventListener('change', event => {
        if (event.target.name.endsWith('-DELETE')) event.target.closest('[data-question-row]').classList.toggle('question-deleted', event.target.checked);
    });
})();
