# Task 09 — Configuration UI & preferences

## Objective
Give the user a settings panel to paste the anti-bot credentials, choose which metadata fields
to import, tune behavior, and verify connectivity — persisted across sessions.

## What must be done
- Build a custom Qt configuration widget (Qt imported via Calibre's shim) backed by persistent
  plugin preferences, laid out to match the reference plugin's screenshot.
- **Anti-bot group**: a `jstsToken` value field with inline help explaining where to copy it
  from (DevTools → Application → Cookies → www.babelio.com → jstsToken) and that it lasts about
  three weeks; an optional User-Agent field; a **"Test connection"** button that performs one
  live fetch and reports success/failure with a reason; and a minimum request-interval control.
- **Metadata fields**: toggles for comments, published date, publisher, rating, series, tags.
- Additional options mirrored from the reference: verbosity level, allow-covers, extended
  comment, detailed rating (dependent on extended), and per-category tag relevance levels
  (genre / thème / lieu / quand, with sensible defaults).
- Persist all settings on save; validate on save and warn if the cookie/UA are missing.
- All user-visible labels must be wrapped for translation.

## Acceptance criteria
- Settings persist across Calibre restarts.
- The "Test connection" button reports a clear ✅/❌ with a reason, driven by the client's
  single-shot test capability.
- Saving with a missing cookie/UA surfaces a warning rather than silently saving.
- Every label is translatable (verified once Task 10 ships the catalogs).

## Dependencies
- Task 05 (client's test-connection capability).

## Out of scope
- The translation catalogs themselves (Task 10) — this task only wraps strings for translation.

## References
- Specification §"Configuration UI (config.py)".
