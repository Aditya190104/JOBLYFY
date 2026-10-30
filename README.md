# JOBLYFY

A Django job portal upgraded in place from the original jobportal project, with a connected job board, offline location suggestions, structured job descriptions, recruiter-configured eligibility and screening questions, reviewed applications, and genuine company insights. Job seekers can build a profile, discover and save opportunities, apply with a PDF resume, and track their applications. Employers can manage their company profile, publish and edit roles, review their own candidates, download authorized resumes, and update application statuses.

The original `apps.accounts`, `apps.jobs`, `apps.dashboard`, custom user model, SQLite database and migration history are retained. This is a Django template application; **Node, npm, React and a frontend build step are not required**.

The supplied local-development database now includes **18 published fictional software/design jobs**, 15 role categories, 4 demo companies, 87 eligibility rules and 72 screening questions. They support clearly labelled practice applications. See `docs/DEMO_JOBS.md`.

## Premium interface and reliable accounts

The advanced interface release adds shared scroll reveals, finite hero atmosphere,
menu/drawer transitions, keyboard-safe feedback and reduced-motion support across
the existing layouts. Saved jobs update in place after server confirmation; both
dashboards show current application-status distributions from their own records.
No new runtime dependency or migration is required. See
`docs/MOTION_UPGRADE_REPORT.md` for the modified-file list and current verification,
and `docs/MOTION_SYSTEM.md` for the implementation.

When upgrading, extract into a separate folder and copy your current `db.sqlite3`,
`media/` and `.env` into it before running setup. Keep a backup of the old folder.
Do not replace newer local accounts/applications with the supplied sample database.
If your database path is configured through environment variables, keep that path.

Shared navy/violet/lavender styling now covers public pages, job search, companies,
authentication, both dashboards and the full application workflow. Mobile text and
controls, short reduced-motion-aware animations, actual loading feedback and
password visibility controls use local assets. The shared footer credits **Aditya
Raj** with a safe LinkedIn link. See `docs/DESIGN_SYSTEM.md`.

Login now preserves exact password spaces. New identities are rechecked inside the
SQLite save transaction. Signup/unchecked login use browser-length sessions;
**Keep me signed in** lasts 14 days. Keep your existing `.env`, database and uploads
across restarts and upgrades. See `docs/AUTHENTICATION.md` for troubleshooting.

## Windows setup (PowerShell or Command Prompt)

Install **Python 3.11 or newer**. Extract the ZIP and open the `JOBLYFY` folder containing `manage.py`. In File Explorer, open that folder, type `powershell` in the address bar, and press Enter. Confirm `dir manage.py` shows the file. **Do not run `cd JOBLYFY` again if you are already inside that folder.** Then run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\configure_env.py
.\.venv\Scripts\python.exe manage.py backup_database
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createcachetable
.\.venv\Scripts\python.exe manage.py seed_categories
.\.venv\Scripts\python.exe manage.py seed_demo_jobs --refresh-deadlines
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver
```

Open **http://127.0.0.1:8000/**. Keep the terminal open. Stop the server with **Ctrl+C**.

The commands use the virtual environment's Python directly, so you do not need to activate it or change PowerShell's execution policy. If your installed version is 3.12 or newer, replace `py -3.11` in the first command with that version or `py -3`. Do not reuse the old project's bundled virtual environment.

If you opened a terminal in the parent folder first, run `cd JOBLYFY` before the commands. If you already have your own newer database or media directory, retain those and make a backup before applying the upgrade; do not overwrite them with the delivered database. See the migration notes below.

Optional administration account:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Visit http://127.0.0.1:8000/admin/. No administrator or demonstration password is shipped. Create ordinary employer and job seeker accounts through the registration pages to use those workflows. An administrator without a seeker/employer profile is routed to an administrative account landing page.

## Sample listings and recruiter access

The bundled database is already populated. If you retain your own newer database, this command adds the same catalog without overwriting existing records:

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo_jobs --refresh-deadlines
```

