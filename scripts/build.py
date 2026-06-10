"""Build the installable Calibre plugin ZIP (compiles `fr.po` → `fr.mo`)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "calibre_babelio"
TRANSLATIONS = PACKAGE / "translations"
DIST = ROOT / "dist"
OUTPUT = DIST / "babelio.zip"

LOCALES = ["fr"]

_EXCLUDED_SUFFIXES = (".pyc", ".po", ".pot")
_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def compile_catalogs() -> None:
    for locale in LOCALES:
        po_path = TRANSLATIONS / f"{locale}.po"
        with po_path.open("rb") as fh:
            catalog = read_po(fh, locale=locale)
        bad = [
            message.id
            for message in catalog
            if message.id and (not message.string or message.fuzzy)
        ]
        if bad:
            raise SystemExit(
                f"{po_path.name} has {len(bad)} untranslated/fuzzy entries; aborting build"
            )
        with (TRANSLATIONS / f"{locale}.mo").open("wb") as fh:
            write_mo(fh, catalog)


def _staged_files() -> list[tuple[str, Path]]:
    staged: list[tuple[str, Path]] = []
    for path in PACKAGE.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in _EXCLUDED_SUFFIXES:
            continue
        staged.append((path.relative_to(PACKAGE).as_posix(), path))
    staged.sort()
    return staged


def build_zip() -> list[str]:
    DIST.mkdir(parents=True, exist_ok=True)
    staged = _staged_files()
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for arcname, path in staged:
            info = zipfile.ZipInfo(arcname, date_time=_ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return [arcname for arcname, _ in staged]


def main() -> None:
    compile_catalogs()
    names = build_zip()
    print(f"Built {OUTPUT.relative_to(ROOT)} with {len(names)} files")


if __name__ == "__main__":
    main()
