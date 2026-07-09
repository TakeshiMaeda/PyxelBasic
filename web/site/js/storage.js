/* Storage bridge for PyxelBasic web.
 *
 * The single place that touches browser storage. BASIC's SAVE/LOAD/FILES
 * reach this object from Python (WebFileStore -> window.pyxelbasicStorage),
 * and the page UI uses the same object, so both sides always see the same
 * files. Keeping every storage access in this file lets the backend be
 * swapped without touching the Python side or the UI.
 *
 * Backend: IndexedDB (DB "pyxelbasic", stores "files" and "meta") behind a
 * write-through in-memory cache. BASIC runs synchronously, so reads are
 * served from the cache (loaded once via the `ready` Promise before launch)
 * and writes update the cache synchronously, then flush to IndexedDB in the
 * background. This page is the only writer, so the cache stays coherent;
 * changes from another tab arrive best-effort via BroadcastChannel.
 */
"use strict";

(function () {
  const DB_NAME = "pyxelbasic";
  const DB_VERSION = 1;
  const DEFAULT_EXT = ".bas";

  // Write-through cache: the synchronous view Python and the UI read from.
  const files = new Map();   // name -> text
  const meta = new Map();    // name -> string

  let db = null;             // IDBDatabase, or null = in-memory only
  let downloadUrl = null;    // blob URL of the last download (see below)

  const listeners = new Set();
  function notify() {
    listeners.forEach((fn) => { try { fn(); } catch (e) { /* UI's problem */ } });
  }

  function reportWriteError(err) {
    console.error("PyxelBasic: storage write failed:", err);
    if (storage.onWriteError) {
      try { storage.onWriteError(String(err)); } catch (e) { /* ignore */ }
    }
  }

  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const d = req.result;
        if (!d.objectStoreNames.contains("files")) d.createObjectStore("files");
        if (!d.objectStoreNames.contains("meta")) d.createObjectStore("meta");
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
      req.onblocked = () => reject(new Error("database blocked"));
    });
  }

  function readAllInto(storeName, map) {
    return new Promise((resolve, reject) => {
      const req = db.transaction(storeName, "readonly")
        .objectStore(storeName).openCursor();
      req.onsuccess = () => {
        const cur = req.result;
        if (cur) {
          map.set(String(cur.key), String(cur.value));
          cur.continue();
        } else {
          resolve();
        }
      };
      req.onerror = () => reject(req.error);
    });
  }

  // Background flush of one cache mutation (value null = delete).
  function write(storeName, name, value) {
    if (!db) return;
    try {
      const tx = db.transaction(storeName, "readwrite");
      const os = tx.objectStore(storeName);
      if (value === null) {
        os.delete(name);
      } else {
        os.put(value, name);
      }
      tx.oncomplete = () => broadcast();
      tx.onerror = () => reportWriteError(tx.error);
      tx.onabort = () => reportWriteError(tx.error || "transaction aborted");
    } catch (e) {
      reportWriteError(e);
    }
  }

  // Cross-tab refresh (best effort): another tab of the same origin reloads
  // its cache from the database when this one commits a change.
  let channel = null;
  try {
    channel = new BroadcastChannel("pyxelbasic-storage");
  } catch (e) { /* not supported; single-tab behavior only */ }

  function broadcast() {
    if (channel) {
      try { channel.postMessage("changed"); } catch (e) { /* ignore */ }
    }
  }

  async function reloadFromDb() {
    if (!db) return;
    try {
      const f = new Map();
      const m = new Map();
      await Promise.all([readAllInto("files", f), readAllInto("meta", m)]);
      files.clear();
      for (const [k, v] of f) files.set(k, v);
      meta.clear();
      for (const [k, v] of m) meta.set(k, v);
      notify();
    } catch (e) { /* keep the current cache */ }
  }

  if (channel) {
    channel.onmessage = () => { reloadFromDb(); };
  }

  // Files dropped or fetched keep their own name; a name without any
  // extension gets the default one, mirroring BASIC's SAVE rule.
  function normalizeName(name) {
    name = name.trim();
    return name.includes(".") ? name : name + DEFAULT_EXT;
  }

  const storage = {
    persistent: false,     // set by ready once the DB is open
    ready: null,           // Promise; boot.js/ui.js await it before reading
    onWriteError: null,    // hook set by ui.js to surface flush failures

    /* --- the surface Python (WebFileStore) relies on --- */
    listNames() {
      return Array.from(files.keys());
    },
    getFile(name) {
      return files.has(name) ? files.get(name) : null;
    },
    putFile(name, text) {
      text = String(text);
      files.set(name, text);
      write("files", name, text);
      notify();
    },
    exists(name) {
      return files.has(name);
    },

    /* --- UI-side operations --- */
    deleteFile(name) {
      const had = files.delete(name);
      if (had) {
        write("files", name, null);
        notify();
      }
      return had;
    },
    usedBytes() {
      // Rough figure for the usage meter (JS strings are UTF-16 units).
      let units = 0;
      for (const [k, v] of files) units += k.length + v.length;
      return units * 2;
    },
    downloadFile(name) {
      const text = this.getFile(name);
      if (text === null) return false;
      const blob = new Blob([text], { type: "text/plain" });
      // The blob URL must outlive the whole download: with "ask where to
      // save" the browser reads the blob only after the user picks a
      // location, and a URL revoked by then leaves a stuck .crdownload.
      // Keep the URL until the next download replaces it.
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
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
      return meta.has(name) ? meta.get(name) : null;
    },
    setMeta(name, value) {
      value = String(value);
      meta.set(name, value);
      write("meta", name, value);
    },
  };

  storage.ready = (async () => {
    try {
      db = await openDb();
      await Promise.all([readAllInto("files", files),
                         readAllInto("meta", meta)]);
      storage.persistent = true;
      // Best effort: ask the browser not to evict this origin's storage
      // under disk pressure.
      if (navigator.storage && navigator.storage.persist) {
        navigator.storage.persist().catch(() => {});
      }
    } catch (e) {
      console.warn("PyxelBasic: IndexedDB unavailable, storage is in-memory:",
                   e);
      db = null;
      storage.persistent = false;
    }
  })();

  window.pyxelbasicStorage = storage;
})();
