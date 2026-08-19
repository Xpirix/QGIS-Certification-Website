# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[3.1.1]: https://github.com/qgis/QGIS-Certification-Website/compare/version-3_1_0...version-3_1_1
