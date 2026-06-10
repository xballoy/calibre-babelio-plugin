# Calibre Babelio Metadata Plugin — Specification

## Context

Calibre's metadata-download feature lets plugins fetch book metadata + covers from external
sources. The only Babelio source plugin (`lrpirlet/cal-babelio_db`, GPL-3.0) is effectively
unmaintained and breaks repeatedly because **Babelio now gates access behind a JS-challenge
cookie**: headless requests get **HTTP 403** unless they carry a valid, browser-obtained
**`jstsToken`** cookie. Confirmed properties of that cookie (from live DevTools inspection):
- name **`jstsToken`**, **`HttpOnly`** (must be copied from DevTools → Application → Cookies — *not* readable via the JS console), **`Secure`** (HTTPS only), **`HostOnly`** to `www.babelio.com`, `Path=/`.
- lifetime **≈ 21 days** (e.g. created 2026-06-09, expires 2026-06-30) — so it is *not* minutes-short; a pasted token is usable for weeks, though Babelio may invalidate it earlier on IP change or abuse.
A matching `User-Agent` is still configurable (kept as a safety lever in case Babelio later binds the token to UA), but the **`jstsToken` value is the single thing that unlocks access**.

We are building a **fresh** plugin (no code copied from the reference — only architecture studied).
Goals: a clean, well-typed, tested, CI-built plugin that (1) ships EN/FR UI translations,
(2) is configurable like the reference, (3) requires the user to paste a cookie + User-Agent to
bypass the anti-bot wall, with graceful errors when it expires, and (4) stores a `babelio_id`
identifier **byte-compatible with the old plugin** so existing libraries keep working.

