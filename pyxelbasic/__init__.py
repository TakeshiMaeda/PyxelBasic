# -*- coding: utf-8 -*-
"""PyxelBasic package."""

from .version import __version__
from .interpreter import Interpreter, tokenize, BasicError

__all__ = ["Interpreter", "tokenize", "BasicError", "App", "__version__"]


def __getattr__(name):
    # Import App (and thus Pyxel) lazily, so that importing the package or its
    # version does not require Pyxel or a display (e.g. for `--version`).
    if name == "App":
        from .app import App
        return App
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
