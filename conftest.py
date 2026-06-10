"""Test-suite shim so the pytest collection works without Calibre installed.

Unit tests are pure by design (they import only the calibre-free ``parser`` module),
so this registers empty stand-ins for the Calibre/Qt modules purely as a safety net:
an accidental import during collection raises no ``ModuleNotFoundError``. Integration
tests (gated on ``BABELIO_COOKIE``/``BABELIO_UA``) handle their own skip logic before
importing anything calibre-dependent.
"""

import sys
import types

for _name in ("calibre", "qt", "qt.core"):
    sys.modules.setdefault(_name, types.ModuleType(_name))
