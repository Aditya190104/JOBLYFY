# JOBLYFY screening upgrade — 28 October 2026

The existing Django application has been extended in place with structured job descriptions, recruiter-owned lifecycle management, configurable eligibility rules and screening questions, and a reviewed candidate application workflow. The original apps, authentication, SQLite support, template architecture, visual identity and previous features remain.

## Implemented behavior

| Area | Result |
| --- | --- |
| Recruiter job management | Draft, publish, pause and close actions; complete JD sections, mandatory/preferred skills, experience bounds, salary, location/work mode/type, deadline and instructions. Ownership and stale-edit validation are enforced server-side. |
| Eligibility | Saved rules for accepted qualifications, relevant experience, mandatory skills, allowed locations/relocation and work arrangement. Each rule can block independently. Missing facts remain unknown; preferred skills are advisory. Candidates can correct answers and rerun. |
| Questions | Up to 20 ordered Yes/No, single-select, multi-select and short-text questions; requiredness, editing, deletion and validated expected-answer rules. Short text stays manual. Required No answers are handled correctly. |
| Candidate workflow | Eligibility → questions → private PDF selection/upload → review and consent. Owned drafts can be resumed or discarded. The backend rechecks current rules, deadline, ownership, answers, PDF and a signed, expiring review token before creating an application. |
| Review and tracking | Saved answers, candidate facts, assessment and original JD/rules are preserved with the application. Candidates get a receipt; recruiters get screening filters and evidence beside profile/resume review. Existing status changes, notifications, cover-letter editing and eligible withdrawal remain. |
| Security | CSRF, role/ownership checks, bounded formsets, stale draft/revision handling, duplicate constraint, private files, server-computed results and snapshot preservation. Direct posting to the old apply URL cannot bypass the review. |
| UI | Existing purple/lavender/navy components extended with structured JD sections, clear rule policies, four application stages, readable results, review panels, question ordering and responsive layouts. Submission loading retains the clicked action. |
| Maintenance | Dry-run-by-default stale draft cleanup command, reproducible checks and documented Windows installation/upgrade. No additional dependency, API key or external service is needed. |

The original gaps and preservation decisions are documented in `SCREENING_AUDIT.md`. Earlier reports and audits remain available. The previous 75 backend tests were retained; older direct-apply tests were adapted to exercise the new real reviewed flow while preserving their validation assertions.

## Database changes and preservation

- One new forward migration: **`jobs/0005_job_screening_workflow.py`**. All twelve earlier migration Python files are byte-identical to the previous delivered ZIP.
- Added structured JD/publication/revision fields to `Job`, and evidence snapshots plus screening outcome to the existing `Application` model.
- Added `EligibilityRule`, `ScreeningQuestion`, `ApplicationDraft` and `ScreeningAnswer`, with owned relationships, bounded values and uniqueness constraints. Deleting a question keeps its historical answer snapshot.
- Existing active jobs map to published, inactive jobs to paused. Historical applications are labelled legacy; their status, resume reference and uniqueness relationship remain intact. No historical eligibility answers are invented.
- A database backup was made before schema changes: `backups/db-before-screening.sqlite3`. Earlier backups remain in the project.
- Original columns and rows in **17 existing tables** compare unchanged against that backup. All prior migration/content-type/permission metadata rows remain, with expected additions for the new schema.
- SQLite integrity is **ok** and foreign-key checks report no errors.
- The delivered database contains the original **6 users, 4 seeker profiles, 2 employer profiles and 8 categories**. There are **zero jobs, applications, drafts, questions, answers or eligibility rules**. All QA data and uploaded QA PDFs were isolated outside the delivered project.
- A populated historical-migration regression separately proves that legacy active/inactive jobs, an application, resume references and password hashes survive the forward migration.

## Verification completed

