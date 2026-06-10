# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release workflow reads the section matching a pushed `vX.Y.Z` tag from this file and uses it as
the GitHub Release notes.

## [Unreleased]

## [0.1.0] - 2026-06-10

### Added

- Initial release of the Babelio metadata source plugin for Calibre.
- Identify books by title/author or ISBN, or directly by a `babelio_id` identifier (kept
  byte-compatible with the unmaintained `lrpirlet/cal-babelio_db` plugin).
- Imports title, authors, ISBN, publisher, publication date, rating, series, tags, and comments;
  downloads covers.
- EN/FR user-interface translations.
- Anti-bot handling: authenticates with a browser-obtained `jstsToken` cookie, sends a configurable
  User-Agent and a French `Accept-Language`, rate-limits requests, and trips a ~23 h circuit breaker
  after repeated HTTP 403 blocks to avoid an IP ban. Surfaces a clear, translated message when the
  cookie is missing or expired.
- Configuration UI with a "Test connection" button, metadata-field toggles, request-interval and
  tag-relevance settings, and a cover toggle.
