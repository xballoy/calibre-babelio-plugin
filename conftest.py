"""Test-suite shim so pytest collection works without Calibre installed.

Importing any ``calibre_babelio`` submodule runs the package ``__init__.py`` — the plugin entry
point — which imports ``calibre`` and calls the ``load_translations`` / ``_`` builtins Calibre
installs at startup. None of that exists off-Calibre, so this shim registers no-op builtins and a
meta-path finder that fabricates dummy ``calibre.*`` / ``qt.*`` modules (attribute access yields a
dummy class, usable even as a base class). Unit tests stay pure: they exercise the calibre-free
modules and never touch the fabricated stand-ins. Integration tests (gated on
``BABELIO_COOKIE``/``BABELIO_UA``) handle their own skip logic against real Calibre.
"""

import builtins
import importlib.abc
import importlib.machinery
import sys
import types

_STUB_ROOTS = ("calibre", "qt")


class _StubModule(types.ModuleType):
    def __getattr__(self, name: str) -> type:
        attr = type(name, (), {})
        setattr(self, name, attr)
        return attr


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001, ANN201
        if fullname.split(".", 1)[0] not in _STUB_ROOTS:
            return None
        return importlib.machinery.ModuleSpec(fullname, self)

    def create_module(self, spec):  # noqa: ANN001, ANN201
        return _StubModule(spec.name)

    def exec_module(self, module):  # noqa: ANN001, ANN201
        pass


sys.meta_path.insert(0, _StubFinder())
builtins.load_translations = lambda *args, **kwargs: None  # type: ignore[attr-defined]
builtins._ = lambda text: text  # type: ignore[attr-defined]
