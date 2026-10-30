> Historical report for the first upgrade. See UPGRADE_REPORT.md for current functionality and verification.

# JOBLYFY upgrade report

Completed 25 October 2026. The provided Django project is the foundation; its apps, model identities, original migration files, SQLite compatibility and original assets are retained.

## Problems corrected

| Original issue | Implemented correction |
| --- | --- |
| Missing dependency file and a bundled Windows virtual environment | Pinned runtime dependencies; normal Python virtual-environment setup; generated dependencies/caches excluded from the deliverable. |
| Conflicting inactive settings/app fragments | `core.settings` remains the single active configuration; six inactive fragments preserved under `docs/legacy/` as text. |
| Model/migration drift for experience, title and location | Restored the already-migrated experience field and original field lengths. Added two forward migrations; all four original migrations remain byte-for-byte unchanged. |
| Broken dashboard, search, profile-edit, reset and review routes | Connected the missing routes, forms, templates and namespaced redirects. Search uses one implementation. |
| Different posting forms for GET and POST, and incorrectly rendered widgets | One complete validated ModelForm for create/edit, with actual selects, date controls and textareas. |
| Disconnected filters and cosmetic sorting | Working keyword, location, category, employer, job type, experience, work mode and sorting; encoded query parameters retained through pagination. |
| Inconsistent role checks and unsafe review lookups | Shared role decorators, owner-scoped querysets, controlled 403/404 responses and POST-only mutations. |
| Unrestricted uploaded media and unvalidated resumes/logos | Size/extension/content validation; private resume download routes; explicit image route; no catch-all public media serving. |
| Duplicate applications and deleting withdrawals | Existing uniqueness constraint retained; duplicate submission handled; withdrawal becomes a status without deleting history. |
| Incorrect dashboard counts | Database aggregates with ownership filters and genuine open/pending/accepted counts, independent of recent-item limits. |
| Hardcoded secret, unconditional DEBUG, missing password/email configuration | Generated local secret, environment-based settings, Django password validators, safe redirects, generic authentication errors, basic persistent throttling and complete reset templates. |
| Static settings text on homepage, inconsistent branding and placeholder links | Unified JOBLYFY branding, local assets, functioning navigation and honest database-backed content/empty states. |
| No meaningful tests | 49 automated tests plus actual browser journeys, responsive checks and targeted accessibility scans. |

## New and completed functionality

- Employer and job seeker registration, username or unique-email login, POST logout, persistent/session-only sign-in choice and password reset.
- Editable account, career and company profiles; validated company logo and resume upload.
- Job posting, editing, activation/deactivation, deadline enforcement, categories, company directory and company detail pages.
- Search, filters, stable pagination and sorting.
- Saved jobs, application submission with a resume snapshot, pending cover-letter editing and eligible withdrawal.
- Employer review of owned candidates, private resume downloads and application statuses visible to seekers.
- Separate dashboards, recent activity tables and real database statistics.
- Database backup and idempotent category initialization commands.

## UI and accessibility

A consistent indigo, white and dark-navy design system replaces fragmented styling while keeping Django templates. It includes a branded hero, career artwork made with local SVG/CSS, reusable cards, clear filters, company pages, role-selection and authentication screens, dashboard side navigation, profile forms, candidate review, status badges and responsive tables.

All essential actions submit normal Django forms. JavaScript adds mobile-menu state, Escape-key behavior, confirmation and submission feedback. The UI includes visible focus indicators, form labels, validation feedback, a skip link, reduced-motion support, empty states and locally served assets. No third-party runtime CSS/JS CDN is required.

Browser inspection found and corrected a narrow-screen sidebar overflow. Accessibility scans found and corrected low-contrast dashboard labels and status text.

## Verification completed

