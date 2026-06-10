# Task 01 — Project scaffolding & tooling

## Objective
Establish the repository layout, dev environment, and quality-gate configuration so every
later task has a place to put code and a way to lint/type-check/test it.

## What must be done
- Create the source package directory that becomes the ZIP root (flat layout Calibre expects),
  including the empty `plugin-import-name-babelio.txt` marker that establishes the
  `calibre_plugins.babelio` import namespace.
- Create the `tests/` layout (fixtures already exist) and the `scripts/` and
  `.github/workflows/` directories as placeholders for later tasks.
- Set up a `uv`-managed Python project targeting Python ≥ 3.12 **for development only**.
- Pin **exact** versions of dev dependencies needed to lint, type-check, and run the parser
  unit tests locally without Calibre installed (test runner, linter, type checker, and the
  HTML-parsing libraries the parser uses so fixtures parse the same way locally and inside
  Calibre). Look up the latest stable version of each before pinning.
- Configure the linter, type checker, and test runner via project config.
- Provide a mechanism (type stubs and/or a test-config shim) so the type checker and test
  runner ignore or stub out Calibre/Qt-dependent modules and still succeed on a machine with
  no Calibre installed.

## Acceptance criteria
- A fresh checkout can run the lint, type-check, and unit-test commands through `uv` without
  Calibre present (they may report "no code yet" but must not error on missing Calibre).
- The package directory exists with the import-name marker file present and empty.
- All dev dependencies are pinned to exact versions.

## Out of scope
- Any plugin/parser logic (later tasks).

## References
- Specification §Architecture (directory tree), §"uv & tooling".
