---
"calibre-babelio-plugin": minor
---

Restore search and metadata import after Babelio's site redesign (#55), which left every search empty even though "Test connection" succeeded.

- Book details now come from the page's structured data (schema.org JSON-LD), which is less likely to break on the next restyle. Series still comes from the page's details table.
- Searching for an author's name alone now follows that author's bibliography and returns their 20 most-read books.
- **Tags** are now the book's genres as Babelio lists them (usually one or two, e.g. "science-fiction"). Babelio no longer publishes tag categories or relevance scores, so the "Tag relevance thresholds" setting has been removed.
- **Publisher** is now the publisher alone ("Albin Michel") instead of publisher and imprint ("Albin Michel / Wiz").
- Two error messages about a missing or rejected cookie are now translated into French.
