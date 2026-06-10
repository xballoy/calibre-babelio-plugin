# Task 11 — Build script & packaging

## Objective
Produce the installable Calibre plugin ZIP with the flat layout Calibre expects, including
compiled translation catalogs.

## What must be done
- Provide a build script that:
  - Compiles each translation source catalog into its binary form.
  - Stages the source package contents **flat** (the package contents become the ZIP root),
    including the empty import-name marker file and the compiled catalogs.
  - Emits a single distributable ZIP into a `dist/` output directory.
- The script must run via `uv` in development and in CI with no Calibre present.

## Acceptance criteria
- Running the build produces `dist/babelio.zip` containing a top-level `__init__.py`, the empty
  `plugin-import-name-babelio.txt` marker, and the compiled `.mo` catalogs at the expected paths.
- The resulting ZIP installs into a real Calibre via its plugin-install/customize flow.

## Dependencies
- Task 01 (layout & tooling), Task 10 (catalogs to compile).

## Out of scope
- CI wiring (Task 13).

## References
- Specification §"uv & tooling" (scripts/build.py), Verification step 2.
