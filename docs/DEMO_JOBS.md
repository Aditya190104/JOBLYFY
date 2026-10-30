# Using the populated career catalog

The ZIP's SQLite database already has 18 **fictional development jobs**, covering all 15 requested software/design roles, four demo companies and eight location/work regions. These are database records, not HTML fixtures. All pay and benefits are illustrative, not verified offers.

## Install or update

Follow the Windows commands in the README from the folder containing `manage.py`. When upgrading your own copy, retain its newer database, private `.env` and `media/`, and back them up first. Do not overwrite newer user data with the bundled database.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createcachetable
.\.venv\Scripts\python.exe manage.py seed_categories
.\.venv\Scripts\python.exe manage.py seed_demo_jobs --refresh-deadlines
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/. The command backs up SQLite first and requires local DEBUG=True. No new dependency, secret or external service is required. With DEBUG=False the samples are hidden and cannot receive new applications. Do not enable DEBUG on a public deployment.

## Add, edit, hide and clean up

| Command/action | Behavior |
| --- | --- |
| `seed_demo_jobs` | Creates only missing catalog entries; preserves edited jobs, questions, rules, passwords, applications and deadlines. |
| `seed_demo_jobs --refresh-deadlines` | Creates missing entries and renews existing deadlines for 60 days. Does not unpause jobs or overwrite other fields. Unfinished applications must review the changed configuration again. |
| `seed_demo_jobs --deactivate` | Pauses catalog jobs to remove them from listings; preserves all history. |
| `seed_demo_jobs --reactivate` | Publishes existing catalog jobs and renews deadlines. Does not recreate deleted entries. |
| `seed_demo_jobs --remove-unused` | Deletes only catalog jobs without applications, drafts or saved-job references. Retains all accounts/categories and referenced jobs. Pause referenced jobs instead. |
| Recruiter dashboard → Edit / Questions | Edits the recruiter's owned records. Rerunning the seed command preserves those edits. |

To add another sample, add a complete entry with a new unique slug to `apps/jobs/data/demo_jobs.json`, then seed. Do not rename an existing slug to edit a title; use the dashboard. Removed unreferenced entries are recreated by normal seeding. A manually posted demo-company job outside this catalog remains browse-only. Use an ordinary employer account for genuine vacancies.

All command mutations run inside a transaction after backup. Collisions with unrelated usernames or job identifiers abort instead of taking over records. The earlier `seed_demo` command and `joblyfy-v1:` browse-only records remain separate.

## Recruiter access

No default/shared passwords are provided. Set a private password interactively, for example:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword joblyfy_demo_stack
```

| Demo company | Username |
| --- | --- |
| Stackway Studio — Demo | `joblyfy_demo_stack` |
| Pixel Grove Design — Demo | `joblyfy_demo_pixel` |
| Cloudfield Labs — Demo | `joblyfy_demo_cloud` |
| Routecraft Digital — Demo | `joblyfy_demo_route` |

Sign in with that username and the password you chose. Each recruiter can manage only its own jobs and applications. The accounts start with unusable passwords. Original account credentials are unchanged.

## Practice applications

Register a seeker, open a sample, and choose **Check eligibility & apply**. Enter the facts requested by its saved rules, answer four required questions, select a valid PDF and review before submitting. Use a synthetic PDF without personal or confidential information. The receipt and recruiter dashboard label the saved result as a practice application; no real employer receives it.

The first Yes/No question explicitly confirms the fictional nature of the vacancy. Other questions cover availability, relevant tools and a role-specific short response. Missing/unmet blocking requirements stop progression. Preferred skills remain advisory. Remote roles have no city rule; on-site/hybrid roles accept their stated location or declared relocation. Degree names use the explicit alternatives shown, not an inferred equivalence. All checks and final submission run on the Django backend.

## Data conventions

- Each job has its own description, tasks, qualifications, skills, experience bounds, benefits and questions. The catalog includes fresher, junior, experienced and internship roles; full-time, part-time, contract and internship types; on-site, hybrid and remote arrangements.
- Locations: Mohali, Chandigarh, Ludhiana, Delhi NCR, Bengaluru, Hyderabad, Pune and Remote — India.
- Full-time/part-time/contract bounds are illustrative annual INR. Three internships display ₹8,000–₹18,000/month across their respective bands. Filters use 12 times the monthly stipend as an annualized comparison, not guaranteed annual pay. When editing internship pay, keep numeric bounds consistent with that convention.
- Creation timestamps are real seeding timestamps; no past posting history is fabricated. New deadlines are 60 days after command execution.
- There is no openings-count model field. No invented office coordinates are stored. Delhi NCR uses the existing Delhi alias/approximate center for optional distance searches; it does not claim an exact NCR workplace.
- Demo companies cannot receive fabricated reviews. Their sample salary bands do not contribute to company salary insights.

See `DEMO_CATALOG.md` for the complete record list and `UPGRADE_REPORT.md` for executed checks and limits.
