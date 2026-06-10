# Task 06 — Per-book fetch worker

## Objective
Bridge the parser and the client: for a single search hit (or known id), fetch the book page,
parse it, and build a Calibre `Metadata` object ready to be queued.

## What must be done
- Provide a worker that, given a target (a search hit or a known `babelio_id`) and the client,
  fetches the book page, parses it, and constructs a `Metadata` object.
- Map every parsed field onto the corresponding `Metadata` field and identifiers, honoring the
  plugin's configured metadata-field toggles (comments, published date, publisher, rating,
  series, tags, etc.).
- Set the `babelio_id` and (when present) `isbn` identifiers; record the Babelio result order as
  the source relevance; cache the cover URL against the identifiers for later cover download.
- Run the work in a way that cooperates with Calibre's threading and abort signal, and respects
  the rate limit between requests.
- When a résumé is truncated, optionally retrieve the full text via the AJAX follow-up exposed by
  the client.

## Acceptance criteria
- Given a fixture-equivalent book page (via the client), the worker produces a `Metadata` object
  with the expected fields populated and identifiers set.
- Disabled metadata-field toggles result in those fields being left unset.
- The worker stops promptly when the abort signal is set.

## Dependencies
- Task 02 (parser), Task 05 (client).

## Out of scope
- Orchestrating multiple workers / search flow (Task 07).

## References
- Specification §identify() step 4.
