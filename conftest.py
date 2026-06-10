"""Pytest shim that stubs `calibre`/`qt` and their builtins so collection works off-Calibre."""

from __future__ import annotations

import builtins
import importlib.abc
import importlib.machinery
import sys
import types
from collections.abc import Sequence

_STUB_ROOTS = ("calibre", "qt")


class _StubModule(types.ModuleType):
    def __getattr__(self, name: str) -> type:
        attr = type(name, (), {})
        setattr(self, name, attr)
        return attr


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.split(".", 1)[0] not in _STUB_ROOTS:
            return None
        return importlib.machinery.ModuleSpec(fullname, self)

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        return _StubModule(spec.name)

    def exec_module(self, module: types.ModuleType) -> None:
        pass


sys.meta_path.insert(0, _StubFinder())
builtins.load_translations = lambda *args, **kwargs: None  # type: ignore[attr-defined]
builtins._ = lambda text: text  # type: ignore[attr-defined]
