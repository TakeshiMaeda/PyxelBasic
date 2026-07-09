# -*- coding: utf-8 -*-
"""Build script for the PyxelBasic web distribution.

Usage:
    python web/build.py    build web/dist/ (the publishable folder)

The Pyxel wasm runtime (pyxel.js and everything it pulls: the emscripten
wheel, pyxel.css, images, and Pyodide itself) is NOT downloaded or bundled.
The page loads pyxel.js straight from the jsdelivr CDN at the version pinned
below - the same CDN Pyxel already uses for Pyodide - so nothing of Pyxel's is
redistributed from this repo or from dist/. Bumping the web pyxel version is a
one-line change to PYXEL_WASM_VERSION (it is injected into index.html's CDN
URL and reported in version.json); rebuild and verify in a browser.
"""

import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys

# Pinned pyxel version for the web runtime (jsdelivr serves the git tag).
# The single source: index.html's pyxel.js CDN URL and version.json both come
# from here.
PYXEL_WASM_VERSION = "2.9.7"

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(WEB_DIR)
BUILD_DIR = os.path.join(WEB_DIR, "build")
DIST_DIR = os.path.join(WEB_DIR, "dist")
APP_NAME = "pyxelbasic_web"

# Placeholder in site/index.html replaced with the pinned tag at build time.
VERSION_TOKEN = "__PYXEL_WASM_TAG__"


def _pyxelbasic_version():
    sys.path.insert(0, ROOT_DIR)
    try:
        from pyxelbasic.version import __version__  # Pyxel-free import
    finally:
        sys.path.pop(0)
    return __version__


def stage_app():
    """Assemble web/build/stage/pyxelbasic_web/ (the pyxapp content)."""
    stage_root = os.path.join(BUILD_DIR, "stage")
    app_dir = os.path.join(stage_root, APP_NAME)
    if os.path.exists(stage_root):
        shutil.rmtree(stage_root)
    os.makedirs(app_dir)
    for fn in ("web_main.py", "webfilestore.py"):
        shutil.copy2(os.path.join(WEB_DIR, "app", fn), app_dir)
    shutil.copytree(os.path.join(ROOT_DIR, "pyxelbasic"),
                    os.path.join(app_dir, "pyxelbasic"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    print("stage: %s" % app_dir)
    return app_dir


def package_pyxapp(app_dir):
    """Run pyxel package; the pyxapp lands in the process CWD (web/build)."""
    pyxapp = os.path.join(BUILD_DIR, APP_NAME + ".pyxapp")
    if os.path.exists(pyxapp):
        os.remove(pyxapp)
    startup = os.path.join(app_dir, "web_main.py")
    cmd = [sys.executable, "-m", "pyxel", "package", app_dir, startup]
    print("package: %s" % " ".join(cmd[2:]))
    subprocess.run(cmd, check=True, cwd=BUILD_DIR)
    if not os.path.exists(pyxapp):
        raise RuntimeError("pyxel package did not produce %s" % pyxapp)
    return pyxapp


def _pin_pyxel_version(index_path):
    """Replace the CDN version placeholder in dist/index.html."""
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    if VERSION_TOKEN not in html:
        raise RuntimeError("%s not found in index.html" % VERSION_TOKEN)
    html = html.replace(VERSION_TOKEN, "v" + PYXEL_WASM_VERSION)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)


def assemble_dist(pyxapp):
    """Build web/dist/ - the folder to publish as-is."""
    version = _pyxelbasic_version()
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    shutil.copytree(os.path.join(WEB_DIR, "site"), DIST_DIR)
    shutil.copy2(pyxapp, DIST_DIR)
    _pin_pyxel_version(os.path.join(DIST_DIR, "index.html"))

    samples_dir = os.path.join(DIST_DIR, "samples")
    os.makedirs(samples_dir)
    names = []
    for path in sorted(glob.glob(os.path.join(ROOT_DIR, "samples", "*.bas"))):
        shutil.copy2(path, samples_dir)
        names.append(os.path.basename(path))
    with open(os.path.join(samples_dir, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump({"version": version, "files": names}, f, indent=2)

    with open(os.path.join(DIST_DIR, "version.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "pyxelbasic": version,
            "pyxelWasm": PYXEL_WASM_VERSION,
            "built": datetime.datetime.now(datetime.timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, f, indent=2)
    print("dist: %s (%d samples)" % (DIST_DIR, len(names)))


def main():
    argparse.ArgumentParser(
        prog="build.py",
        description="Build the PyxelBasic web distribution.").parse_args()
    app_dir = stage_app()
    pyxapp = package_pyxapp(app_dir)
    assemble_dist(pyxapp)
    print("done. Local test:")
    print("  python -m http.server 8000 -d %s" %
          os.path.relpath(DIST_DIR, os.getcwd()))
    print("  -> http://localhost:8000/")


if __name__ == "__main__":
    main()
