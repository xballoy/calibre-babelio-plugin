# Task 07 — Plugin entry point & Source class

## Objective
Implement the `Source` subclass that Calibre loads — its declared capabilities, the
identifier round-trip, the `identify()` orchestration, and a runnable self-test block.

## What must be done
- Define the `Babelio(Source)` class with the required class attributes: name (distinct from the
  old "Babelio_db" so both can coexist), description, author, version, minimum Calibre version,
  capabilities (identify + cover), touched fields, HTML-comments / gzip flags, and translation
  loading at module import so `_()` resolves against the shipped catalogs.
- Implement the **backward-compatible identifier** round-trip:
  - `get_book_url(identifiers)` → returns the `babelio_id` key, value, and full Babelio URL.
  - `id_from_url(url)` → parses a Babelio book URL back into the `babelio_id` key/value.
  - The stored value format must be byte-compatible with the reference plugin.
- Implement `identify()` orchestration:
  - Read preferences (cookie, UA, options).
  - If a `babelio_id` is already on the book, fetch that page directly.
  - Otherwise build the normalized query (Task 04), POST the search, parse hits, cap at the
    configurable top-N, and dispatch workers for the hits — respecting abort and rate limit.
  - Queue each resulting `Metadata`, run Calibre's downloaded-metadata cleanup, and let Calibre
    re-rank (do not trust Babelio ordering for correctness).
  - Return `None` on success or a translated error string on an anti-bot block / expired cookie.
- Provide a `__main__` self-test block invoking Calibre's `test_identify_plugin` against known
  books (a known `babelio_id` and an ISBN lookup) so the integration workflow can execute it.

## Acceptance criteria
- The identifier round-trip is lossless and matches the reference format exactly.
- With a valid cookie, `identify()` queues correct results for both a direct-id book and a
  search-based lookup; with an invalid cookie it returns the translated expiry message.
- The `__main__` block runs under `calibre-debug` and exercises the self-test.

## Dependencies
- Task 02 (parser), Task 04 (query), Task 05 (client), Task 06 (worker).

## Out of scope
- Cover download (Task 08), config persistence/UI (Task 09).

## References
- Specification §"Babelio(Source) class attributes", §Identifier, §identify() flow.