The command backs up the selected SQLite database before writes and requires `DJANGO_DEBUG=True`. It creates missing records and renews existing catalog deadlines for 60 days without unpausing jobs. Ordinary `seed_demo_jobs` reruns preserve deadlines too. No credentials, applications or reviews are fabricated. Demo jobs are hidden and new applications are blocked with DEBUG=False; do not enable DEBUG on a public deployment.

Register a job seeker and open a sample's **Check eligibility & apply** link. Its real backend workflow saves a labelled practice application after eligibility, screening, PDF selection and review. Use a synthetic PDF without private information. No real employer receives it.

To edit seeded jobs and review their applications, choose a private password interactively:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword joblyfy_demo_stack
```

Then sign in with that username and your password. Company accounts are `joblyfy_demo_stack`, `joblyfy_demo_pixel`, `joblyfy_demo_cloud` and `joblyfy_demo_route`; each owns different jobs and sees only its candidates. Passwords start unusable, are never shipped, and existing user passwords are unchanged.

```powershell
# Hide catalog jobs without losing history
.\.venv\Scripts\python.exe manage.py seed_demo_jobs --deactivate
# Publish existing catalog jobs and renew deadlines
.\.venv\Scripts\python.exe manage.py seed_demo_jobs --reactivate
```

Optional `--remove-unused` deletes only catalog jobs with no applications, drafts or saved-job references. All accounts/categories and referenced jobs remain. Pause referenced jobs to remove them from listings. Normal seeding recreates missing entries. To add more samples, add complete entries with unique stable slugs to `apps/jobs/data/demo_jobs.json`; existing slugs identify jobs and must not be renamed. Edit existing jobs/questions through their recruiter dashboard; seed reruns preserve edits.

The older `seed_demo` command remains compatible and creates separate browse-only `joblyfy-v1:` samples. Use `seed_demo_jobs` for this software/design catalog and practice workflow. Full details are in `docs/DEMO_JOBS.md`.

## Included data and preservation

- `db.sqlite3` retains the original six accounts (four seekers and two employers), plus four demo employer accounts with unusable passwords. It has 18 demo jobs, 87 rules and 72 questions, with no submitted applications, drafts or QA accounts bundled. Existing password hashes, account fields and original profile values are unchanged.
- `backups/db-before-upgrade.sqlite3` preserves the original database, `backups/db-before-advanced.sqlite3` preserves the previously enhanced database before the advanced migrations, and `backups/db-before-screening.sqlite3` preserves the database before the screening migration. `backups/db-before-demo-jobs.sqlite3` preserves the database immediately before catalog insertion. `backups/db-before-premium.sqlite3` preserves the full populated database before this visual/authentication upgrade. The original uploaded ZIP also remains available through its version history.
- The original uploaded database had no jobs, applications or categories. Eight categories were added previously; this release adds 15 role categories for a total of 23. New companies/jobs are explicitly fictional development examples. No real vacancies, placements, ratings or testimonials are fabricated.
- Featured/recent listings and searches now retrieve the seeded records. Homepage listing totals identify the sample count; the registered-company count and salary insights exclude demo companies. Empty search states mean no open records match.
- Existing duplicate email addresses are preserved. If an old email matches multiple accounts, sign in with your unique **username**. New registrations and email changes reject addresses already in use. Existing accounts are not merged or renamed.
- The original archive did not contain a `media/` directory. Existing references to missing company logos use initials; upload an image again to replace them. A missing resume returns a controlled unavailable-file response.
- Preserve your existing `.env` and secret. Losing or replacing it invalidates sessions and reset links, but account records/password hashes remain. `configure_env.py` never overwrites an existing `.env`.
- Do not publish the database, backups, `.env`, resumes or other personal data in a public Git repository. They are ignored by the included `.gitignore`.

## First working walkthrough

1. Choose **Get started → Build my team**, register an employer, and complete the company profile.
2. Select **Post a job**. Fill the title, category, full description, responsibilities, qualifications, mandatory/preferred skills, experience bounds, location, work mode, employment type, benefits, deadline, and application instructions. Company ownership comes from your account. Salary text is optional; both annual INR bounds enable numeric filtering. Save as **Draft** while preparing the role.
3. In the job editor, define accepted qualifications, allowed locations, relocation and work-arrangement requirements as needed. Each mandatory rule has an independent **block application** setting. Keep preferred skills advisory. Save, then open **Questions** from **Manage jobs**.
4. Add up to 20 Yes/No, single-select, multiple-select, or short-text questions. Set required answers, display order, and optional automatic matching rules. Short-text answers always need human review. Save the questions, then **Publish** the job.
5. Sign out and register a job seeker. Complete the profile; a resume must be an unencrypted PDF, up to 5 MB and 1–30 pages.
6. Open the job and choose **Check eligibility & apply**. Enter the requested facts, check the results, correct answers if needed, and continue. Complete screening questions, select your profile resume or upload another PDF, add an introduction, and review everything before confirming submission.
7. Sign in as the employer. Open **Applications → Review** to see the submitted answers, eligibility evidence, original JD snapshot, profile, and authorized resume. Filter by screening outcome and update the application status.
8. The seeker sees the receipt and status in **My applications**, plus real in-app **Updates**. Eligible pending applications retain cover-letter editing; eligible applications can be withdrawn. Saved drafts can be continued or discarded from the seeker dashboard.

Pause a job to stop new applications temporarily; publish again to reopen it with a valid deadline. Close it when hiring ends. These actions keep application history. No Google/LinkedIn login, chat, external job feed or payment control is presented as a working feature.

## Eligibility and screening behavior

- The checker compares self-reported facts with the employer's explicitly saved rules. Results are **met**, **not met**, or **not enough information**. It does not verify credentials, infer qualifications from a PDF, or promise that a candidate is fully qualified.
- Qualification matching uses employer-entered accepted names, ignoring case and extra spacing. Enter alternatives such as `B.Tech, B.E.` explicitly; no automatic degree hierarchy is assumed. Skills use whole comma/newline-separated names, so Java does not match JavaScript. Employers should include the actual spellings they accept.
- Relevant experience accepts numeric years from 0 to 60 and checks inclusive minimum/maximum bounds. Empty experience remains unknown. Location uses the existing city aliases; relocation counts only when the employer explicitly permits it and the candidate agrees. Remote jobs have no city restriction unless the employer configures one.
- A mandatory rule blocks only when its blocking switch is enabled. Both unknown and unmet blocking rules stop progression. Non-blocking gaps are disclosed for recruiter review. Preferred skills are recommendations and never reject an application.
- Required questions must be answered even if their matching rule is advisory. Yes/No accepts an explicit No as an answer. Select questions support 2–20 distinct options. Automatic rules can match any accepted answer; multi-select also supports all expected answers. Free text is limited to 2,000 characters and never automatically graded. Blocking questions require both a matching rule and a required answer.
- Application outcomes are **configured requirements met**, **recruiter review needed**, **information incomplete**, **no automatic rules**, or **legacy application**. None automatically shortlists, hires or rejects a candidate. The employer controls application status.
- Final submission repeats validation on the server using the saved draft and current rules. The signed review token expires after one hour and is tied to the candidate, job, draft version and JD/rule fingerprint. Job/question changes require another check and review. Client-submitted scores or forged status fields are ignored.
- Submitted answers, candidate facts, JD/rules and assessment are recorded as snapshots. Later profile, question or JD edits do not rewrite that evidence. Only the existing permitted cover-letter/status/withdrawal actions remain editable through the application UI.
- Unsubmitted drafts and draft PDFs belong to the candidate; recruiters cannot access them. Candidates can discard drafts. Operators may inspect stale drafts without deleting them:

```powershell
.\.venv\Scripts\python.exe manage.py cleanup_application_drafts --days 30
```

To explicitly delete drafts older than that cutoff and their draft PDFs, add `--apply`. There is no automatic schedule. Submitted applications are never deleted by this command. Eligibility answers are retained with the application for review; configure an appropriate operator retention policy.

## Application rules

- A seeker can have only one application per job, enforced by the existing database uniqueness constraint. Withdrawn records remain in history and cannot be resubmitted or reopened by employers.
- Editing changes the cover letter only, while the application is pending and the job is open.
- Statuses: pending, reviewing, shortlisted, interview, accepted, rejected and withdrawn. Employers can change review statuses on their own applications; only the applicant can withdraw an eligible application.
- Submitted resumes are copied to the application so later profile updates do not silently change a submitted file. Existing legacy applications without a snapshot fall back to their profile resume.
- Resumes download as attachments through views that check account role and record ownership. There is deliberately **no public `/media/` catch-all route**. Withdrawal blocks subsequent employer resume downloads; it cannot recall a file already downloaded.
- Employer deactivation keeps job/application history. Expired jobs cannot be reactivated until their deadline is updated. The deadline remains valid through that date in `Asia/Kolkata`.
- Inactive roles are hidden from public browsing. Their employer and existing applicants can still view them. Original free-text salaries are preserved. Optional numerical annual INR bounds enable salary filters; existing free text is never guessed or automatically converted.

## Search, location and filters

- Keywords match title, responsibilities, qualifications, mandatory/preferred skills, requirements, description, company and category. All typed words (up to 12) must match. **Best match** scores title matches most strongly, then company and requirements; this is transparent keyword ranking, not an AI recommendation claim. Other sorts are newest, oldest, title and deadline.
- Location suggestions combine a bundled catalog of 15 Indian city centers with actual employer-entered locations. Includes Ludhiana, Chandigarh, Mohali, Delhi and Bengaluru, with aliases such as Bangalore and SAS Nagar. Free-text cities and states also work. Counts represent open database listings, including visibly labelled samples in development.
- Suggestions support arrow keys, Enter, Escape and touch. The bundled catalog remains available when the suggestion endpoint fails. Searching still works without JavaScript; autocomplete needs JavaScript.
- **Use my current location** requests browser permission only after a click. Precise coordinates are used in the browser to suggest the nearest supported city within 50 km, never transmitted or stored. The user checks the city and submits search. If denied, unsupported, insecure, or outside coverage, enter a location manually. HTTPS or localhost is required by browsers.
- Distance is an approximate straight-line radius from a supported city center. Explicit employer coordinates take priority; otherwise a known job city center is used. It is not a driving distance. Jobs with unknown coordinates/cities are excluded when distance is set. Exact city matching remains available.
- Choose **Remote** as location or work mode to search remote roles across cities; physical location and radius are ignored for that search. Check the employer's regional eligibility in each description.
- Salary filters compare overlapping employer-supplied **annual INR ranges**, excluding unstructured/undisclosed salaries. Both salary endpoints are required when posting numerical pay. Text remains available for other currencies/periods; no currency conversion is claimed.
- Category, experience, job type, work mode, company and posting age combine in the same database query. Invalid filters show validation errors. Nine results per page, selected-filter removal and a wide-screen role preview retain query values.
- Recent keyword/location searches are stored only in this browser's local storage (maximum four). **Clear history** removes them. No device coordinates or resumes are stored there.
- Set **Job preferences** in the seeker workspace to filter dashboard recommendations. If no roles match, the dashboard says so. Preferences do not enable email job alerts.

## Company insights, reviews and maps

Company pages retain employer information and open roles, with salary insights only from that company's open, non-sample jobs with structured INR pay. The displayed interval is the lowest advertised minimum through the highest advertised maximum, labelled with its listing count; it is not a market average or verified employee pay.

Job seekers can submit one company review per company. Ratings are 1–5 and experience text requires 50–2,000 characters. Author account names are not displayed publicly; the relationship is explicitly self-reported. All new and edited reviews are pending until a non-employer moderator with the appropriate Django admin permission publishes them. In `/admin/`, use **Company reviews → Publish selected reviews** or review the individual entry. Employers cannot moderate reviews through their company account. Pending/rejected reviews do not contribute to ratings. Authors can edit or remove their own reviews. No reviews are seeded.

Workplace maps appear only when the employer supplies valid coordinates. A **Load workplace map** button creates an OpenStreetMap iframe on demand, with attribution and a persistent location/link fallback. There is no geocoding API key, automatic external geocoder, or tile prefetching. Map availability depends on OpenStreetMap; use a suitable provider for a large public deployment and follow its usage policy. See `docs/DATA_SOURCES.md` for catalog attribution and policies.

## Environment configuration

`scripts/configure_env.py` creates a private `.env` from `.env.example` and generates a unique secret without printing it. Keep this file local. Environment variables supplied by the host take precedence over `.env`.

| Variable | Purpose / default |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required secret of at least 50 characters; generated by the setup script. |
| `DJANGO_DEBUG` | `.env.example` uses `True` for local development. Without an environment value, settings default to `False`. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames. Local defaults: `localhost,127.0.0.1,[::1]`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Optional complete HTTPS origins for deployment, separated by commas. |
| `DJANGO_DB_PATH` | Optional absolute database path; defaults to `db.sqlite3` in the project. |
| `DJANGO_MEDIA_ROOT` | Optional absolute private upload directory; defaults to project `media/`. |
| `EMAIL_BACKEND` | Console email by default; use Django's SMTP backend for real delivery. |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP server and port (587 by default). |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP credentials, stored only in your environment. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | STARTTLS or implicit TLS; never enable both. Defaults: True / False. |
| `DEFAULT_FROM_EMAIL` | Sender address; replace `JOBLYFY <noreply@localhost>` with an authorized sender for SMTP. |
| `DJANGO_TRUST_PROXY_HTTPS` | Optional; False by default. Enable only behind a trusted proxy that strips/sets X-Forwarded-Proto. See `docs/AUTHENTICATION.md`. |
| `DJANGO_SECURE_SSL_REDIRECT` | Defaults to enabled when DEBUG is False. |
| `DJANGO_SECURE_HSTS_SECONDS` | Defaults to one year when DEBUG is False, zero locally. Only use with correctly configured HTTPS. |

### Password reset email

During local development, requesting a reset prints the complete email and link in the **runserver terminal**. Open that link to finish resetting the password. Nothing is delivered to an inbox by the console backend.

For real email, configure `.env` with your provider's settings:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-provider.example
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=JOBLYFY <your-authorized-sender@example.com>
```

