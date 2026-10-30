# Changelog

## 30 October 2026 — advanced interface and motion

- Shared reduced-motion-aware reveals, finite hero accents, native public page
  transitions and responsive menu/drawer feedback across the existing layouts.
- Server-confirmed in-place saves with explicit, idempotent save/remove intent.
- Owned application-status charts; job-description anchors; file and editor feedback.
- Fixed error-number contrast, drawer focus isolation, resize focus restoration,
  and feedback animations being cancelled by focus or pointer guards.
- No runtime dependency or migration changes. Existing database bytes retained.
- See docs/MOTION_UPGRADE_REPORT.md for the current file list and verification.

## 29 October 2026 — Premium UI and persistent authentication

- Shared navy/violet design, actual featured-job hero, refined cards/forms/search,
  readable mobile controls, dark role workspaces and application tables.
- Aditya Raj developer credit with safe LinkedIn link on public, account and
  dashboard pages; reduced-motion-aware animation and real submission feedback.
- Fixed password-space trimming on login, consistent signup/login session expiry,
  transactional identity rechecks, unambiguous case-insensitive usernames and
  preserved safe destinations after login throttling.
- Explicit database session settings and opt-in trusted HTTPS proxy support.
- No database records, models, migration history or dependencies changed.
- See docs/UPGRADE_REPORT.md for tests, setup and remaining manual checks.


## Populated career catalog — 28 October 2026

- Added 18 detailed fictional software/design roles, 15 role categories, 4 demo companies, 87 eligibility rules and 72 screening questions.
- Added backup-first idempotent `seed_demo_jobs`, safe deadline renewal, pause/reactivate and cleanup that retains referenced jobs.
- Enabled explicitly labelled local practice applications through the existing backend, with private resumes and recruiter review; retained production hiding and legacy demo restrictions.
- Connected actual listing counts, useful card summaries, monthly illustrative internship stipends, Delhi NCR alias and work-from-home search.
- Preserved original data and all 13 migrations; no new dependencies or external API keys. Added 17 tests to the 117 existing tests.

## Job descriptions, eligibility and screening — 28 October 2026

- Added owned draft/publish/pause/close management and structured responsibilities, qualifications, mandatory/preferred skills, experience bounds and application instructions.
- Added configurable mandatory eligibility rules, independent blocking switches, explicit unknown results and advisory preferred skills.
- Added up to 20 configurable Yes/No, single-select, multi-select and short-text screening questions with ordering, requiredness and validated matching rules.
- Added private saved application drafts, four-step eligibility/questions/resume/review flow, signed review tokens and final backend revalidation.
- Preserved submitted candidate facts, job/rule snapshots and typed answers; added candidate receipts and recruiter screening filters/evidence review.
- Retained existing search, profiles, saved jobs, notifications, cover-letter editing, status updates and eligible withdrawal. Protected submitted evidence from those edits.
- Added one forward migration and a pre-change database backup; retained every previous migration and original record.
- Added 42 tests, including populated legacy migration coverage. Updated Windows setup, upgrade and privacy/retention guidance. Detailed verified results and limits are in `docs/UPGRADE_REPORT.md`.

## Advanced upgrade — 26 October 2026

- Diagnosed empty listings as a database with no job records; added explicit, protected development samples.
- Added Indian city autocomplete, aliases, keyboard support, location clearing, local geolocation lookup and offline fallback.
- Added shared keyword relevance, approximate nearby search, salary-band and date filters alongside all existing filters.
- Added top search controls, mobile filter drawer, removable chips, query-preserving sorting/pagination and desktop role preview.
- Added optional structured INR salary bounds and workplace coordinates without replacing old salary/location text.
- Connected genuine featured/recent jobs, categories and company sections; retained honest empty states and real counts.
- Added moderated user company reviews and clearly labelled salary summaries from existing postings only.
- Added job preferences, in-app application updates and password settings.
- Improved hero dropdown overflow, clickable cards, responsive layouts and accessibility.
- Preserved accounts, profiles, original migrations, assets and all prior features; added 3 forward migrations and a second database backup.
- Retained 49 tests and added 26 backend tests. Browser verification and known limits are in `docs/UPGRADE_REPORT.md`.
