# Pre-change audit: job descriptions and screening

The supplied enhanced JOBLYFY project was reviewed before adding the screening system. The existing `accounts`, `jobs` and `dashboard` apps, configuration, routes, forms, models, migrations, templates, CSS, JavaScript, upload validation and tests were used as the integration starting point.

## Findings and integration decisions

| Existing behavior | Gap | Incremental change |
| --- | --- | --- |
| Employer-owned posting/editing and active/inactive toggle | No distinct draft, published, paused or closed state | Retain `is_active` and its original route; add publication state and owned lifecycle actions. |
| Description, requirements, benefits, salary, location, type, work mode, experience-level fields | No separate responsibilities, mandatory/preferred skills, numerical experience bounds or application instructions | Add structured fields beside the original fields, retaining existing text and relationships. |
| Private PDF validation and unique job/seeker application | Direct apply lacked a saved eligibility check, screening answers and review step | Keep `Application` and its uniqueness constraint; add a private saved draft and a server-validated final submission through the existing apply route. |
| Applicant dashboard, status updates, withdrawal and pending cover-letter edits | No evidence showing which rules and answers were used at submission | Store immutable-through-UI snapshots and typed answer records; preserve existing actions and their permissions. |
| Existing company and seeker profiles | Education/experience were free text and could not establish eligibility reliably | Collect only facts needed by configured rules; do not infer qualifications or experience from profile prose or PDF content. |
| Existing role decorators, CSRF, private resume routes and environment settings | New objects and stages would create additional ownership/bypass risks | Apply owned querysets, bounded formsets, stale-version checks, signed review tokens, backend recomputation and private file access. |
| Existing SQLite and 12 migration Python files | Changes must preserve old records and migration history | Back up first; add one forward migration; test against populated historical models and compare old columns after migration. |
| Existing purple/navy templates and responsive components | New recruiter and application pages were absent | Extend those layouts with a small screening stylesheet and progressive JavaScript. |

The original database had six users, four seeker profiles, two employer profiles, eight seeded categories and no job postings or applications. No real job/application history was available in this database to exercise migration semantics, so a separate populated migration regression test covers legacy active/inactive jobs, an application, a resume reference and password hashes.

The first-generation and advanced audits remain in `INITIAL_AUDIT.md` and `ADVANCED_AUDIT.md`. Existing duplicate-email handling, authentication, location search, filters, saved jobs, moderated reviews, notifications and password-reset behavior were retained. No fake reviews, qualifications, applications or jobs were inserted into the delivered database.

## Preservation boundary

- `backups/db-before-screening.sqlite3` was taken before this schema change. Earlier backups remain available.
- All twelve earlier migration Python files are preserved byte for byte. Only `jobs/0005_job_screening_workflow.py` is added.
- No migration drops a model or old field, deletes an application, resets a password or renames an account.
- New publication state maps existing active jobs to published and inactive jobs to paused. New application evidence defaults to empty/legacy without inventing historical answers.
- No new external integration, framework, runtime dependency, secret or API key is required.

See `UPGRADE_REPORT.md` for the actual checks performed, evidence locations and remaining limits.
