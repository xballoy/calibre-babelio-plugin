# calibre-babelio-plugin

## 0.2.0

### Minor Changes

- [#56](https://github.com/xballoy/calibre-babelio-plugin/pull/56) [`32f11f3`](https://github.com/xballoy/calibre-babelio-plugin/commit/32f11f341a46e262a0aa0a8d8078122d7e97893b) Thanks [@xballoy](https://github.com/xballoy)! - Restore search and metadata import after Babelio's site redesign ([#55](https://github.com/xballoy/calibre-babelio-plugin/issues/55)), which left every search empty even though "Test connection" succeeded.
  
  - Book details now come from the page's structured data (schema.org JSON-LD), which is less likely to break on the next restyle. Series still comes from the page's details table.
  - Searching for an author's name alone now follows that author's bibliography and returns their 20 most-read books.
  - **Tags** are now the book's genres as Babelio lists them (usually one or two, e.g. "science-fiction"). Babelio no longer publishes tag categories or relevance scores, so the "Tag relevance thresholds" setting has been removed.
  - **Publisher** is now the publisher alone ("Albin Michel") instead of publisher and imprint ("Albin Michel / Wiz").
  - Two error messages about a missing or rejected cookie are now translated into French.

## 0.1.1

### Patch Changes

- [#7](https://github.com/xballoy/calibre-babelio-plugin/pull/7) [`2626d88`](https://github.com/xballoy/calibre-babelio-plugin/commit/2626d888c8baa5daaedde98ccc0a61ca9ab8c3dc) Thanks [@xballoy](https://github.com/xballoy)! - Fix the ISBN in the live integration test, which pointed at the wrong book: `9782070396733` resolves to "Canisse" by Olivier Bleys, not "L'élégance du hérisson". Use the correct EAN `9782070391653` (verified against Babelio) in both the integration test and the `__main__` self-test. Add a fail-fast preflight to the integration workflow so a stale `BABELIO_COOKIE` fails the job before the live tests run.

- [#7](https://github.com/xballoy/calibre-babelio-plugin/pull/7) [`2626d88`](https://github.com/xballoy/calibre-babelio-plugin/commit/2626d888c8baa5daaedde98ccc0a61ca9ab8c3dc) Thanks [@xballoy](https://github.com/xballoy)! - Refresh `uv.lock` when syncing the release version. `sync-version.mjs` bumped `pyproject.toml` and `__init__.py` but left the lockfile pinned to the previous project version, so release PRs shipped a stale `uv.lock` that the next `uv` invocation silently rewrote.

## 0.1.0

### Minor Changes

- [#1](https://github.com/xballoy/calibre-babelio-plugin/pull/1) [`bae5bcf`](https://github.com/xballoy/calibre-babelio-plugin/commit/bae5bcf79625c5ef0d55ed4340931e9c216c0369) Thanks [@xballoy](https://github.com/xballoy)! - Initial release of the Babelio metadata source plugin for Calibre.

  - Identify books by title/author or ISBN, or directly by a `babelio_id` identifier (kept byte-compatible with the unmaintained `lrpirlet/cal-babelio_db` plugin).
  - Imports title, authors, ISBN, publisher, publication date, rating, series, tags, and comments; downloads covers.
  - EN/FR user-interface translations.
  - Anti-bot handling: authenticates with a browser-obtained `jstsToken` cookie, sends a configurable User-Agent and a French `Accept-Language`, rate-limits requests, and trips a ~23 h circuit breaker after repeated HTTP 403 blocks to avoid an IP ban. Surfaces a clear, translated message when the cookie is missing or expired.
  - Configuration UI with a "Test connection" button, metadata-field toggles, request-interval and tag-relevance settings, and a cover toggle.

### Patch Changes

- [#3](https://github.com/xballoy/calibre-babelio-plugin/pull/3) [`5995cf1`](https://github.com/xballoy/calibre-babelio-plugin/commit/5995cf138baf7e7bb89eb5455a3bac956030842e) Thanks [@xballoy](https://github.com/xballoy)! - Add Renovate configuration extending the shared `xballoy/renovate-config` preset to automate dependency, lockfile, and GitHub Actions updates. Python version updates (`.python-version` and `requires-python`) are disabled because the plugin must track the Python interpreter bundled with Calibre.

- [#4](https://github.com/xballoy/calibre-babelio-plugin/pull/4) [`4991498`](https://github.com/xballoy/calibre-babelio-plugin/commit/49914987ea8e025c19fdd132e4a0378b04214798) Thanks [@xballoy](https://github.com/xballoy)! - Use a GitHub App token in the release workflow so the changesets "Version Packages" PR triggers CI and can satisfy the required `build-and-test` status check before merging.
