# Original project audit — before enhancement

The source archive contains 9,889 entries (about 68.6 MB uncompressed), including a Windows virtual environment. There are 73 application/configuration/asset files after generated dependencies and caches are excluded. All Python modules, migrations, template content, inline styles/scripts, URL references, database schema and configuration fragments were inspected before implementation.

## Architecture and data

- `manage.py`, ASGI and WSGI use `core.settings` and `core.urls`.
- Installed project apps: `apps.accounts`, `apps.jobs`, `apps.dashboard`.
- Django templates use Tailwind's runtime CDN, Font Awesome and Google Fonts. There is no React or Node backend.
- Custom user model: `accounts.CustomUser`, with separate employer/seeker flags and one-to-one profiles. Login uses Django's username field, with an extra email lookup in the view.
- Core models: Employer, JobSeeker, Category, Job, Application. Applications already have a job/seeker uniqueness rule.
- SQLite contains six users, four seeker profiles, two employer profiles, no jobs, no categories and no applications. No media directory was supplied. Some profile filenames may therefore refer to missing files.
- All four original application migrations are retained byte-for-byte. Database backup: `backups/db-before-upgrade.sqlite3`.

## Confirmed problems

1. README references a nonexistent requirements file; the archive instead bundles platform-specific dependencies.
2. `Job.experience_level` exists in migration 0002/database but not the model. `makemigrations --check --dry-run` proposes removing it. Model title/location lengths also disagree with the existing migration.
3. GET job posting uses JobForm while POST uses a narrower JobPostForm, losing category, requirements and deadline. The template renders every widget as an input, breaking textareas and selects.
4. Category search choices are never populated. Listing filter controls sit outside their form, company/experience/salary filters are unwired, and sorting is decorative. Salary is stored as text, so numeric filtering cannot truthfully be inferred.
5. Applying redirects to a nonexistent dashboard URL name. Employer status changes have a view and template link but no URL. Dashboard home and search-results templates are missing.
6. Profile views are read-only but link to nonexistent edit routes. Seeker templates treat text fields as related managers and reference fields that do not exist. Employer public URL reversal supplies an argument to an argument-free private-profile route.
7. Reset templates, email templates and explicit namespaced success redirects are missing. Email configuration is absent.
8. Login can raise MultipleObjectsReturned for duplicate emails and reveals whether an account exists. Role denial paths have invalid redirects. GET logout changes state.
9. Uploads lack size/type/content validation. Catch-all development media serving exposes resumes by URL. Job/application ownership checks are inconsistent; review lookup can return an unhandled exception. Dates are not enforced.
10. Withdrawal deletes applications; status eligibility differs between the template and view. Dashboard pending counts incorrectly use the limited recent-application list.
11. Settings contain a hardcoded secret, DEBUG is always true, password validators are absent, LOGIN_URL is unset, and duplicate top-level settings/apps are incomplete and unused.
12. Homepage renders raw settings text, uses inconsistent JobPortal/JobFly branding and unsupported job-volume claims. Footer links are placeholders. Styles and scripts are duplicated across templates; mobile navigation clones controls.
13. Tests are empty scaffolds. A successful original system check therefore did not establish that user journeys work.

## Preservation and implementation policy

Keep table identities, original migration files, existing user/password records and uploaded asset references. Extend with forward migrations. Archive the six inactive duplicate Python fragments under `docs/legacy/` as text, retaining their contents without import ambiguity. Keep original static assets. Use validated Django forms, explicit role/ownership checks and real database aggregates. Do not seed fake job or employer records into the supplied database.
