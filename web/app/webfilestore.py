# -*- coding: utf-8 -*-
"""Browser-storage FileStore for the web front end.

Bridges SAVE/LOAD/FILES to the page's storage API (window.pyxelbasicStorage,
implemented in web/site/js/storage.js). The storage object is injected, so
this module imports nothing browser-specific and can be tested under CPython
with a plain fake object. Name resolution reuses the shared helpers from
pyxelbasic.filestore, keeping extension-priority behavior identical to the
local store by construction.
"""

from pyxelbasic.errors import BasicError, Err
from pyxelbasic.filestore import (
    DEFAULT_EXTENSIONS, FILESTORE_METHODS,
    resolve_save_name, resolve_load_name,
)


class WebFileStore:
    """FileStore over the page's storage bridge (duck-typed JS proxy)."""

    def __init__(self, storage, extensions=None):
        self._storage = storage
        self.extensions = tuple(extensions) if extensions else DEFAULT_EXTENSIONS

    def save(self, name, text):
        name = resolve_save_name(name, self.extensions)
        try:
            self._storage.putFile(name, text)
        except Exception:
            # Browser storage write failure (typically the quota); reported
            # as a BASIC error instead of a raw JS traceback.
            raise BasicError(Err.FILE_WRITE_FAILED, name)
        return name

    def load(self, name):
        found = resolve_load_name(name, self._storage.exists, self.extensions)
        # Missing files are detected with exists() (a JS boolean converts
        # reliably to a Python bool); getFile()'s "null for missing" cannot
        # be trusted across the bridge, where JS null does not necessarily
        # arrive as Python None.
        if not self._storage.exists(found):
            return None
        return found, str(self._storage.getFile(found))

    def list_names(self):
        return [str(n) for n in self._storage.listNames()]


assert all(hasattr(WebFileStore, m) for m in FILESTORE_METHODS)
