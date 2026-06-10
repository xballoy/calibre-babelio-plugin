---
"calibre-babelio-plugin": patch
---

Fix the ISBN in the live integration test, which pointed at the wrong book: `9782070396733` resolves to "Canisse" by Olivier Bleys, not "L'élégance du hérisson". Use the correct EAN `9782070391653` (verified against Babelio) in both the integration test and the `__main__` self-test. Add a fail-fast preflight to the integration workflow so a stale `BABELIO_COOKIE` fails the job before the live tests run.