These are placeholders, not credentials. The reset form uses generic success messaging to avoid exposing account existence. Reset links last one hour and become invalid after use. Actual SMTP delivery has not been tested because no email-provider credentials were supplied.

## Project map

| Path | Responsibility |
| --- | --- |
| `core/settings.py` | Single active Django configuration, environment loading, SQLite and email. |
| `core/access.py`, `core/throttle.py` | Role checks and persistent basic authentication throttling. |
| `apps/accounts/` | Users, seeker/company profiles, preferences, signup/login/reset/settings and upload validation. |
| `apps/jobs/` | Jobs, categories, applications, saved jobs, moderated reviews and employer job editing. |
| `apps/jobs/job_management.py` | Owned structured job/rule editing, lifecycle actions and screening-question management. |
| `apps/jobs/screening.py`, `screening_forms.py` | Deterministic eligibility checks, typed questions, server validation and snapshots. |
| `apps/jobs/application_views.py` | Private drafts, four-step application flow, signed review and final validation. |
| `apps/jobs/search.py`, `locations.py` | Shared ORM filtering/ranking, nearby search and location normalization. |
| `apps/dashboard/` | Role dashboards, candidate review, in-app notifications, status changes and history. |
| `templates/` | Reusable Django template layouts, forms, cards, tables and error pages. |
| `static/css/joblyfy.css`, `search.css`, `screening.css`, `premium.css` | Existing responsive structure and shared premium component refinements. |
| `static/js/joblyfy.js`, `search.js`, `screening.js` | Navigation, submission feedback, accessible autocomplete, filters and opt-in maps. |
| `static/data/locations.json` | Finite offline city catalog and approximate center points. |
| `static/images/` | Local brand/icon SVGs and all original image assets. |
| `docs/legacy/` | Six unused duplicate Python fragments preserved as `.txt`, outside import paths. |
| `docs/INITIAL_AUDIT.md` | Original findings and preservation decisions. |
| `docs/SCREENING_AUDIT.md` | Pre-change screening findings and preservation decisions. |
| `docs/UPGRADE_REPORT.md` | Implemented changes, verification and remaining setup. |
| `scripts/check_project.py` | Repeatable checks from any working directory. |

