# Advanced upgrade audit — 26 October 2026

Starting point: the previous enhanced JOBLYFY archive, compared byte-for-byte with this working source before edits. Existing Django apps, templates, route names, authentication and migration history remain the foundation. The original code audit is in INITIAL_AUDIT.md.

## Findings before editing

- SQLite contains 6 users, 2 employer profiles, 4 seeker profiles and **zero jobs, applications or saves**. The public queryset correctly selects active, unexpired jobs from active employers. No database jobs were being hidden by a broken template; there were none to show.
- Home, search, companies and categories already use database querysets. The homepage's `featured_jobs` is actually a slice of newest jobs; there is no editorial feature flag.
- Location is a substring-only filter. There is no autocomplete endpoint, keyboard interaction, city alias normalization, offline catalog or current-location control. Permissions-Policy currently blocks geolocation entirely.
- Search matches a complete phrase in four fields; no token relevance scoring. Filters lack posting age and structured salary ranges. Original salary values are free text; they must not be guessed or silently converted.
- Results have a long sidebar form, no mobile drawer, no removable filter chips or details preview. Pagination and saved jobs already work.
- Company profiles exist, but have no user reviews, moderation or salary-data summaries. Seeker preferences and in-app notifications are absent.
- Existing application ownership, POST/CSRF protections, private PDF snapshots, hashed passwords, authentication throttling and complete reset templates must be retained. All 49 prior regression tests remain relevant.
- The existing local design system, responsive dashboard, local SVG assets and core.settings configuration are suitable foundations. No framework or build-tool conversion is needed.

## Preservation

A consistent SQLite backup was made at `backups/db-before-advanced.sqlite3` before model or data changes. Original backup is retained. Existing migration files were hashed before changes; only new forward migrations may be added. Existing account, profile, password and job records must not be rewritten for demonstration purposes.

## Implementation approach

Extend existing models with optional structured data; consolidate querying in a search module; add a small attributed offline city catalog and accessible suggestions; enhance the existing templates and CSS. Keep external maps opt-in and all basic search functional without paid services. Demo records require an explicit development-only management command and visible Sample labels. Real ratings and salary summaries use only eligible database content. Verify both an empty preserved database and an isolated seeded development database.
