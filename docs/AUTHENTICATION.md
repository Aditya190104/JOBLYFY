# Authentication and persistent data

JOBLYFY uses Django's database sessions and password hashing. Account/profile
details, preferences, saved jobs, applications, screening answers, notifications
and recruiter jobs are database rows. Resume and logo files live under MEDIA_ROOT;
the database retains their file paths. No passwords or authentication tokens use
localStorage. Only optional recent search text uses browser storage.

## Sign-in policy

- New registrations require unused email/username values, compared without case.
  Availability is rechecked within the existing SQLite IMMEDIATE save transaction.
- Login accepts email or username. Exact legacy usernames take priority, then an
  unambiguous case-insensitive username or email. Legacy duplicate identities are
  preserved; use your exact username when an old email is shared.
- Password spaces and case are significant. The old login form stripped edge
  spaces although signup accepted them; this has been fixed and tested.
- Signup and unchecked login use browser-length cookies. **Keep me signed in**
  requests a persistent 14-day cookie. Refresh and ordinary server restarts retain
  an unexpired session. Expiry is not extended on every page view.
- Browsers with session restore may retain browser-length cookies after closing.
  Always sign out on shared devices.
- Logout requires a CSRF-protected POST. Password changes preserve the current
  session and invalidate other sessions. Reset tokens expire after one hour and
  cannot be reused.

## Preserve these across upgrades and restarts

1. Your private .env and DJANGO_SECRET_KEY.
2. Your db.sqlite3, or the file selected by DJANGO_DB_PATH.
3. Your media directory, or DJANGO_MEDIA_ROOT.

configure_env.py creates .env only if missing; it never rotates an existing secret.
Stop the server with Ctrl+C, then run the same manage.py runserver command again.
Default database/media paths are relative to the project, not the terminal's
working directory. Prefer absolute environment paths when hosting elsewhere.

For an upgrade, stop Django and back up your current database, uploads and .env.
Extract the release separately and copy those current files into it before setup.
Do not replace a newer local database with the supplied snapshot: it cannot contain
records you created later on your computer.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Signed in at one address only | Use one origin consistently. localhost and 127.0.0.1 have different cookies. |
| Local HTTP does not retain login | Use DJANGO_DEBUG=True locally. Production secure cookies require HTTPS. |
| Sessions fail after restart | Keep the same secret and database; check host-injected variables and ephemeral storage. |
| Profile or PDF is missing | Verify database/media paths point to the previous installation. |
| Specific password fails | Use its exact spaces/case or reset it. Plaintext passwords cannot be recovered. |
| Old shared email fails | Use the account's exact username. Legacy users were not merged. |
| Login changes when switching local projects | Cookies are host-scoped, not port-scoped. Other Django apps may replace sessionid; use separate browser profiles or hostnames. |
| HTTPS proxy redirects repeatedly | Configure TLS correctly and only enable the trusted-proxy option below when appropriate. |

Do not delete users, reset migrations or disable authentication to resolve login
problems. Expired session rows can be removed with python manage.py clearsessions;
this does not delete users or their records.

## HTTPS and email

DEBUG=False enables secure session/CSRF cookies, HTTPS redirects and HSTS.
Session cookies are HttpOnly and SameSite=Lax. Behind a trusted TLS proxy only:

    DJANGO_TRUST_PROXY_HTTPS=True

The proxy must strip client-supplied X-Forwarded-Proto and set it from the actual
connection. By default the application does not trust that header. Configure
ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, durable storage and static serving for your host.

Local password-reset emails appear in the runserver terminal. Real delivery needs
an SMTP provider configured in .env. The tests use isolated memory/file-email
backends; no live SMTP delivery is claimed.

No schema/dependency changes. Identity protection covers portal signup and profile
editing under SQLite IMMEDIATE transactions. Admin/import scripts must apply their
own identity policy; a global unique-email constraint was not imposed on legacy
duplicate data.

References:
- https://docs.djangoproject.com/en/5.2/topics/http/sessions/
- https://docs.djangoproject.com/en/5.2/topics/auth/default/
- https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header

