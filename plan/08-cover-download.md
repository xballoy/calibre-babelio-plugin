# Task 08 — Cover download

## Objective
Let Calibre fetch book covers for resolved books, using the cover URL discovered during identify.

## What must be done
- Implement `download_cover()`: use the cached cover URL for the given identifiers; if none is
  cached, run `identify()` first to populate the cache, then download.
- Account for the fact that covers may be self-hosted on Babelio (behind the same wall) or on an
  external CDN — so cover fetches may or may not need the cookie.
- Optionally strip a size suffix from CDN cover URLs to obtain full-resolution images.
- Respect the abort signal and the configured "allow covers" preference.

## Acceptance criteria
- For a book with a cached cover URL, the cover downloads and is delivered to Calibre's result
  queue.
- For a book without a cached cover URL, identify runs first and then the cover downloads.
- When covers are disabled in preferences, no cover request is made.

## Dependencies
- Task 05 (client), Task 07 (identify + cover-URL caching).

## Out of scope
- Cover-URL extraction itself (done in the parser, Task 02).

## References
- Specification §download_cover().
