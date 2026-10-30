# Premium interface and authentication audit — 28 October 2026

Starting point: JOBLYFY-jobs-ready.zip, delivered version 4. The existing accounts,
jobs and dashboard apps, server-rendered templates, SQLite database, 13 migration
files and 18 labelled sample roles remain the basis of this upgrade.

Before changes, all 134 existing tests passed. The database was copied consistently
with SQLite's backup API to `backups/db-before-premium.sqlite3`. Source hashes were
recorded separately for comparison. No account or application reset is planned.

## Findings before implementation

- Password hashing, session/authentication middleware, CSRF, private resume routes,
  role checks, database application drafts, immutable submitted answers and
  employer ownership checks already exist. These should be preserved.
- Login without Remember me uses a browser-length session; signup instead inherits
  Django's persistent-session default. Make those entry points consistent and
  explain the 14-day Remember me option.
- Signup's case-insensitive identity checks execute before the transaction that
  saves the user. Recheck while holding the existing SQLite IMMEDIATE transaction
  to prevent competing web registrations from inserting duplicate email addresses.
  Apply the same validation/save boundary to profile email edits. Preserve legacy
  duplicate emails and case-variant usernames rather than deleting or merging users.
- Username login only accepts exact case. Safely accept a case-insensitive match
  when unambiguous, keeping exact legacy usernames as the first choice.
- Normal navigation already uses database sessions. Repeated-login complaints
  cannot be attributed to a reproduced account-loss bug at audit time. Test with a
  real process restart and document stable database, media, secret and origin paths.
- Production uses secure cookies, but a TLS-terminating reverse proxy has no
  explicit opt-in HTTPS-forwarding setting. Add a documented trust flag; do not
  trust arbitrary forwarded headers by default.
- The dashboard suppresses the footer and authentication pages use a separate
  footer. Share the requested developer credit across all three layouts.
- Mobile styles reduce some controls and supporting text to 8–11px. Improve the
  type scale and touch targets across the full template system.
- Current form feedback only disables the clicked submitter; alternate submitters
  and Enter can still post a second request. Add a form-level guard while retaining
  submit action values, server validation and back/forward recovery.
- Existing search, location fallback, filter drawer, preview, notifications and
  screening editor are functional progressive enhancements. Keep their contracts.

No schema change or runtime dependency is necessary for this work. Operational
deployment, SMTP credentials and physical Windows testing remain separate checks.

A follow-up regression reproduced login rejecting a valid signup password with edge
spaces. Login now passes the password unchanged (strip=False). The final checks
were rerun after recovery of the saved checkpoint on 29 October 2026.
