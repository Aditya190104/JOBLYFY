# Motion and interaction system

The existing Django templates, local SVG icons and navy/violet/lavender tokens
remain the application. No runtime dependency, build step or CDN was added.

## Shared components

- `motion.css` defines timing, easing, hover/focus states, menu/drawer transitions,
  chart appearance, action notices and reduced-motion rules.
- `motion.js` manages one-time Intersection Observer reveals and Web Animations.
  It covers cards, headings, panels, forms, empty states, notifications and footers.
  Nested fields do not move independently of their form.
- `page-transitions.css` progressively enables native transitions on anonymous
  public GET pages. Private/account pages use local entrances. Navigation is never
  delayed or replaced by a client router.
- Existing joblyfy.js, search.js and screening.js retain their controls and forms.

Small interactions take 140–240ms; surface entrances take 380ms. Sibling stagger
is capped at 140ms. Chart bars animate for 480ms. The hero's atmospheric introduction
finishes within 4.32 seconds. There are no perpetual decorative loops, fake
count-up statistics, parallax listeners or layout animation loops.

Content is never hidden awaiting JavaScript. Missing animation APIs leave normal
content visible. Focus and pointer activity cancel surface movement around active
controls. Reduced-motion preferences disable CSS motion, smooth scrolling and
JavaScript effects, including when the preference changes during use. Background
tabs and history restoration cancel active animations.

## Search, navigation and forms

Normal GET searches keep existing results visible and use actual submit-button
feedback. Location suggestions appear immediately from the local catalog; a small
indicator runs only while live counts are requested. A five-second timeout keeps
offline suggestions available without inventing counts.

Mobile menus and the filter drawer use progressive display/opacity/transform
transitions. Hidden controls are inert. The drawer isolates all background
siblings, traps Tab, supports Escape and restores focus on closure and resizing.
Unsupported browsers open and close these controls normally.

Job description section links are genuine anchors; requirements remain visible.
Application steps remain separate server-validated pages. File-selection feedback
describes the chosen filename/size and says validation/upload happen on submission.
It never claims that an unsubmitted file has been accepted.

## Saved jobs

The existing CSRF-protected save URL accepts explicit save/remove intent and
returns JSON only when requested. Each action is atomic and idempotent. Existing
HTML forms and legacy toggles still work.

Result cards and job details update only after server confirmation. Pending guards
prevent duplicate requests for the same job. Network uncertainty leaves the last
confirmed state and offers refresh/retry; retrying the same intent cannot undo a
save. Closed jobs, invalid CSRF and login redirects display real error feedback.
No authentication data is written to browser storage and no action is queued offline.
Saved-job management retains server pagination and ordinary removal forms.

## Application charts

One aggregate query counts all records owned by the candidate or recruiter. All
seven statuses are represented, with an Other / legacy row for older unknown
values. Recent-five limits do not affect totals. Each application appears once at
its current status; this is not a historical funnel or hiring-success estimate.

Counts and percentages are ordinary readable text. Decorative SVG bars use the
same values and are hidden from assistive technology. Standard status labels link
to existing filtered application pages. No applications produces an honest empty
state. Practice applications count only if actual records exist.

Platform references:
https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@view-transition
https://developer.mozilla.org/en-US/docs/Web/API/Element/animate

See MOTION_UPGRADE_REPORT.md for test evidence and limitations.