## Migrations and an existing installation

All previously supplied migrations are unchanged. The first upgrade's two forward `0003` migrations add profile fields, work mode/benefits, an application resume snapshot, expanded status choices and saved jobs. The pre-existing experience field is restored to the model instead of being removed from the database. The advanced upgrade adds `accounts/0004`, `jobs/0004` and `dashboard/0001` for optional salary/coordinates, sample markers, featured roles, reviews, preferences and notifications. Salary/coordinate constraints accept all legacy rows with empty new fields. The catalog and premium interface/authentication releases require no migration and preserves all 13 migration Python files. The preceding screening upgrade adds **`jobs/0005_job_screening_workflow`**: optional JD fields, publication state, application evidence, and `EligibilityRule`, `ScreeningQuestion`, `ApplicationDraft` and `ScreeningAnswer`. Existing active jobs become published; inactive jobs become paused. Old applications keep their status/resume and carry a legacy screening label; employers can continue reviewing them as before. No old answers or rules are fabricated. No models or existing user, job or application records are deleted by the upgrade.

For your existing Windows copy: stop the server and back up its current `db.sqlite3`, `media/` and private `.env`. Extract this release to a **separate folder**. Copy your current database, uploads and environment into that new project, replacing the bundled older database with **your own newer database**. Create a fresh virtual environment there, install the requirements, run `backup_database`, then `migrate`, `createcachetable` and `seed_categories`. Keep the old folder until you have verified the upgrade. If you use `DJANGO_DB_PATH` or `DJANGO_MEDIA_ROOT`, verify that those paths point to the intended files before running commands. No new dependencies or API keys are needed. The optional trusted HTTPS proxy flag is unnecessary locally. Never run `makemigrations` just to suppress an error: supplied migrations already match the models. Never use `--fake` without investigating the database state.

