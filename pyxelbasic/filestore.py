# -*- coding: utf-8 -*-
"""File storage seam for SAVE/LOAD/FILES.

Session never touches the filesystem directly; it goes through a small
duck-typed store object providing the FILESTORE_METHODS surface. The default
LocalFileStore stores plain files in a fixed working directory; the web front
end injects a browser-storage implementation with the same surface (kept
outside this package, under web/). Name resolution (extension priority) lives
here as pure functions shared by every implementation, so the SAVE/LOAD
behavior stays identical across platforms by construction.
"""

import os

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

# Program file extensions, in priority order. The first is appended by SAVE
# when the name has no extension; LOAD tries them in order until a file
# exists. Overridable at startup (--ext); fixed for the session after that.
DEFAULT_EXTENSIONS = (".bas", ".pxbas")

# The store surface Session relies on (duck typing; verified by an assert in
# Session.__init__, in the spirit of the interpreter's dispatch-name check).
#   save(name, text) -> stored display name
#   load(name)       -> (display_name, text) or None when not found
#   list_names()     -> plain file names (unsorted; Session sorts/filters)
FILESTORE_METHODS = ("save", "load", "list_names")


def resolve_save_name(name, extensions):
    """Append the first-priority extension when the name has none."""
    if not os.path.splitext(name)[1]:
        name += extensions[0]
    return name


def resolve_load_name(name, exists, extensions):
    """Resolve the name LOAD should read.

    The typed name is tried exactly as given first; when no such file exists,
    the registered extensions are appended in priority order (never
    substituted) and the first existing candidate wins. When nothing exists,
    the literal name is returned so the caller's not-found report has a
    concrete name to test. `exists` is a callable so every store shares this
    logic against its own backend.
    """
    if exists(name):
        return name
    for ext in extensions:
        candidate = name + ext
        if exists(candidate):
            return candidate
    return name


class LocalFileStore:
    """Default store: plain files in a fixed working directory."""

    def __init__(self, workdir=None, extensions=None):
        self.workdir = os.path.abspath(workdir) if workdir else SAMPLE_DIR
        self.extensions = tuple(extensions) if extensions else DEFAULT_EXTENSIONS

    def save(self, name, text):
        name = resolve_save_name(name, self.extensions)
        os.makedirs(self.workdir, exist_ok=True)
        path = os.path.join(self.workdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return os.path.basename(path)

    def load(self, name):
        found = resolve_load_name(name, self._exists, self.extensions)
        path = os.path.join(self.workdir, found)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return os.path.basename(path), text

    def list_names(self):
        try:
            entries = os.listdir(self.workdir)
        except OSError:
            return []
        return [e for e in entries
                if os.path.isfile(os.path.join(self.workdir, e))]

    def _exists(self, name):
        return os.path.exists(os.path.join(self.workdir, name))


# Catch a store/declaration mismatch at import time (cheap interface check).
assert all(hasattr(LocalFileStore, m) for m in FILESTORE_METHODS)
