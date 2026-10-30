# Advanced interface audit — 29 October 2026

Starting point: JOBLYFY-premium.zip version 5, verified SHA-256
66580364c48e78b68489591d13fd809963fcd499c24b70e7fdf0dd131a8f35ed.
The baseline has 76 Python files, 63 HTML templates, four stylesheets, three
JavaScript files and 13 migration files. The accounts/jobs/dashboard apps, pinned
requirements, native SVG icons, CSRF, database sessions and existing data remain.
There is no React, Tailwind, messaging/chat module or client-side tab router.

Findings before modification:
- A small subset of cards/headings had entrances; menus, forms, editor rows,
  detail sections and footer lacked a common motion policy.
- Search used ordinary GET navigation but obscured existing results with a skeleton.
  Location autocomplete is the actual asynchronous search operation.
- Save-job POST toggled state and navigated away. Repeating an uncertain request
  could undo the intended save, so asynchronous enhancement requires explicit intent.
- Dashboard aggregates covered only selected statuses. Charts must count all owned
  records, not the recent-five table, and must not imply conversion rates.
- Filter isolation omitted some background siblings; menu closing could leave focus
  in hidden content. These need keyboard checks alongside visual transitions.

Implementation extends existing templates, CSS and JavaScript. One motion layer
uses CSS, Intersection Observer and Web Animations, with reduced motion and visible
no-JS fallbacks. Public GET pages progressively opt into native transitions.
Explicit save/remove requests use the existing protected endpoint. Charts use
scoped ORM aggregates and keep text counts. No schema change is planned.

SQLite was backed up with its backup API to backups/db-before-motion.sqlite3.
Testing must use isolated copies; the shipped database must remain byte-identical.


Final implementation and verification were completed on 30 October 2026. See MOTION_UPGRADE_REPORT.md and docs/verification/motion/.
