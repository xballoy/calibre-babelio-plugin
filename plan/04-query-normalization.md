# Task 04 — Query normalization

## Objective
Build the search-query builder that makes Babelio actually return the target book. The
validation work proved raw accented queries return garbage; normalization is mandatory.

## What must be done
- Provide a pure, calibre-free helper that turns the available book metadata into the search
  term string to send to Babelio.
- Encode the empirically validated rules:
  - If a valid ISBN/EAN is known, search it directly (yields a single exact result).
  - Otherwise build terms from title + author(s), then: remove diacritics, strip
    apostrophes/punctuation, drop leading articles and very short stop tokens, lowercase, and
    join with spaces.
- Keep this logic unit-testable without network or Calibre (it may live in the parser module or
  a sibling calibre-free module).

## Acceptance criteria
- Given the validation doc's example inputs, the builder produces the deburred form that was
  shown to surface the target at rank 0 (e.g. the hérisson example).
- ISBN input is passed through unchanged as the query.
- Covered by unit tests with no network and no Calibre.

## Dependencies
- Task 02 (shares the calibre-free module boundary / types).

## Out of scope
- Sending the request and ranking results (Tasks 05/07).

## References
- `docs/selector-validation.md` Finding 2.
- Specification §identify() step 3.
