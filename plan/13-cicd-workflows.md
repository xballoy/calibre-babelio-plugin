# Task 13 — CI/CD workflows

## Objective
Automate quality gates on every change, allow manual live verification, and publish releases.

## What must be done
- **Continuous integration** (on push / pull request): set up the dev environment via `uv`, run
  the linter, type checker, and the parser unit tests, build the plugin ZIP, and upload it as a
  build artifact. Must succeed with no Calibre installed.
- **Live integration** (manual dispatch, taking a fresh cookie + optional User-Agent as inputs):
  install Calibre, stage/customize the plugin, inject the supplied credentials into the plugin
  preferences, and run the live self-test against Babelio. Fail on no results or on a block.
- **Release** (on a version tag): build the ZIP and publish a GitHub Release with the ZIP asset
  and changelog notes.

## Acceptance criteria
- Opening a PR runs the CI workflow green (lint + type-check + unit tests + build).
- The integration workflow can be triggered manually with a fresh cookie and goes green against
  live Babelio.
- Pushing a version tag publishes a release with the ZIP attached.
- No secrets (cookie/UA) are hard-coded; they come from workflow inputs/secrets.

## Dependencies
- Task 03 (unit tests), Task 11 (build), Task 12 (integration test).

## Out of scope
- The plugin logic itself.

## References
- Specification §CI/CD, Verification step 7.