| Check | Observed result |
| --- | --- |
| Django system check | Passed, no issues. |
| Migration/model consistency | `makemigrations --check --dry-run` reports no changes; `migrate --check` passes. |
| Backend regression suite | **117 tests passed**: 75 retained, 41 new screening/permission/workflow tests, 1 populated migration test. |
| Production-sensitive Django settings | `check --deploy` under production flags passes without warnings. This is a settings check, not a deployment. |
| Static and code checks | `collectstatic`, JavaScript syntax checks and Ruff undefined/unused-name checks pass. |
| Full browser journeys | **15 passed** in headless Chromium, including account registration, structured job/rule creation, all question types/reordering, publication, unknown and corrected eligibility, blocking questions, private PDF/review, submission, receipt, duplicate prevention, editing, recruiter filtering/status changes, pause/close and withdrawal. |
| Responsive layout | **55 checks** across 1440, 1024, 768, 390 and 320 pixels. No page overflow, broken images or unlabelled form controls in these checks. Mobile review and recruiter evidence were also visually inspected. |
| Accessibility automation | **11 page/state scans**, axe WCAG 2 A/AA and 2.1 AA rules, no violations in those scans. This is not a full accessibility certification. |
| Browser errors | No unexpected console errors or HTTP failures in the normal journeys. One intentional 400 response is recorded for the negative blocking-question check. |
| Without JavaScript | Recruiter question editor save passed. A complete no-JavaScript candidate journey was not separately exercised. |
| Packaged installation | **Passed**: 13 setup/check commands; preserved bundled database; brand-new SQLite initialization; 10 public/auth routes; job creation, eligibility, screening, PDF review/submission, persisted answer, candidate receipt, private download and recruiter review. See `verification/screening/package-check.json`. |

New backend coverage includes mandatory/advisory/preferred differences, incomplete facts, exact skills, numeric boundaries, aliases/relocation/remote rules, each question type, option validation, required No answers, ownership/CSRF, foreign question IDs, formset bounds, stage bypass, forged results, consent, expired/cross-user/stale review tokens, changing rules, closed/expired jobs, PDF source/validation, private draft downloads, immutable evidence, status filters, duplicate/withdrawn records and dry-run retention.

Existing authentication, password-reset token flow, combined keyword/location/filter search, saved jobs, company reviews/preferences, notifications and other regression coverage continue to run. Historical advanced browser evidence is retained under `verification/advanced/`; it is not represented as a new rerun of every old browser check.

Current evidence is under `verification/screening/`. Screenshots were used internally for visual review and are not distributed. No browser runner, test database, test upload, virtual environment, cache, private `.env` or generated static collection is included in the ZIP.

## Setup and limits

1. Follow the Windows commands in `README.md` from the folder containing `manage.py`. If upgrading your own newer copy, retain its database, media and environment, back them up, then apply the migration. Do not overwrite newer local user data with the bundled database.
2. The preserved database has no jobs. Register an employer and publish one, or explicitly use `seed_demo` locally for labelled fictional listings. Samples cannot receive applications. No jobs, ratings or salaries are fabricated as real records.
3. Eligibility is a transparent comparison of self-reported facts with configured rules. Qualifications use explicit accepted names; skills use whole normalized names. It does not verify credentials, infer a degree hierarchy, rank candidates with AI or parse resumes for qualifications. Recruiters review text and advisory gaps themselves.
4. Resume validation checks PDF type, readability, size and page count; it is not malware or active-content scanning. Serve private files only through authorized routes. Configure an operator retention policy; draft cleanup requires explicit execution.
5. Live SMTP delivery remains unverified. Configure real provider credentials for password-reset email. In-app notifications and the local reset/token flow are tested.
6. No new external service is required. Optional live OpenStreetMap rendering, real GPS accuracy and external email availability were not verified in this upgrade.
7. Tested on Linux with Python 3.12, Django 5.2.18 and headless Chromium. Python 3.11+ Windows commands are supplied but not executed on a physical Windows machine. Firefox, Safari and physical mobile devices remain unverified.
8. No production deployment, traffic/load test, backup-restore exercise against a real deployment, or full simultaneous-browser race stress test was performed. SQLite uses short `IMMEDIATE` write transactions and a 20-second timeout; configure hosting, HTTPS, storage, email and traffic limits for production.

Previous reports: `UPGRADE_REPORT_2026-10-26_ADVANCED.md` and `UPGRADE_REPORT_2026-10-25.md`.