### Decisions locked with the user
- **Multilingual** = UI translations (EN + FR) via gettext only. (No per-book language detection requested; default book `languages` to `fr`, which matches Babelio's French metadata.)
- **Anti-bot input** = a `jstsToken` value field **+** an optional `User-Agent` field, with a "Test connection" button. (Old wording said "paste full Cookie header"; narrowed now that we know the exact cookie.)
- **Config scope** = mirror the reference's useful options + add cookie/UA + rate-limit.
- **CI tests** = unit tests on fixtures every push/PR; live integration via **manual `workflow_dispatch`** that takes a fresh cookie+UA as input. Release on tag.
- **License** = **MIT** (we wrote everything fresh — not bound by the reference's GPL-3.0).

### Key constraints (verified during research)
- Calibre ships **its own Python 3.12** — you **cannot install runtime deps**. The plugin may only use Calibre-bundled libs: `self.browser` (mechanize), `lxml`, `html5lib`, `css_selectors`, `bs4`, stdlib. **`uv` is dev/CI tooling only** (pytest/ruff/mypy/build), never a runtime dependency.
- `Source` base class: `calibre.ebooks.metadata.sources.base.Source`; results are `calibre.ebooks.metadata.book.base.Metadata` objects put on `result_queue` in `identify()`.
- Qt imports must use Calibre's shim: `from qt.core import ...` (Calibre ≥ 6).

---

## Architecture

**Separation-of-concerns is the core testability decision:** all HTML parsing lives in a
**calibre-free** module (`parser.py`) of pure functions over `str` → typed dataclasses, so unit
tests import it directly without Calibre. Everything that imports `calibre`/`qt` is confined to
`__init__.py`, `config.py`, `client.py`, `worker.py` and exercised only by live integration tests.

```
calibre-babelio-plugin/
├── pyproject.toml            # uv project: dev deps + tool config (ruff, mypy, pytest)
├── uv.lock
├── README.md  LICENSE  CHANGELOG.md
├── src/calibre_babelio/      # contents become the ZIP root (flat layout calibre expects)
│   ├── __init__.py           # Babelio(Source); load_translations(); identify/download_cover; get_book_url/id_from_url; __main__ test block
│   ├── plugin-import-name-babelio.txt   # EMPTY file → import namespace calibre_plugins.babelio
│   ├── config.py             # Qt config widget + JSONConfig('plugins/babelio') prefs + "Test cookie" button
│   ├── client.py             # HTTP layer: builds self.browser, injects cookie+UA, rate-limit, 403/challenge detection, 23h circuit-breaker
│   ├── worker.py             # threaded per-book fetch → calls parser, builds Metadata
│   ├── parser.py             # PURE, calibre-free: parse_search_results(html)->list[SearchHit]; parse_book_page(html)->BabelioBook
│   └── translations/         # babelio.pot, fr.po, fr.mo, en.po/en.mo (compiled at build)
├── tests/
│   ├── fixtures/             # saved Babelio HTML: search result page, book pages (w/ series, w/ rating, truncated résumé)
│   ├── test_parser.py        # unit, NO network, NO calibre — runs anywhere
│   └── test_integration.py   # gated on env BABELIO_COOKIE/BABELIO_UA; skipped if unset
├── scripts/build.py          # compile .po→.mo (msgfmt), copy src→staging, zip → dist/babelio.zip
└── .github/workflows/
    ├── ci.yml                # push/PR: ruff + mypy + pytest(unit) + build zip (artifact)
    ├── integration.yml       # workflow_dispatch (inputs: cookie, user_agent): install calibre, inject prefs, run live identify
    └── release.yml           # on tag v*: build zip + create GitHub Release w/ asset
```

---

## Plugin behavior

### `Babelio(Source)` class attributes (`__init__.py`)
- `name = 'Babelio'` (distinct from old "Babelio_db" so both can coexist), `description`, `author`, `version`, `minimum_calibre_version = (6, 0, 0)`.
- `capabilities = frozenset({'identify', 'cover'})`.
- `touched_fields = frozenset({'title','authors','identifier:babelio_id','identifier:isbn','comments','rating','publisher','pubdate','series','series_index','tags','languages'})`.
- `has_html_comments = True`, `supports_gzip_transfer_encoding = True`.
- Call `load_translations()` at module top so `_()` resolves against shipped `.mo`.

### Identifier — backward compatible
- Key: **`babelio_id`**; value: the URL path after `https://www.babelio.com/livres/`, e.g. `Chattam-Autre-Monde-tome-5--Oz/401283` (slug + `/` + numeric id). Verbatim format from the old plugin.
- `get_book_url(identifiers)` → `('babelio_id', val, 'https://www.babelio.com/livres/' + val)`.
- `id_from_url(url)` → parse the same shape back to `('babelio_id', val)`.

### `identify()` flow
1. Read prefs (cookie, UA, options) via `config.prefs`.
2. If `babelio_id` already on the book → fetch that book page directly (cheap, exact).
3. Else POST `https://www.babelio.com/recherche` with `Recherche=<terms>`. **Query building is critical** (see `selector-validation.md` Finding 2): prefer ISBN if known (single exact result); otherwise **deburr accents, strip apostrophes/punctuation, drop leading articles, lowercase** the title+author terms — raw accented queries return garbage. Parse via `parse_search_results()`: iterate `.cr_meta` blocks (title `.titre1`, author `.libelle`); fall back to `ul.livres_mozaique li.item` for author-name matches. Cap at top *N* (configurable, default ~5) to limit ban risk.
4. For each hit (respecting `abort.is_set()` and rate limit): fetch book page → `parse_book_page()` → build `Metadata`, set identifiers, `mi.source_relevance = i`, cache cover URL via `self.cache_identifier_to_cover_url`, `self.clean_downloaded_metadata(mi)`, `result_queue.put(mi)`. Do not trust Babelio's ordering — Calibre re-ranks by comparing metadata to the query.
5. Return `None` on success, or a translated error string (e.g. "Babelio cookie expired — paste a fresh one in plugin settings") on anti-bot block.

### Anti-bot layer (`client.py`)
- Build `br = self.browser`; set `Accept-Language: fr-FR,fr;q=0.9` and the configured `User-Agent`. Inject the `jstsToken` cookie via `br.set_simple_cookie('jstsToken', value, 'www.babelio.com')` — host-only, and only sent over HTTPS (Secure). Do **not** broaden to `.babelio.com`.
- **Rate limit**: enforce a configurable min interval (default ≥ 1.2 s) between requests using Calibre's `rate_limit()` context manager.
- **Challenge detection**: treat HTTP 403 (or a body/redirect indicating the JS-challenge interstitial) as "token invalid/expired". Raise a typed `BabelioBlocked` error → surfaced to the user as a clear, translated message: "Babelio `jstsToken` is missing or expired — copy a fresh one from your browser (DevTools → Application → Cookies → www.babelio.com → jstsToken) into plugin settings."
- **Circuit breaker**: on repeated blocks, write a lockfile (temp dir) and refuse outbound calls for ~23 h to avoid IP bans (learned from reference; reimplemented cleanly).

### `download_cover()`
- Use `get_cached_cover_url(identifiers)`; if empty, run `identify()` to populate the cache, then fetch. Covers are usually on `m.media-amazon.com` (outside Babelio's wall), so they often download even without the cookie. Optional `_SXxxx_` size-suffix stripping for full-res.

### Parsing (`parser.py`, pure) — **selectors validated live 2026-06-09**, see `selector-validation.md`
Pages are **iso-8859-1** — parse with `from_encoding='iso-8859-1'`. Key corrections vs. the reference:
- Search: iterate `.cr_meta` → `.titre1` (title+href) + `.libelle` (author); fallback `ul.livres_mozaique li.item` + `.titre_compact` for author matches. Don't sweep bare `a[href^="/livres/"]` (catches "popular" widgets).
- Book page: title `head>title` (strip ` - <author> - Babelio`); authors `.livre_con a[href^="/auteur/"]` using `get_text(' ')` (spans concatenate; page-wide `[itemprop=author]` also matches reviewers — avoid); ISBN = **first bare `\d{13}`** in `.livre_refs.grey_light` (the `EAN :` prefix is gone); pubdate `dd/mm/YYYY` in same block but **reject `/-1` sentinel** (unknown); rating `[itemprop="ratingValue"]` first non-empty, **`,`→`.`**, **×2** (Babelio is /5, Calibre is /10); series `a[href^="/serie/"]` (optional — absent on standalones), series_index from `tome\s+(\d+)` in title; cover `link[rel="image_src"]` (often babelio-hosted `/couv/`, may need cookie); résumé `.livre_resume` (+ `voir_plus_a(...)` → `aj_voir_plus_a.php`); tags `.tags a` where class `tag_tNN`=relevance level and `tc_N`=category (only `tc_0` seen so far — 1–3 mapping unconfirmed).

### Configuration UI (`config.py`)
Custom `QWidget` (matches the reference screenshot layout) persisting to `JSONConfig('plugins/babelio')`:
- **Anti-bot group**: `jstsToken` value field (with inline help: where to copy it from in DevTools, and that it lasts ~3 weeks), optional User-Agent field, **"Test connection"** button (does one live fetch, shows ✅/❌ + reason), min request-interval spinbox.
- **Metadata fields** checkbox row: Comments, Published date, Publisher, Rating, Series, Tags.
- Verbosity (0–15), Allow covers (bool), Extended comment (bool), Detailed rating (bool, depends on extended).
- Tag relevance levels (number spinboxes): genre / thème / lieu / quand (defaults 12).
- All labels wrapped in `_()` for EN/FR. `save_settings()` writes prefs; `validate()` warns if cookie/UA missing.

---

## uv & tooling

- `pyproject.toml`: `requires-python = ">=3.12"` for the dev env; **dev deps pinned to exact versions** (`pytest`, `ruff`, `mypy`, `beautifulsoup4`, `lxml`, `html5lib` so unit tests can parse fixtures locally). Look up latest stable with `uv pip` / `npm view`-equivalent before pinning.
- Provide Calibre type stubs or a thin `conftest.py` that skips calibre-dependent modules so `mypy`/`pytest` run without Calibre installed.
- `uv run pytest tests/test_parser.py`, `uv run ruff check`, `uv run mypy src/calibre_babelio/parser.py` are the local quality gates.
- `scripts/build.py`: `msgfmt` each `.po`→`.mo`, stage `src/calibre_babelio/*` flat, emit `dist/babelio.zip`.

## CI/CD (`.github/workflows/`)

- **ci.yml** (push/PR): `astral-sh/setup-uv`, `uv sync`, ruff + mypy + `pytest tests/test_parser.py`, run `scripts/build.py`, upload `babelio.zip` artifact.
- **integration.yml** (`workflow_dispatch` with `jsts_token` + optional `user_agent` inputs): install Calibre (official installer), `calibre-customize -b` the staged plugin, inject inputs into `plugins/babelio.json`, run `calibre-debug -e src/calibre_babelio/__init__.py` which executes the `__main__` `test_identify_plugin([...])` block against live Babelio. Fail on no results / block.
- **release.yml** (tag `v*`): build zip, `gh release create` with the zip asset + CHANGELOG notes.

---

## Verification (end-to-end)

1. **Local unit**: `uv run pytest tests/test_parser.py` — parser extracts correct fields from each saved fixture (title/author/isbn/pubdate/rating/series/tags/cover). No network, no Calibre.
2. **Build**: `uv run python scripts/build.py` → `dist/babelio.zip` exists with flat `__init__.py` + `plugin-import-name-babelio.txt` + `.mo` files.
3. **Install in real Calibre**: `calibre-customize -b src/calibre_babelio/` (local Calibre at `/opt/homebrew/bin`). Open *Preferences → Metadata download → Babelio → Configure*; confirm the UI matches the screenshot and the **Test connection** button reports cookie validity.
4. **Live identify**: with a fresh `jstsToken` (+ optional UA), run `calibre-debug -e src/calibre_babelio/__init__.py` → `test_identify_plugin` passes `title_test`/`authors_test`/`series_test` on known books (e.g. the `Chattam-Autre-Monde-tome-5--Oz/401283` id and an ISBN lookup).
5. **Expiry path**: clear/garble the `jstsToken` → identify returns the translated "token missing/expired" message and the circuit-breaker engages instead of hammering Babelio.
6. **i18n**: launch Calibre with `LANG=fr_FR` and `LANG=en_US`; confirm config labels switch.
7. **CI**: open a PR → ci.yml green (lint+unit+build); manually run integration.yml with a fresh cookie → live test green; push a tag → release.yml publishes the zip.

## Open follow-ups (non-blocking)
- Selectors validated live (see `selector-validation.md`). Remaining gaps: confirm tag categories `tc_1/2/3` (need a multi-category fixture), re-verify the `aj_voir_plus_a.php` full-résumé call, and decide multi-edition preference.
