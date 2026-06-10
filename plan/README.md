# Implementation Plan — Calibre Babelio Metadata Plugin

This folder breaks the [specification](../docs/specification.md) into discrete tasks.
Each task describes **what** must be delivered and how it will be judged "done" — not
**how** to build it. Tasks are written to be picked up independently; the
**Depends on** field names only hard prerequisites (a task that literally cannot be
verified without another's output).

## Task index

| # | Task | Depends on |
|---|------|-----------|
| 01 | [Project scaffolding & tooling](01-project-scaffolding.md) | — |
| 02 | [Pure parser module & domain types](02-parser-module.md) | 01 |
| 03 | [Parser unit tests on fixtures](03-parser-unit-tests.md) | 02 |
| 04 | [Query normalization](04-query-normalization.md) | 02 |
| 05 | [HTTP client & anti-bot layer](05-http-client-antibot.md) | 01 |
| 06 | [Per-book fetch worker](06-worker.md) | 02, 05 |
| 07 | [Plugin entry point & Source class](07-plugin-entry.md) | 02, 04, 05, 06 |
| 08 | [Cover download](08-cover-download.md) | 05, 07 |
| 09 | [Configuration UI & preferences](09-config-ui.md) | 05 |
| 10 | [Internationalization (EN/FR)](10-i18n-translations.md) | 07, 09 |
| 11 | [Build script & packaging](11-build-packaging.md) | 01, 10 |
| 12 | [Live integration test harness](12-integration-tests.md) | 07, 11 |
| 13 | [CI/CD workflows](13-cicd-workflows.md) | 03, 11, 12 |
| 14 | [Project documentation & license](14-docs-license.md) | 01 |

## Suggested execution order (sequential)

Work the tasks in numeric order — **01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14**.
The numbering is already a valid dependency order: every task's prerequisites have a lower number,
so you never reach a task whose dependencies are unfinished.

1. **01 Scaffolding** — nothing can be built or tested until the layout and quality gates exist.
2. **02 Parser** then **03 Parser tests** — get the calibre-free core correct and locked against
   the fixtures first; this is the fastest path to a green signal and the tightest feedback loop.
3. **04 Query normalization** — the other pure, calibre-free piece; finish all non-Calibre logic
   before touching the network/Qt layers.
4. **05 Client** → **06 Worker** → **07 Plugin entry** — build the Calibre-dependent stack bottom-up
   so each layer sits on a finished one; 07 is where it all converges into a loadable plugin.
5. **08 Cover download** — extends the now-working identify/cover-cache path.
6. **09 Config UI** — needs the client's test-connection capability (05) in place.
7. **10 i18n** — done after 07 and 09 so the full set of user-visible strings exists to translate.
8. **11 Build/packaging** — needs the translation catalogs (10) to compile into the ZIP.
9. **12 Integration tests** — needs a loadable plugin (07) and an installable ZIP (11) to exercise.
10. **13 CI/CD** — wires up the gates that depend on unit tests (03), build (11), and integration (12).
11. **14 Docs & license** — can technically start right after 01, but is placed last so the README
    documents the finished, verified behavior rather than a moving target.

## Conventions every task must honor

- **Runtime code uses only Calibre-bundled libraries** (`self.browser`/mechanize, `lxml`,
  `html5lib`, `css_selectors`, `bs4`, stdlib). No installable runtime dependencies. `uv` and
  its dev dependencies are for development/CI only.
- **Calibre-free isolation**: `parser.py` (and any query-normalization helper it owns) must
  not import `calibre` or `qt`. Everything that touches Calibre/Qt is confined to
  `__init__.py`, `config.py`, `client.py`, `worker.py`.
- **Qt imports** go through Calibre's shim: `from qt.core import ...`.
- **Backward compatibility**: the `babelio_id` identifier format must stay byte-compatible
  with the reference plugin so existing libraries keep resolving.
- **Selectors are already validated** — see [`docs/selector-validation.md`](../docs/selector-validation.md)
  and the saved HTML in `tests/fixtures/`. Treat that document as the source of truth for
  field extraction.
- **License is MIT.**
