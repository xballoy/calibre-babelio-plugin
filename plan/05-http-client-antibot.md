# Task 05 — HTTP client & anti-bot layer

## Objective
Provide the network layer that authenticates against Babelio's JS-challenge wall, rate-limits
requests, detects blocks, and protects against IP bans.

## What must be done
- Build the HTTP layer on top of Calibre's browser (`self.browser` / mechanize). It must:
  - Set the required request headers (French `Accept-Language` and the configured `User-Agent`).
  - Inject the `jstsToken` cookie scoped **host-only** to `www.babelio.com` over HTTPS only — not
    broadened to the parent domain.
  - Expose the two request shapes the plugin needs: GET a book page by its id/URL, and POST the
    search endpoint with the search terms. (The full-résumé AJAX follow-up POST is also part of
    this layer.)
  - Return raw bytes (so the parser can decode as Latin-1) plus enough context to detect blocks.
- **Rate limit**: enforce a configurable minimum interval between requests (default ≥ ~1.2 s)
  using Calibre's rate-limiting facility.
- **Challenge/block detection**: treat HTTP 403 (or a body/redirect indicating the JS-challenge
  interstitial) as "token invalid/expired" and raise a typed, distinguishable error the upper
  layers can turn into a user-facing message.
- **Circuit breaker**: on repeated blocks, persist a lock (temp dir) and refuse outbound calls
  for ~23 h to avoid triggering an IP ban; recover automatically once the window elapses.
- Provide a single-shot "test connection" capability the config UI can call to report whether
  the current cookie/UA combination works.

## Acceptance criteria
- A valid cookie yields HTTP 200 bytes for both book-page and search requests.
- A missing/garbled cookie raises the typed block error (not a generic exception).
- Repeated blocks engage the circuit breaker, which then refuses calls for the cooldown window
  instead of continuing to hit Babelio.
- The configured minimum interval is observed between consecutive requests.

## Dependencies
- Task 01 (package exists).

## Out of scope
- Parsing responses (Task 02) and building `Metadata` (Task 06).
- Reading preference values from disk — accept cookie/UA/interval as inputs (config wiring is Task 07/09).

## References
- Specification §"Anti-bot layer (client.py)".
