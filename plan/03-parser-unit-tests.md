# Task 03 — Parser unit tests on fixtures

## Objective
Prove the pure parser extracts the correct fields from every saved Babelio HTML fixture, with
no network and no Calibre, so the parser is locked against regressions.

## What must be done
- Add unit tests that load the existing fixtures in `tests/fixtures/` and assert the parser
  returns the expected values. Cover at minimum:
  - **Search results**: ISBN search (single exact hit), title search (multiple hits), combined
    author+title search, author-name search (mosaic layout), and the no-results page (zero hits).
  - **Book pages**: a book **with** a series and series index, a book **without** a series, and
    the richly-tagged book that exercises all four tag categories and an editorial-role author
    that must be filtered out.
- Assert the documented edge cases explicitly: French decimal comma in ratings and the /5→/10
  rescale; the unknown-date sentinel leaving the publication date unset; whitespace-collapsed
  author names; ISBN extracted as a bare 13-digit number; tag category and relevance-level
  classification.
- Tests must run with no network access and without Calibre installed.

## Acceptance criteria
- The unit-test command passes on a machine with no Calibre.
- Each fixture is asserted against concrete expected values (not just "parses without error").

## Dependencies
- Task 02 (parser module to test).

## Out of scope
- Live integration tests (Task 12).

## References
- `docs/selector-validation.md` (fixture table & expected fields).
