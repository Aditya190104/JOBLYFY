# JOBLYFY advanced upgrade — 26 October 2026

The existing Django project has been enhanced in place. Its apps, custom user model, Django templates, SQLite compatibility, original assets and migration history remain intact. The preserved database still contains the original 6 users, 4 seeker profiles and 2 employer profiles. It has no job postings; fictional demonstration records are available only through an explicit development command.

## Diagnosed problems and fixes

| Finding | Implemented change |
| --- | --- |
| Empty job board | Verified the database had zero jobs; confirmed the active/unexpired queryset and template paths. Added a guarded, idempotent `seed_demo` command with 18 labelled sample roles and 3 fictional companies. Real posting and querying were exercised end to end. |
| Plain location field, no suggestions | Live suggestions from a local catalog and actual job locations; city aliases, state matching, keyboard and touch interactions, clear controls, offline fallback and click-only geolocation. |
| Weak search and limited filters | Shared token-based keyword search/ranking; company/category/skills matching; location, work mode/type, experience, date and company filters; optional annual-INR bands; approximate city-radius filtering. |
| Unstructured salary strings | Original text retained, nullable numerical bounds added. Validation and database constraints reject partial/inverted ranges. No legacy salary is guessed or rewritten. |
| Long, awkward results form on mobile | Top keyword/location bar, one connected GET form, desktop sidebar, mobile filter drawer with focus handling, removable chips, accurate counts, sorting, pagination and a wide-screen job preview. |
| Dropdown clipping in the existing hero | Adjusted overflow only during focus so suggestions remain reachable; tested mouse/touch targets at desktop and mobile widths. |
| Limited company context | Existing company profiles now include published user reviews and correctly labelled advertised-salary bounds with sample counts. No fabricated ratings or salary estimates. |
| Missing preference and update workflow | Saved job preferences filter the seeker dashboard. Application submissions/status changes/withdrawals create owned in-app notifications. Account settings include password changes. |
| Location display lacked maps | Optional employer coordinates with validation; on-demand OpenStreetMap iframe and persistent address/link fallback. No API key, paid service or external geocoding dependency. |

## What remains working

Registration for each role, username/unique-email login, POST logout, complete password reset, editable profiles, company logos, private validated PDF resumes, posting/editing/deactivation, saved jobs, application snapshots, duplicate prevention, pending cover-letter editing, eligible withdrawal, employer-owned candidate access and status changes. Existing public and dashboard route names are retained. All 49 prior regression tests remain in the suite.

The purple/lavender/navy identity, hero artwork, header/footer, local SVG assets, auth pages and dashboard foundation are preserved. New screens use the same typography, spacing, form and card components. No React, Node, PHP, frontend build tool or runtime CDN dependency has been introduced.

## Preservation and migration evidence

- Backups: `backups/db-before-upgrade.sqlite3` and `backups/db-before-advanced.sqlite3`.
- Every original row and column across the 16 pre-existing non-migration tables matches the advanced backup. Django added expected content-type and permission records for new models; original records are unchanged.
- All 9 existing migration Python files, including package initializers, match their pre-edit hashes. Three new forward migration files add optional fields, reviews, preferences and notifications.
- SQLite `integrity_check`: **ok**. `foreign_key_check`: **no errors**.
- Original account fields, role flags, profile content and password hashes are unchanged. No QA users, jobs, reviews, resumes or sample companies are in the delivered default database.
- Optional samples use unusable account passwords, cannot receive applications and are hidden from production browsing. The command backs up the selected database first and refuses to run with DEBUG=False. Deactivation preserves its records.

## Verification completed

| Verification | Result |
| --- | --- |
| Django system check | Passed, no issues. |
| `makemigrations --check --dry-run` | No changes detected. |
| Applied migration check | Passed on preserved database. |
| Fresh SQLite setup | All supplied migrations, cache-table creation and category initialization checked. |
| Automated backend suite | **75 tests passed**: 49 retained plus 26 advanced tests. |
| Static assets and JavaScript syntax | `collectstatic`, syntax and unused-name checks passed. |
| Full browser journeys | **17 checks passed** in Chromium: employer/seeker registration, posting, profiles, combined search, saved jobs, application/edit/status/withdrawal, private resume download, preferences, pending review submission, notifications and mobile navigation. |
| Responsive layout | **152 checks** across public and signed-in pages, from 320 to 1440 pixels. No horizontal overflow in those checks. Additional hero suggestion visibility/touch-target checks passed at desktop and mobile widths. |
| Accessibility automation | **29 page/state scans** with axe WCAG 2 A/AA and 2.1 AA rules, no violations found in those scans. Includes active suggestions, mobile filter dialog, preferences, reviews, settings and notifications. This is not a full accessibility certification. |
| Search interaction checks | Keyboard selection, Enter submission, selected city filtering, mobile drawer/Escape, clear location + radius, recent-search clearing, geolocation permission flow, denied-permission fallback and failed-endpoint fallback passed. |
| Without JavaScript | Mobile keyword/filter GET submission passed; plain navigation and server-rendered results remain usable. |
| Browser errors | No unexpected console errors or HTTP failures in the full normal journeys. Forced network failure/503 cases were explicitly induced to verify fallback behavior and are recorded separately. |
| Map interaction | No iframe before click; correct employer-coordinate iframe and persistent location/link after click. External OpenStreetMap rendering was not confirmed in this environment. |

Evidence logs and JSON summaries are under `docs/verification/`. Browser screenshots were used internally for visual review; they are not included in the distributable. All browser QA databases and uploads are excluded.

Backend coverage includes city aliases/state search, radius coordinates/centers, remote searches, keyword relevance, combined filters, posting age, pagination, invalid inputs, salary constraints, selected-preview scope, unsafe redirects, sample safeguards/collisions, review moderation/ownership/aggregates, preference matching, notification ownership/idempotence, and password changes. Existing authentication, CSRF, uploads, password-reset token flow and application ownership tests are retained.

## Manual setup and explicit limits

1. Follow `README.md` to generate a unique private environment, install pinned requirements, run migrations and create the database cache table. Do not overwrite a separately maintained newer database or media directory.
2. The default data has **no jobs**. Publish a role with an employer account, or deliberately run `seed_demo` locally to preview labelled sample listings. No external job-feed synchronization is implemented.
3. Live SMTP delivery remains unverified: configure your provider credentials to send real reset emails. The local console reset flow and complete reset tokens/templates are tested. Notifications are in-app, not email alerts.
4. Review moderation requires a non-employer administrator with permission. Reviews are self-reported and not employment-verified. No fake reviews are seeded; salary insights use only structured non-sample open listings.
5. The location catalog has 15 supported city centers, not universal geocoding coverage. Free-text search works elsewhere. Distance is approximate, not a route/travel-time estimate. Precise geolocation stays in the browser; real device GPS accuracy is not independently verified.
6. The optional map's live external availability is not confirmed. Its fallback address/link and opt-in loading are tested. No external service is required for normal job search.
7. Tested with Python 3.12 and headless Chromium on Linux. Windows commands are supplied for Python 3.11+, but physical Windows execution, Safari, Firefox and real-device touch testing have not been performed.
8. No public production deployment or load test was performed. Configure HTTPS, domain, WSGI/ASGI hosting, backups, email and provider policies before deployment. Keep resumes private and never commit the included personal database or backups publicly.

For the original bug audit, see `INITIAL_AUDIT.md`. For the pre-edit advanced audit, see `ADVANCED_AUDIT.md`. The previous report is retained as `UPGRADE_REPORT_2026-10-25.md` for history.
