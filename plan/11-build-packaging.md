# Task 11 — Build script & packaging

## Objective
Produce the installable Calibre plugin ZIP with the flat layout Calibre expects, including
compiled translation catalogs.

## What must be done
- Provide a build script that:
  - Compiles `fr.po` into its binary `fr.mo`. **Skip `en.po`**: English is the source language —
    its catalog has empty `msgstr` entries and resolves via gettext fallback to the source `msgid`,
    so no `en.mo` is shipped.
  - **Fails loudly** if `fr.po` has any untranslated (empty `msgstr`) or fuzzy entries — the build
    must error out and produce no ZIP, so a regression in translation coverage cannot ship silently.
  - Stages the source package contents **flat** (the package contents become the ZIP root),
    including the empty import-name marker file and the compiled catalog(s).
  - Emits a single distributable ZIP into a `dist/` output directory.
- The script must run via `uv` in development and in CI with no Calibre present.

## Compilation tooling: use Babel, not system `msgfmt`
- Compile with **Babel's Python API in-process**, not the gettext `msgfmt` binary. Babel
  (`babel==2.18.0`) is already a pinned dev dependency used for extraction, so `uv sync` provides
  it on every platform — no `apt-get install gettext` in CI, no `brew install gettext` for
  contributors. Reproducible and identical across Linux/macOS/Windows runners.
- Use `read_po` / `write_mo` directly so the output path is explicit:
  ```python
  from babel.messages.pofile import read_po
  from babel.messages.mofile import write_mo

  with open(po_path, "rb") as f:
      catalog = read_po(f, locale="fr")
  untranslated = [m.id for m in catalog if m.id and (not m.string or m.fuzzy)]
  if untranslated:
      raise SystemExit(f"fr.po has {len(untranslated)} untranslated/fuzzy entries; aborting build")
  with open(mo_path, "wb") as f:
      write_mo(f, catalog)
  ```
- **Layout gotcha:** Calibre loads a **flat** `translations/fr.mo` (not gettext's
  `<locale>/LC_MESSAGES/<domain>.mo`). The `read_po`/`write_mo` API above writes to exactly the
  path given, so it sidesteps `pybabel compile`'s default directory convention. (If the CLI is used
  instead, pass explicit `-i`/`-o`/`-l`.)

## Acceptance criteria
- Running the build produces `dist/babelio.zip` containing a top-level `__init__.py`, the empty
  `plugin-import-name-babelio.txt` marker, and the compiled `translations/fr.mo` catalog (no
  `en.mo`).
- The build errors out (non-zero exit, no ZIP) when `fr.po` contains any untranslated or fuzzy
  entry.
- The build runs under `uv` with no gettext system binary and no Calibre present.
- The resulting ZIP installs into a real Calibre via its plugin-install/customize flow.

## Dependencies
- Task 01 (layout & tooling), Task 10 (catalogs to compile).

## Out of scope
- CI wiring (Task 13).

## References
- Specification §"uv & tooling" (scripts/build.py), Verification step 2.