To create another backup at any time:

```powershell
.\.venv\Scripts\python.exe manage.py backup_database
```

For a brand-new empty installation, point `DJANGO_DB_PATH` to a new file and run `migrate`, `createcachetable`, `seed_categories` and `seed_demo_jobs` for the practice catalog. A new empty database has no personal accounts; seeded demo recruiters start with unusable passwords. Register or create a superuser. The backup command is only applicable once the database exists.

## Verification

Current results and limits are in `docs/UPGRADE_REPORT.md`. The premium release adds authentication regressions and real browser restart/persistence checks while retaining all prior workflow tests.

From the project folder:

```powershell
.\.venv\Scripts\python.exe scripts\check_project.py
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

The automated tests run against Django's **isolated test database** and temporary uploads, not your user database. Coverage includes registration, login/logout, CSRF, unsafe redirects, legacy duplicate-email behavior, profile updates, file validation, password-reset token flow, role permissions, job search/filtering/pagination, posting/editing/deactivation, applications, uniqueness, saved jobs, status changes, withdrawal, private files and dashboard counts.

The catalog adds 17 integration tests covering all 18 application flows, every role category/location, combined search, safe reruns, credentials and referenced-record cleanup.

The screening suite adds structured-job lifecycle, ownership, typed question rules, incomplete/eligible/ineligible checks, advisory preferences, signed-token and stale-tab protections, private drafts, resume validation, frozen evidence, duplicate/expired jobs, and populated legacy migration coverage.

See `docs/UPGRADE_REPORT.md` for verified results, browser coverage and explicit limits. The advanced suite also covers alias/nearby search, salary/date filters, location suggestions, demo command safeguards, moderation, preference matching and notification ownership. The application was tested on Linux with Python 3.12; the Windows commands use standard Python/Django tooling but were not executed on a physical Windows machine.

## Deployment notes

This deliverable is ready for local development and portfolio demonstration. `runserver` is not a production web server. For an internet deployment, configure a WSGI/ASGI server, HTTPS, the real domain, email, secure backups and appropriate request limits. Serve `collectstatic` output at `/static/`; **do not publish the private `media/` directory**. Company logos are served by their explicit application route.

SQLite uses short explicit `IMMEDIATE` write transactions and a 20-second lock timeout to serialize final submissions and recruiter rule changes; it does not wrap every request in a transaction. This is not a production load-test result.

With production environment values set, run `manage.py check --deploy`. Configure trusted reverse-proxy HTTPS forwarding only for a proxy you control; the project intentionally does not trust arbitrary forwarded headers. The included database-backed throttle is basic protection for small installations, not a substitute for production gateway rate limiting. File validation checks format, size and readability; it is not an antivirus or PDF active-content scanner. Scale SQLite and the storage/deployment model according to your traffic and privacy requirements.

## Troubleshooting

- **Secret missing:** run `scripts\configure_env.py`. If you manually copied a blank `.env`, populate its `DJANGO_SECRET_KEY` securely or remove only that unused blank configuration and rerun the script. Do not replace a production secret casually.
- **No such table / cache table:** run `migrate` and `createcachetable` in the intended environment/database path.
- **Review expired or job changed:** return to eligibility, check the current requirements, continue through questions and resume selection, then open a fresh review. Submitted applications remain intact.
- **Question cannot be saved:** use unique display-order numbers, valid distinct options, and accepted answers from those options. Blocking questions must be required and have an automatic matching rule; text questions use manual review.
- **No jobs shown:** run `seed_demo_jobs --refresh-deadlines` against the intended database, or publish your own role. Paused catalog jobs need explicit `--reactivate`. Check the selected database path, active flag, employer activity and deadline, then clear filters. Sample vacancies are hidden with DEBUG=False.
- **No location suggestions:** enable JavaScript; a failed suggestion endpoint falls back to the bundled cities. Arbitrary locations remain searchable as text. Current location also needs browser permission and HTTPS/localhost.
- **Salary or radius returns no jobs:** free-text salaries cannot participate in numeric filters; unknown locations cannot participate in distance filtering. Clear those filters to broaden the search.
- **Review not visible:** it is pending moderator approval, or was edited and returned to pending.
- **Role denied:** sign in with the correct employer or seeker account. Having a staff/admin account alone does not grant an employer profile.
- **Email login ambiguous:** use the account's original unique username. Existing duplicate email addresses were deliberately preserved.
- **Styles not loading locally:** keep `DJANGO_DEBUG=True`, run through `manage.py runserver`, and refresh. All application CSS/JS/icons are local.
- **Resumes return 404:** the file may be absent, you may not own the application, or the application was withdrawn. Public media URLs are intentionally unavailable.
- **Port already in use:** run `manage.py runserver 8001` and open `http://127.0.0.1:8001/`.
