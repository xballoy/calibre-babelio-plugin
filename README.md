# Babelio metadata plugin for Calibre

A [Calibre](https://calibre-ebook.com/) metadata source plugin that fetches book metadata and
covers from [Babelio](https://www.babelio.com/), the French book community site. It imports title,
authors, ISBN, publisher, publication date, rating, series, tags, and comments, and downloads
covers. The UI is available in English and French.

It stores a `babelio_id` identifier in the same format as the older, unmaintained
[`lrpirlet/cal-babelio_db`](https://github.com/lrpirlet/cal-babelio_db) plugin, so libraries already
populated by that plugin keep working.

## How it works: the `jstsToken` cookie

Babelio gates access behind a JavaScript-challenge cookie: headless requests get **HTTP 403** unless
they carry a valid, browser-obtained **`jstsToken`** cookie. The plugin therefore cannot work until
you paste a fresh token into its settings. There is no way around this; the token is the single
thing that unlocks access.

### Where to get the token

1. Open https://www.babelio.com/ in your browser and make sure you are not blocked.
2. Open the developer tools (F12) → **Application** (Chrome/Edge) or **Storage** (Firefox) →
   **Cookies** → `https://www.babelio.com`.
3. Copy the **value** of the cookie named **`jstsToken`**.

The cookie is `HttpOnly`, so it is **not** readable from the JavaScript console; you must copy it
from the Cookies panel. It is also `Secure` (HTTPS only) and host-only to `www.babelio.com`.

### Lifetime and expiry

A pasted token is usable for **about three weeks** (≈ 21 days), though Babelio may invalidate it
sooner after an IP change or abuse. When it expires, identify returns a translated message,
*"Babelio cookie is missing or expired: paste a fresh jstsToken in the plugin settings"*, and the
plugin stops calling Babelio. Just copy a fresh token from your browser and paste it again.

## Requirements

- Calibre 6.0 or newer.

## Install

- **From a release:** download `babelio.zip` from the
  [Releases](../../releases) page, then in Calibre go to *Preferences → Plugins → Load plugin from
  file* and select the ZIP.
- **From source (development):** `calibre-customize -b src/calibre_babelio/`.

After installing, open *Preferences → Metadata download* and make sure **Babelio** is enabled.

## Configuration

Open *Preferences → Metadata download → Babelio → Configure*:

- **jstsToken**: the cookie value described above (required).
- **User-Agent**: optional; defaults to a recent Chrome string. Kept as a safety lever in case
  Babelio later binds the token to a User-Agent.
- **Min request interval**: seconds between requests (default 1.2). Keep this reasonable.
- **Test connection**: does one live request and reports whether the token is valid.
- **Metadata to import**: toggles for comments, publication date, publisher, rating, series, tags.
- **Max results**, **Allow covers**, **Verbosity**.
- **Tag relevance thresholds**: minimum Babelio relevance for genre / theme / place / period tags.

## Responsible use

Babelio reserves text-and-data-mining rights on its content. Use this plugin for your own personal
library, not for bulk harvesting:

- Keep the request interval at **1.2 s or higher**.
- Keep **Max results** low.
- The plugin trips a **~23 h circuit breaker** after repeated HTTP 403 blocks and refuses further
  requests during that window, to avoid getting your IP banned.

## Development

This repository is a development/CI project; the runtime plugin uses only Calibre-bundled libraries.
[`uv`](https://docs.astral.sh/uv/) manages the dev environment.

```sh
uv sync                              # set up the dev environment
uv run ruff check                    # lint
uv run mypy                          # type-check
uv run pytest                        # unit tests (no network, no Calibre)
uv run python scripts/build.py       # build dist/babelio.zip
```

The live integration test is opt-in and gated on a real cookie:

```sh
BABELIO_COOKIE=<fresh token> uv run pytest tests/test_integration.py --no-cov
```

`--no-cov` is required because the coverage gate measures only the pure parser/query modules, which
the network-driven test does not cover on its own. You can optionally set `BABELIO_UA` to override
the User-Agent.

The same suite can be run in CI via the **Live integration** workflow (manual `workflow_dispatch`
only). It reads the `jstsToken` from a `BABELIO_COOKIE` **repository secret** (*Settings → Secrets
and variables → Actions*), never from a workflow input, so the token is never exposed in the public
Actions UI. Refresh the secret when the token expires (~3 weeks). The optional `user_agent` input
overrides the User-Agent for the run.

## License

[MIT](LICENSE.md) © 2026 Xavier Balloy.
