# JOBLYFY populated career catalog — 28 October 2026

The existing Django portal now ships with **18 published database-backed fictional jobs**, covering all 15 requested software/design roles, four demo companies and eight location/work regions. Existing views and ORM queries retrieve them for the homepage, listings, categories, companies, filters and details. No frontend job array was substituted.

## Implemented changes

- Distinct descriptions/tasks, qualifications, mandatory/preferred skills, experience bounds, illustrative pay, work mode/type, benefits, actual creation timestamps and future deadlines.
- **87 eligibility rules and 72 required questions** (four per job). Preferred skills stay advisory; remote roles have no city restriction. The existing backend validates all final submissions.
- Backup-first transactional `seed_demo_jobs`, stable unique identifiers, safe reruns, deadline renewal, pause/reopen, and cleanup that deletes only jobs without application/draft/saved-job references.
- Clearly labelled **local practice applications** through the real eligibility/questions/private PDF/review flow. Answers/snapshots belong to the selected job and are reviewed by its authorized recruiter. Production hiding and older browse-only demo restrictions remain.
- Correct visible-listing/sample counts, useful role summaries, monthly sample internship stipends with an annualized filter explanation, Delhi NCR aliases and work-from-home matching.
- Demo recruiters start with unusable passwords. The operator sets a private password interactively using `changepassword`. No shared credential is shipped.

No migration, dependency, stack conversion, paid service or API key is needed. The source catalog is `apps/jobs/data/demo_jobs.json`; it supplies database inserts, not frontend cards. The model has no openings-count field, so no count is invented. No fictional office coordinates are stored.

## Preservation

`backups/db-before-demo-jobs.sqlite3` preserves the database before insertion; earlier named backups remain. All original rows across **24 tables**, including password hashes, remain unchanged. All **13 migration Python files** are unchanged. SQLite integrity is **ok**, with no foreign-key errors.

The delivered database contains **10 accounts** (6 original + 4 demo employers), **4 seeker profiles**, **6 employers**, **23 categories**, **18 jobs**, **87 rules** and **72 questions**. It contains **zero applications, drafts and answers**. QA accounts, passwords, uploads and practice submissions were isolated and excluded from the ZIP.

## Verification

| Check | Observed result |
| --- | --- |
| Django system/model/migration checks | Passed; no pending migrations or model changes. |
| Backend suite | **134 tests passed**: all 117 prior tests plus 17 catalog integration tests. |
| Role-specific applications | Every one of the **18 roles** exercised through eligibility, four questions, PDF, review, submission, saved evidence, receipt and recruiter counts. |
| Search/filter tests | All 15 role categories, requested locations/aliases/state/remote searches, title/skill/company search, combined filters, types, experience, salaries, date, sorting and pagination. |
| Seed safety | Idempotence, preserved edits/passwords/records, production guard, identifier collisions, backup failure, lifecycle actions and referenced-record cleanup tested. |
| Browser journeys | **10 passed** in Chromium: populated home/results, autocomplete/search, categories/locations, pagination/sorting, mobile remote filter, correct empty state, signup, practice submission, private recruiter review/status and candidate tracking. |
| Browser routes | All **18 details**, **15 category filters/pages**, **8 location searches** returned expected records. |
| Responsive layout | **40 checks** across 1440, 1024, 768, 390 and 320 pixels; no overflow, broken images or unlabelled controls in those checks. |
| Accessibility | **8 axe scans**, WCAG 2 A/AA and 2.1 AA rules; no violations in scanned states. Not a complete accessibility certification. |
| Browser errors | No unexpected console or HTTP errors in normal journeys. |
| Other checks | Production-flag `check --deploy`, static collection, dependencies, JavaScript syntax and Ruff F checks passed. |
| Extracted ZIP setup | **Passed:** 14 setup/check commands, bundled-data preservation, fresh empty SQLite initialization, repeated seeding without duplicates, 8 public/auth routes, all 18 details and a complete saved practice application with private PDF/recruiter review. Evidence: `verification/demo-jobs/package-check.json`. |

Evidence is under `docs/verification/demo-jobs/`. Earlier reports remain historical evidence rather than claims that every old browser check was rerun. Screenshots were used internally and are not distributed.

## Setup and limits

Follow `README.md` from the folder containing `manage.py`. Keep any newer database, media and `.env` from your current installation and back them up. Run `seed_demo_jobs --refresh-deadlines` to add the catalog to that database and renew its deadlines for 60 days. It does not unpause jobs; `--reactivate` is explicit.

The jobs, companies, pay and benefits are fictional. Use synthetic PDFs for practice; no real employer receives them. Reviews and salary insights exclude sample data. Eligibility checks self-reported facts against explicit rules; it does not verify credentials, infer degree equivalence, parse resumes for skills or decide hiring. PDF validation is not malware scanning.

Tests ran on Linux with Python 3.12, Django 5.2.18 and Chromium. Physical Windows execution, Firefox/Safari, physical devices, live SMTP, external map rendering, production deployment/load and concurrent-browser stress testing remain unverified. Python 3.11+ Windows commands are supplied. No external service is required for normal local practice.

See `DEMO_JOBS_AUDIT.md`, `DEMO_JOBS.md`, `DEMO_CATALOG.md` and the retained `UPGRADE_REPORT_2026-10-28_SCREENING.md`.
