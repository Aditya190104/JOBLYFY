# JOBLYFY design system

The existing Django templates and routes remain the application. No frontend
framework, external font, runtime CDN or build step has been added.

| Token | Value | Use |
| --- | --- | --- |
| --navy | #11152B | Hero, workspace navigation, footer |
| --purple | #5B43F5 | Primary actions, links, active states |
| --lavender | #B8A7FF | Brand accents |
| --surface | #FFFFFF | Forms and cards |
| --canvas | #F7F8FC | Page background |
| --ink | #18213A | Main text |
| --muted | #667085 | Supporting text |
| --success | #16865B | Success palette |
| --warning | #B7791F | Warning palette |

Darker companion status colors preserve readable contrast on tinted backgrounds.
System fonts avoid network requests and use Segoe UI on Windows when available.

joblyfy.css retains the original structure; search.css and screening.css retain
their specialized components. premium.css refines the shared typography, spacing,
surfaces, focus states and responsive layouts across all three.

The hero uses actual featured database jobs and labels samples. Developer credit is
shared by the public footer and compact account/workspace footers. The LinkedIn
link includes a new-tab accessible label and noopener/noreferrer.

Card entrances never leave content hidden waiting for JavaScript. Reduced motion
disables transitions/animations and cancels the reveal observer. Live location
requests have a bounded loading indicator; normal GET search keeps current results
visible while the submit button is busy. The form-level duplicate guard preserves
the chosen action before disabling buttons and restores them on browser history
navigation. Backend uniqueness and permission checks remain authoritative.

Password visibility uses native controls and aria-pressed. Existing location
keyboard navigation, offline suggestions, filter drawer, private file access and
server-rendered form workflows remain intact. Tables scroll inside their container
on narrow screens without forcing horizontal page overflow.

See UPGRADE_REPORT.md for tested viewports, browser journeys, accessibility results
and explicit verification limits.

motion.css and motion.js extend the shared components with finite hero atmosphere,
consistent timing, menu/drawer transitions, save confirmation and chart entrances.
MOTION_SYSTEM.md documents their progressive fallbacks and accessibility behavior.

