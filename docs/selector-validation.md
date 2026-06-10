# Babelio selector validation (live, 2026-06-09)

Validated against **real pages** fetched with a working `jstsToken` cookie (HTTP 200). HTML
fixtures saved under `tests/fixtures/` and used by `tests/test_parser.py`. This document records
what actually works on the current site — it supersedes the reference plugin's selectors, several
of which are now **wrong**.

## How fixtures were captured

```
GET  https://www.babelio.com/livres/<slug>/<id>          → book page
POST https://www.babelio.com/recherche  (body: Recherche=<terms>)  → search results
```
Headers used: `User-Agent: <modern Chrome UA>`, `Accept-Language: fr-FR,fr;q=0.9`,
`Cookie: jstsToken=<value>`. Without the cookie every request is **HTTP 403**.

| Fixture | Source |
|---|---|
| `book_chattam.html` | book **with** series — `/livres/Chattam-Autre-Monde-tome-5--Oz/401283` |
| `book_herisson_noseries.html` | book **without** series — `/livres/Barbery-Lelegance-du-herisson/2852` |
| `search_by_isbn.html` | `Recherche=9782226244338` (ISBN) → 1 result |
| `search_by_title.html` | `Recherche=L'élégance du hérisson` (title) → 10 results |
| `search_by_both.html` | `Recherche=Barbery élégance hérisson` (author+title) → 10 results |
| `search_by_author.html` | `Recherche=Maxime Chattam` (author) → mosaic layout |
| `search_no_results.html` | nonsense query → 0 results |
| `book_montecristo_richtags.html` | richly-tagged classic — `/livres/Dumas-Le-Comte-de-Monte-Cristo/1424592` (all 4 tag categories; editorial-role author) |
| `serie_autre_monde.html` | series page — `/serie/Autre-Monde/30` (17 books) |
| `ajax_resume_voirplus.html` | response of `POST /aj_voir_plus_a.php` (full résumé) |

---

## ⚠️ Finding 1 — Page encoding is `iso-8859-1`

Pages declare `charset=iso-8859-1` (Latin-1), **not** UTF-8. Parse with
`BeautifulSoup(raw_bytes, 'html.parser', from_encoding='iso-8859-1')` (or decode Latin-1 first).
Decoding as UTF-8 mangles every accented character. Calibre's `self.browser` returns bytes; pass
them with the explicit encoding.

## ⚠️ Finding 2 — Search is accent/punctuation-sensitive → **query normalization is mandatory**

This is the single most important result and explains why the reference plugin deburred queries.

| Query sent | Top result | Verdict |
|---|---|---|
| `Barbery élégance hérisson` | *À la croisée des mondes* (Pullman) | ❌ target absent from top 10 |
| `Barbery élégance hérisson` + `item_recherche=livres` | Pullman (identical) | ❌ no effect |
| `L'élégance du hérisson` | Harry Potter #1, target ~#5 | ⚠️ buried |
| **`elegance herisson barbery`** (deburred, no article, lowercase) | ***L'élégance du hérisson* at rank 0** | ✅ exact |
| `9782226244338` (ISBN) | exact single result | ✅ best |

**Rule for the plugin's query builder** (mirrors the reference's `get_udc()` approach, now justified empirically):
1. If a valid ISBN/EAN is known → search it directly (single, exact result).
2. Else build terms from title + authors, then: **deburr accents** (e.g. `é→e`), **strip apostrophes/punctuation**, **drop leading articles / very short tokens** (`le`, `la`, `les`, `l'`, `du`, `de`…), **lowercase**, join with spaces.
3. Rely on Calibre's own result re-ranking (it compares returned metadata to the query) — set `mi.source_relevance` to the Babelio order but do not trust Babelio's ranking for correctness.

## ⚠️ Finding 3 — Two different search result layouts

