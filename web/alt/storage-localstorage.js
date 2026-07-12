/* localStorage implementation of the PyxelBasic web storage bridge.
 *
 * Same public surface as web/site/js/storage.js (the shipped IndexedDB
 * backend, which additionally exposes a `ready` Promise); drop this file in
 * as js/storage.js to store files in localStorage (~5MB) instead. All key
 * handling stays inside this file.
 */
"use strict";

(function () {
  const FILE_PREFIX = "pyxelbasic:file:";
  const META_PREFIX = "pyxelbasic:meta:";
  const DEFAULT_EXT = ".bas";

  // Feature-detect localStorage (private mode or file:// may throw); fall
  // back to a non-persistent in-memory map so the app still runs.
  let backend;
  let persistent = true;
  try {
    const probe = "pyxelbasic:probe";
    window.localStorage.setItem(probe, "1");
    window.localStorage.removeItem(probe);
    backend = window.localStorage;
  } catch (e) {
    const mem = new Map();
    backend = {
      getItem: (k) => (mem.has(k) ? mem.get(k) : null),
      setItem: (k, v) => { mem.set(k, String(v)); },
      removeItem: (k) => { mem.delete(k); },
      key: (i) => Array.from(mem.keys())[i] ?? null,
      get length() { return mem.size; },
    };
    persistent = false;
  }

  const listeners = new Set();
  function notify() {
    listeners.forEach((fn) => { try { fn(); } catch (e) { /* UI's problem */ } });
  }

  function allKeys() {
    const keys = [];
    for (let i = 0; i < backend.length; i++) keys.push(backend.key(i));
    return keys;
  }

  // Files dropped or fetched keep their own name; a name without any
  // extension gets the default one, mirroring BASIC's SAVE rule.
  function normalizeName(name) {
    name = name.trim();
    return name.includes(".") ? name : name + DEFAULT_EXT;
  }

  const storage = {
    persistent,
    ready: Promise.resolve(),

    /* --- the surface Python (WebFileStore) relies on --- */
    listNames() {
      return allKeys()
        .filter((k) => k.startsWith(FILE_PREFIX))
        .map((k) => k.slice(FILE_PREFIX.length));
    },
    getFile(name) {
      return backend.getItem(FILE_PREFIX + name);
    },
    putFile(name, text) {
      backend.setItem(FILE_PREFIX + name, text);
      notify();
    },
    exists(name) {
      return backend.getItem(FILE_PREFIX + name) !== null;
    },

    /* --- UI-side operations --- */
    deleteFile(name) {
      const had = this.exists(name);
      backend.removeItem(FILE_PREFIX + name);
      if (had) notify();
      return had;
    },
    usedBytes() {
      // Rough figure for the usage meter (localStorage stores UTF-16 units).
      let units = 0;
      for (const k of allKeys()) {
        if (k.startsWith(FILE_PREFIX)) {
          units += k.length + (backend.getItem(k) || "").length;
        }
      }
      return units * 2;
    },
    downloadFile(name) {
      const text = this.getFile(name);
      if (text === null) return false;
      const blob = new Blob([text], { type: "text/plain" });
      // The blob URL must stay alive until the browser has read the blob;
      // with "ask where to save" that happens only after the user picks a
      // location. Revoking the previous URL when the next download starts
      // (the old scheme) still killed a download whose dialog was open -
      // e.g. a double click revoked the URL the first dialog was about to
      // read, and the save failed with no file written. Blob URLs of these
      // small text files cost almost nothing and are released with the
      // document, so they are never revoked.
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      return true;
    },
    async importFiles(fileList) {
      const names = [];
      for (const file of fileList) {
        const name = normalizeName(file.name);
        this.putFile(name, await file.text());
        names.push(name);
      }
      return names;
    },
    async importFromUrl(url, name) {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status + " for " + url);
      if (!name) {
        const path = new URL(url, window.location.href).pathname;
        name = path.split("/").pop() || "program";
      }
      name = normalizeName(name);
      this.putFile(name, await res.text());
      return name;
    },
    subscribe(fn) {
      listeners.add(fn);
    },

    /* --- page metadata (sample-import flag, theme, etc.) --- */
    getMeta(name) {
      return backend.getItem(META_PREFIX + name);
    },
    setMeta(name, value) {
      backend.setItem(META_PREFIX + name, value);
    },
  };

  // Changes made from another tab of the same origin refresh this UI too.
  window.addEventListener("storage", notify);

  window.pyxelbasicStorage = storage;
})();
