/* Boot sequence for PyxelBasic web.
 *
 * Order matters: query parameters -> URL import -> one-time sample import ->
 * options global -> launchPyxel. Everything that must be visible to BASIC's
 * FILES from the very first prompt happens before the launch.
 *
 * Query parameters:
 *   ?load=NAME   load NAME from storage on startup
 *   &run=1       run the loaded program automatically
 *   &spf=N       BASIC statements per frame (default 8000)
 *   &fps=1       show the frame rate in the title
 *   &src=URL     import a remote program into storage first (CORS permitting);
 *                becomes the autoload target unless load= is also given
 *   &name=NAME   storage name for src= (default: URL basename)
 */
"use strict";

(async function () {
  const storage = window.pyxelbasicStorage;
  await storage.ready;   // cache loaded from IndexedDB before anything reads
  const params = new URLSearchParams(window.location.search);

  // One-time sample import; never overwrites an existing file of the same
  // name (user edits win). The imported manifest version is remembered so a
  // future "re-import samples" UI can be explicit rather than silent.
  async function importSamples() {
    try {
      const res = await fetch("samples/manifest.json");
      if (!res.ok) return;
      const manifest = await res.json();
      if (storage.getMeta("samples-imported") === String(manifest.version)) {
        return;
      }
      for (const name of manifest.files) {
        if (storage.exists(name)) continue;
        const r = await fetch("samples/" + name);
        if (r.ok) storage.putFile(name, await r.text());
      }
      storage.setMeta("samples-imported", String(manifest.version));
    } catch (e) {
      console.warn("PyxelBasic: sample import failed:", e);
    }
  }

  let srcName = null;
  const src = params.get("src");
  if (src) {
    try {
      srcName = await storage.importFromUrl(src, params.get("name") || null);
    } catch (e) {
      console.error("PyxelBasic: URL import failed (CORS?):", e);
    }
  }

  await importSamples();

  window.pyxelbasicOptions = {
    autoload: params.get("load") || srcName,
    autorun: params.get("run") === "1",
    stepsPerFrame: params.get("spf") ? Number(params.get("spf")) : null,
    showFps: params.get("fps") === "1",
  };

  launchPyxel({ command: "play", root: ".", name: "pyxelbasic_web.pyxapp" });
})();
