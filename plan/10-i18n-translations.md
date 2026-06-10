# Task 10 — Internationalization (EN/FR)

## Objective
Ship English and French UI translations so the plugin's labels and messages switch with
Calibre's language, via gettext only.

## What must be done
- Ensure all user-visible strings across the plugin (config UI labels/help, error messages such
  as the cookie-expired notice, test-connection feedback) are marked for translation.
- Produce the translation template and the English and French catalogs covering every marked
  string.
- Ensure the runtime loads the compiled catalogs so the active language resolves correctly.
- Scope is **UI translation only** — no per-book language detection; books default their
  `languages` to French to match Babelio's French metadata.

## Acceptance criteria
- Launching Calibre under a French locale shows French labels; under English shows English.
- Every user-visible string has an entry in both catalogs (no untranslated leakage in FR).
- Compiled catalogs are produced by the build (see Task 11) and loaded at runtime.

## Dependencies
- Task 07 (runtime strings/messages), Task 09 (config UI strings).

## Out of scope
- Build-time compilation mechanics live in Task 11; this task owns the source strings and catalogs.

## References
- Specification §Decisions ("Multilingual = UI translations EN + FR"), §Plugin behavior
  (`load_translations()`), Verification step 6.
