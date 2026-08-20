# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.2] - 2026-08-20

### Security

- **Markdown no longer renders the author's own HTML.** `base_markdown`
  passed `safe_mode=True`, which Python-Markdown removed in 3.0 and ignores
  silently, so unsanitised HTML was passed to `mark_safe()`. Checklist
  answers are free text submitted by anyone applying for a certifying
  organisation and are rendered through this filter on the page a reviewer
  opens, so an applicant could run script in the reviewer's session. Input is
  now escaped before rendering, and generated link and image targets are
  restricted to `http`, `https`, `mailto`, `ftp` and relative URLs.

- **Attendee create, update and CSV upload now require organisation rights.**
  All three carried only a login requirement and acted on the organisation
  named in the URL without checking the requester. `AttendeeUpdateView` also
  had no queryset scoping, so `get_object()` selected from every attendee in
  the system by a sequential primary key — the whole attendee table could be
  walked and rewritten. Both attendee forms exposed `certifying_organisation`
  as a hidden field, which is not a server-side constraint, so a POST could
  move an attendee between organisations; the field is gone and the value now
  comes from the URL.

- **Certificate issuing now requires organisation rights.**
  `CertificateCreateView` required only a login, and each success minted a
  genuine, publicly verifiable certificate while spending the organisation's
  purchased credits.

- **The bulk certificate download now requires organisation rights.**
  `download_certificates_zip` had no check at all. Organisation and course
  slugs appear on public pages, so the full attendee roster of every course
  on the site could be harvested.

- **Credit prices are decided by the server.** `CreateCheckoutSessionView`
  took the unit price and total from the query string, so the buyer set their
  own price, and never checked that the buyer was connected to the
  organisation being credited. The price now comes from `project.credit_cost`.

### Fixed

- CSV attendee upload returned a 500 when no file was chosen, when the file
  had fewer than three columns, and on any invalid submission
  (`form_invalid_message` was never set). Uploads are now capped at 1000 rows.
- The attendee revocability check ran on GET only, so a direct POST could
  still rename the attendee on an issued certificate.
- `base_markdown` emitted a malformed `<table` opening tag.

## [3.1.1] - 2026-08-19

### Security

- **Profile update no longer accepts another user's primary key.**
  `UserUpdateView` selected from every user and checked ownership in
  `get_context_data()`, which Django does not call on a successful POST. Any
  authenticated user could rewrite another account's email address and then
  take it over through a password reset. The queryset is now scoped to the
  requesting user, so the check applies to every HTTP method.

- **Certificate paid-status endpoint now requires authentication and
  organisation membership.** `update_paid_status` had no permission check of
  any kind. Its POST branch marks certificates paid and spends the
  organisation's purchased credits, and its GET branch served the confirmation
  form — and a usable CSRF token — to anonymous callers, so credits could be
  drained in a loop. The view now requires login, requires rights over the
  organisation, resolves the course and attendee within that organisation
  rather than by identifier alone, and refuses to let the balance go negative.

[3.1.2]: https://github.com/qgis/QGIS-Certification-Website/compare/version-3_1_1...version-3_1_2
[3.1.1]: https://github.com/qgis/QGIS-Certification-Website/compare/version-3_1_0...version-3_1_1