- **Keyword/title/ISBN search → `.cr_meta` blocks** (this is the canonical result row).
  Per block: title+href `= .cr_meta .titre1` (`<a href="/livres/<slug>/<id>">`); author `= .cr_meta .libelle`.
  (Each block contains *two* `/livres/` links — cover thumbnail in `.cr_gauche` + the `.titre1`; iterate `.cr_meta`, don't collect raw `a[href^="/livres/"]`.)
- **Exact author-name search → `ul.livres_mozaique li.item`** (author's bibliography mosaic).
  Per item: link `a[href^="/livres/"]`, title `.titre_compact`. No `.cr_meta`, no `.libelle`.

Plugin should: parse `.cr_meta` if present; else fall back to `ul.livres_mozaique li.item`.
**Do not** use a bare `a[href^="/livres/"]` / `.titre1` sweep — it also matches "popular books" widgets and pollutes results.

---

## Book page selectors (verified on both fixtures)

| Field | Selector / method | Notes & gotchas |
|---|---|---|
| **babelio_id** | from the request URL path after `/livres/` | e.g. `Chattam-Autre-Monde-tome-5--Oz/401283`; stored verbatim (back-compat) |
| **Title** | `head>title` text, strip trailing ` - <Author> - Babelio` | e.g. `Autre-Monde, tome 5 : Oz - Maxime Chattam - Babelio` |
| **Author(s)** | `.livre_con a[href^="/auteur/"]` → `(href, name)` | href yields author id (`/auteur/Maxime-Chattam/2038`). ⚠️ **name spans concatenate without whitespace** (`MurielBarbery`) — use `get_text(' ', strip=True)` and collapse spaces. Do **not** use page-wide `[itemprop="author"]` — it also matches *reviewers*. ⚠️ **filter editorial roles**: lists include entries like `Claude Schopp (Éditeur scientifique)` — drop names with a parenthetical role (`Éditeur scientifique`, `Traducteur`, `Illustrateur`, `Préfacier`…). |
| **Editions block** | `.livre_refs.grey_light` | One block per edition. Sample text: `9782226244338 400 pages 02/11/2012 Albin Michel / Wiz`. |
| **ISBN/EAN** | first `\d{13}` token inside `.livre_refs.grey_light` | ⚠️ The old `EAN :` prefix is **gone** — it's now a bare 13-digit number. The reference's `EAN[: ]` regex returns `None`. |
| **Publisher** | `.livre_refs.grey_light a[href^="/editeur"]` (or trailing text after the date) | Multiple editions → multiple publishers; `Voir plus` is noise to filter. Sample: `Albin Michel / Wiz`. |
| **Publication date** | `\d{2}/\d{2}/\d{4}` inside `.livre_refs.grey_light`, `strptime("%d/%m/%Y")` | ⚠️ **Sentinel `30/11/-1` = unknown date** (`book_herisson_noseries.html`). Reject year `<= 0` / the `/-1` form → leave `pubdate` unset. |
| **Rating** | `[itemprop="ratingValue"]` (first), count `[itemprop="ratingCount"]` | ⚠️ **French decimal comma** (`4,21`, `3,77`) → replace `,`→`.`. Scale is **/5** → multiply by 2 for Calibre's 0–10. ⚠️ multiple empty `ratingValue` nodes exist; take the first non-empty. |
| **Series** | `a[href^="/serie/"]` → `/serie/<slug>/<id>` | Present on Chattam (`/serie/Autre-Monde/30`), **absent** on hérisson → series handling must be optional. |
| **Series index** | regex `tome\s+(\d+)` on the title | `Autre-Monde, tome 5 : Oz` → `5`. Cheaper than fetching the series page. Fallback: the series page (`serie_autre_monde.html`) lists the 17 books in order if the title lacks a tome number. |
| **Editions** | `.livre_refs.grey_light` | ✅ Pages expose a **single primary edition block** (even Monte-Cristo) — take it directly; no multi-edition disambiguation needed. |
| **Cover** | `link[rel="image_src"]` (== `meta[property="og:image"]`) | ⚠️ Both samples are **self-hosted** `https://www.babelio.com/couv/...jpg` (not Amazon). So cover download may also need the cookie. Some books still use `m.media-amazon.com`. |
| **Summary/résumé** | `.livre_resume` | Truncated ones expose `onclick="javascript:voir_plus_a('#d_bio',1,918135)"` → ✅ **verified live**: `POST /aj_voir_plus_a.php` with `type=1&id_obj=918135` returns the full résumé HTML (with `<br>`, iso-8859-1). Send `X-Requested-With: XMLHttpRequest` + a `Referer`. The 3 args of `voir_plus_a('#sel', type, id_obj)` map to `type`/`id_obj`. |
| **Tags** | `.tags a` | Each `<a>` has classes like `['tag_t18','tc_0','tc_noreco00','tc_noaff00','tc_bold']`. **`tag_tNN`** = relevance/font-size level (bigger NN = more votes); **`tc_N`** = category; tag href is `/livres-/<slug>/<id>`. |

### Tag categories — ✅ confirmed (`book_montecristo_richtags.html`)
The `tc_N` class encodes the colored category, matching the reference's mapping:

| Class | Category | Live examples (Monte-Cristo) |
|---|---|---|
| `tc_0` | **genre** | aventure, roman, littérature, historique, classique, roman historique |
| `tc_1` | **thème** | vengeance, trahison, adapté au cinéma, prisons, amour |
| `tc_2` | **lieu** | france, littérature française, marseille |
| `tc_3` | **période (quand)** | 19ème siècle |

Relevance is the `tag_tNN` font-size class (e.g. `tag_t17` < `tag_t22`). To honor the configurable
"N relevance levels per category", group a category's tags by their `tNN` value (descending) and keep
the top N distinct levels.

### No-results detection — ✅ confirmed
A query with no matches returns **0 `.cr_meta` and 0 `ul.livres_mozaique li.item`** (generic page
title, no explicit "aucun résultat" string). Treat *both selectors empty* as zero results.

---

## Other notes

- **TDM opt-out**: every page carries `<meta name="tdm-reservation" content="1">` — Babelio asserts a
  text-and-data-mining reservation. Worth a line in the README about responsible use + rate limiting.
- **Cost/ban tradeoff**: a keyword search yields up to 10 `.cr_meta` results; fetching all 10 book
  pages = 10 requests. Recommend fetching only the top *N* (configurable, default ~5) after Calibre-side
  relevance pruning, with the ≥1.2 s rate limit, to limit ban risk.
- **Cookie longevity confirmed in practice**: the same `jstsToken` served all ~12 requests in this
  session without re-challenge.

## Open items — ✅ all resolved
1. ~~Tag category mapping~~ → confirmed `tc_0/1/2/3` = genre/thème/lieu/quand.
2. ~~`aj_voir_plus_a.php`~~ → verified live, returns full résumé.
3. ~~Multi-edition pages~~ → only a single primary `.livre_refs.grey_light` block is exposed; take it.

All selectors needed for implementation are validated against saved fixtures. Ready to build.