| Check | Result |
| --- | --- |
| `manage.py check` | Passed, no issues. |
| `manage.py check --deploy` with production-style environment values | Passed, no issues. This does not represent a deployed-host audit. |
| `makemigrations --check --dry-run` | Passed, no pending model changes. |
| `migrate --check` | Passed. |
| Supplied database migration | Passed with the original six accounts/profile records preserved. |
| Fresh empty SQLite initialization | Passed in an isolated browser-test database and Django test database. |
| `collectstatic --noinput` | Passed; local assets and Django admin assets collected. Generated output excluded from the ZIP. |
| Django automated suite | **49 tests passed.** |
| Template compilation | All 48 HTML templates compiled. Active template paths were also exercised through routes. |
| Browser workflows | **13 completed checks**, including employer signup/post/profile, seeker signup/PDF/profile, combined search filters, saved jobs, applying, pending edits, employer login/logout, candidate review/download/status, withdrawal, and mobile navigation/keyboard focus. |
| Responsive browser checks | **96 page/viewport combinations**, primarily 1440, 768, 390 and 320 px; listing also checked at 1024 px. No page-level horizontal overflow, broken loaded images or unlabelled form controls in those checks. Tables and dashboard tabs scroll within their own containers on narrow screens. |
| JavaScript and route requests during browser journeys | No console/page errors or HTTP error responses. |
| Targeted automated accessibility scans | Nine representative routes checked with axe-core against its WCAG 2 A/AA and WCAG 2.1 AA rules. No violations detected after corrections. This is not a full accessibility certification. |
| Preservation comparison | Original user/profile fields, password hashes, group memberships, stored session rows, original job/application records and original migration files matched the input. |

Test evidence is included in `docs/verification/`. Browser checks used clearly marked temporary QA accounts and one temporary QA job in a separate database. **None of those accounts, jobs, resumes, browser dependencies or screenshots are included in the delivered user database or ZIP.**

The backend tests cover role/ownership denial, CSRF, safe redirects, invalid and oversized uploads, duplicate applications, legacy duplicate-email login, password-reset token completion/reuse, expired jobs, application rules and statistics as well as successful journeys. Testing identified and fixed a pagination-order warning. A test fixture was also corrected to reopen a file before comparing its contents.

## Preservation details

The input contained six users, two company profiles, four seeker profiles, one stored session, and no jobs, applications, categories or media files. The delivered database retains the accounts and adds eight category labels. No record counts, job ads, ratings or hiring success claims are fabricated.

The backup `backups/db-before-upgrade.sqlite3` was created before schema changes. `docs/original-file-hashes.json` records the initial non-generated source/asset files. Unused legacy files are retained as text; all original image assets remain under `static/images/`.

Two groups of existing nonempty email addresses were duplicated in the original database. Those values were not merged, deleted or reassigned. Username login remains available. New email duplication is rejected by forms; the legacy email column intentionally has no newly imposed unique database constraint.

## Required manual configuration and limitations

1. Run the Windows commands in the README. Generate your private `.env`; do not ship or commit it. Existing accounts must sign in again because the old hardcoded secret has been replaced.
2. Configure real SMTP settings and a valid sender for inbox delivery. Reset-email creation, token use and templates were tested locally; external SMTP delivery was not tested.
3. The supplied database has no jobs, so an employer must publish roles. No invented vacancies were inserted just to fill the design.
4. Windows installation commands are provided for your Python 3.11 setup, but execution occurred on Linux/Python 3.12. Physical Windows, Safari, Firefox, assistive-technology sessions and actual mobile devices were not available. Chromium desktop/mobile-size layouts were tested.
5. Production hosting, HTTPS/proxy setup, delivery-provider credentials, external website availability, high-concurrency load and infrastructure backups are outside this local verification. SQLite and the basic database-backed throttle suit a local portfolio/small deployment; public hosting should be reviewed for its expected workload.
6. Resume validation is format/size/readability validation, not antivirus scanning or removal of PDF active content. Files download as attachments and require authorization.
7. Salary remains a free-text field for compatibility. No numeric salary filter is claimed. Applicants may edit pending cover letters; submitted resume snapshots are retained. Withdrawn applications cannot be resubmitted.
8. Existing public company data is employer-provided, not independently verified. The UI does not claim certified trust, external reviews, job placements, Google/LinkedIn authentication, messaging or background email notifications.

No known failing automated backend checks, browser journeys or tested responsive layouts remain at delivery. The scope above describes the evidence and the limits of that statement.
