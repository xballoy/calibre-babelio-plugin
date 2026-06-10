---
"calibre-babelio-plugin": patch
---

Add Renovate configuration extending the shared `xballoy/renovate-config` preset to automate dependency, lockfile, and GitHub Actions updates. Python version updates (`.python-version` and `requires-python`) are disabled because the plugin must track the Python interpreter bundled with Calibre.
