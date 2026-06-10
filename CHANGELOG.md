# calibre-babelio-plugin

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
