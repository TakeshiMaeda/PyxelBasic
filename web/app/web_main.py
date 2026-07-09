# -*- coding: utf-8 -*-
"""PyxelBasic web launcher (runs under Pyodide inside the pyxapp).

The page (boot.js) prepares two JS globals before launching:
    window.pyxelbasicStorage  storage bridge (see web/site/js/storage.js)
    window.pyxelbasicOptions  {autoload, autorun, stepsPerFrame, showFps}

The web version always runs exec_mode="main" (single-threaded; Pyodide has
no threads) and stores SAVE/LOAD/FILES in browser storage via WebFileStore.
"""

from js import window

from pyxelbasic.app import App
from webfilestore import WebFileStore


def _opt(opts, name, default):
    if opts is None:
        return default
    value = getattr(opts, name, None)
    return default if value is None else value


def main():
    opts = getattr(window, "pyxelbasicOptions", None)
    store = WebFileStore(window.pyxelbasicStorage)
    autoload = _opt(opts, "autoload", None)
    steps = _opt(opts, "stepsPerFrame", None)
    App(autoload=str(autoload) if autoload else None,
        autorun=bool(_opt(opts, "autorun", False)),
        steps_per_frame=int(steps) if steps else None,
        show_fps=bool(_opt(opts, "showFps", False)),
        exec_mode="main",
        filestore=store).run()


main()
