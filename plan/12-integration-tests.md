# Task 12 — Live integration test harness

## Objective
Provide an opt-in test that exercises the full plugin against live Babelio using a fresh
cookie, including the expiry/circuit-breaker path.

## What must be done
- Add an integration test that is **gated on environment** (a cookie value and optional
  User-Agent supplied via env vars) and **skipped** when those are unset, so the default test
  run never hits the network.
- When credentials are present, the test must drive a real identify against known books and
  assert the resolved metadata matches expectations (title/author/series for a known id, and an
  ISBN lookup).
- Cover the **expiry path**: with a missing/garbled cookie, the plugin returns the translated
  "token missing/expired" message and the circuit breaker engages rather than hammering Babelio.

## Acceptance criteria
- With no env credentials, the integration test is skipped and the default test command passes.
- With valid credentials, the live identify assertions pass against the known books.
- The expiry scenario produces the translated message and trips the circuit breaker.

## Dependencies
- Task 07 (identify + self-test), Task 11 (a staged/installable plugin to exercise).

## Out of scope
- The CI workflow that triggers this (Task 13).

## References
- Specification §Architecture (test_integration.py), Verification steps 4–5.
