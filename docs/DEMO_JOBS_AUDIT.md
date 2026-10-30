# Catalog integration audit — 28 October 2026

Before editing, the current Job/Category/Employer and screening models, seed commands, search/location logic, forms, application endpoints, templates and dashboard permissions were reviewed.

- The database had six original users, eight categories and zero jobs/applications. Missing listings resulted from absent database records.
- All required JD, experience, salary, lifecycle and screening relationships already existed. No replacement models or migration were needed. The model has no openings-count field, so no count was invented.
- The older `seed_demo` command creates basic mixed-industry browse-only samples in a separate namespace. It is retained unchanged for compatibility.
- Both backend application endpoints and the templates disabled every sample. The new career namespace now supports explicit local practice applications using the existing ownership, eligibility, duplicate, deadline, CSRF, private PDF and review-token checks.
- Production queries hide samples; company reviews and salary insights exclude fictional data. Those protections remain.
- Salary bounds represent annual INR. Catalog internships display an illustrative monthly stipend derived from the annualized bounds; details explain the filter basis.
- City/state text, aliases and work mode feed the actual ORM search. Delhi NCR and work-from-home matching were added without a geocoder or fabricated workplace coordinates.
- Homepage real-posting counters were zero despite sample cards. A separate visible-listing total now shows the number of samples while preserving real employer counts.

The database was backed up before insertion. Writes are transactional and use stable unique demo keys. Existing user passwords, job edits, applications, categories and previous migrations are retained. Optional deletion removes only unreferenced catalog jobs and retains accounts/categories.
