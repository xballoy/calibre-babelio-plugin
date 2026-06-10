# Task 02 — Pure parser module & domain types

## Objective
Provide a **calibre-free** module of pure functions that turn raw Babelio HTML into typed
data structures. This is the testability cornerstone of the project.

## What must be done
- Define typed data structures (dataclasses) for a search hit and for a parsed book.
- Implement a function that parses a search-results page into a list of search hits.
  - It must handle **both** result layouts: the canonical keyword/title/ISBN result rows and
    the author-name mosaic layout, with the documented fallback between them.
  - It must avoid the noise sources called out in the validation doc (cover-thumbnail links,
    "popular books" widgets).
  - Empty results from **both** layouts must be reported as zero hits.
- Implement a function that parses a single book page into the book data structure, extracting
  every field listed in the validation doc with its documented gotchas, including at least:
  title (with trailing author/site suffix stripped), authors (whitespace-collapsed, editorial
  roles such as translator/editor/illustrator/preface filtered out), ISBN/EAN, publisher,
  publication date (rejecting the unknown-date sentinel), rating (French decimal comma handled,
  rescaled from /5 to /10), series and series index, cover URL, résumé/summary, and tags with
  their category and relevance level.
- Decode pages using their actual encoding (Latin-1 / iso-8859-1), accepting raw bytes from the
  caller and decoding correctly so accented characters are preserved.
- The module must not import `calibre` or `qt`, and must be importable on any machine.

## Acceptance criteria
- All public functions are pure (input HTML/bytes → typed output), with no network or global state.
- Importable and runnable without Calibre.
- Behavior is fully verified by Task 03's tests against the saved fixtures.

## Out of scope
- Query building (Task 04), network fetching (Task 05), `Metadata` construction (Task 06).
- The full-résumé AJAX follow-up call (a network concern; this module only parses what it's given).

## References
- `docs/selector-validation.md` (authoritative selectors & gotchas).
- Specification §Parsing.
