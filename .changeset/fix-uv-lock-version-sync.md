---
"calibre-babelio-plugin": patch
---

Refresh `uv.lock` when syncing the release version. `sync-version.mjs` bumped `pyproject.toml` and `__init__.py` but left the lockfile pinned to the previous project version, so release PRs shipped a stale `uv.lock` that the next `uv` invocation silently rewrote.
