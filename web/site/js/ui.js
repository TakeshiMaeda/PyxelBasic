/* Page UI for PyxelBasic web: the Menu overlay (storage / options / help
 * accordions) and banners. The overlay is hidden while operating PyxelBasic
 * and opened with the Menu button.
 *
 * Reads and writes files only through window.pyxelbasicStorage (storage.js).
 * The options section maps 1:1 to the query parameters boot.js understands;
 * "Apply and Restart" rewrites the query string and reloads, which relaunches
 * the whole runtime with the new options (the reliable restart path).
 */
"use strict";

(async function () {
  const storage = window.pyxelbasicStorage;
  await storage.ready;   // theme/meta and the file list need the loaded cache
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);

  /* --- theme ---
     Colors live in CSS custom properties (see style.css :root for the
     defaults = the "dark" preset). A preset plus optional per-color
     overrides are persisted in browser storage and applied on the root
     element, so they win over the stylesheet defaults. */
  const THEME_VARS = [
    ["--pb-bg", "Background"],
    ["--pb-fg", "Text"],
    ["--pb-muted", "Sub text"],
    ["--pb-panel", "Panel"],
    ["--pb-border", "Border"],
    ["--pb-control", "Buttons"],
    ["--pb-accent", "Accent"],
  ];
  const THEMES = {
    dark: {
      "--pb-bg": "#1a1a1e", "--pb-fg": "#dddddd", "--pb-muted": "#9a9aa4",
      "--pb-panel": "#232329", "--pb-border": "#3a3a44",
      "--pb-control": "#34343e", "--pb-accent": "#8a8af0",
    },
    light: {
      "--pb-bg": "#eeeef2", "--pb-fg": "#26262c", "--pb-muted": "#6a6a74",
      "--pb-panel": "#fafafc", "--pb-border": "#c4c4ce",
      "--pb-control": "#e0e0e8", "--pb-accent": "#4a4ad0",
    },
    navy: {
      "--pb-bg": "#1d2340", "--pb-fg": "#e8ecff", "--pb-muted": "#93a3d8",
      "--pb-panel": "#2b335f", "--pb-border": "#3d477e",
      "--pb-control": "#395c98", "--pb-accent": "#a9c1ff",
    },
    green: {
      "--pb-bg": "#08140a", "--pb-fg": "#57e389", "--pb-muted": "#2f9e5b",
      "--pb-panel": "#0e2214", "--pb-border": "#1c5f36",
      "--pb-control": "#123920", "--pb-accent": "#8ff0b4",
    },
    pink: {
      "--pb-bg": "#ffe3ee", "--pb-fg": "#8a3d62", "--pb-muted": "#d585a8",
      "--pb-panel": "#fff0f6", "--pb-border": "#ffb8d2",
      "--pb-control": "#ffd1e3", "--pb-accent": "#ff6fa5",
    },
  };

  let theme;
  try {
    theme = JSON.parse(storage.getMeta("theme") || "null");
  } catch (e) {
    theme = null;
  }
  if (!theme || !(theme.preset in THEMES)) {
    theme = { preset: "dark", overrides: {} };
  }
  theme.overrides = theme.overrides || {};

  function themeColor(name) {
    return theme.overrides[name] || THEMES[theme.preset][name];
  }

  function applyTheme() {
    for (const [name] of THEME_VARS) {
      document.documentElement.style.setProperty(name, themeColor(name));
      const input = document.getElementById("pb-theme-color" + name);
      if (input) input.value = themeColor(name);
    }
    $("pb-theme-preset").value = theme.preset;
  }

  function saveTheme() {
    storage.setMeta("theme", JSON.stringify(theme));
  }

  const presetSel = $("pb-theme-preset");
  for (const name of Object.keys(THEMES)) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    presetSel.appendChild(opt);
  }
  presetSel.addEventListener("change", () => {
    theme.preset = presetSel.value;
    theme.overrides = {};
    saveTheme();
    applyTheme();
  });

  const colorRows = $("pb-theme-colors");
  for (const [name, label] of THEME_VARS) {
    const row = document.createElement("div");
    row.className = "pb-theme-row";
    const text = document.createElement("span");
    text.textContent = label;
    const input = document.createElement("input");
    input.type = "color";
    input.id = "pb-theme-color" + name;
    input.addEventListener("input", () => {
      theme.overrides[name] = input.value;
      saveTheme();
      applyTheme();
    });
    row.append(text, input);
    colorRows.appendChild(row);
  }

  $("pb-theme-reset").addEventListener("click", () => {
    theme.overrides = {};
    saveTheme();
    applyTheme();
  });

  applyTheme();

  /* --- overlay open/close --- */
  const overlay = $("pb-overlay");
  $("pb-menu-btn").addEventListener("click", (e) => {
    overlay.hidden = false;
    e.currentTarget.blur();
  });
  $("pb-close-btn").addEventListener("click", () => {
    overlay.hidden = true;
  });
  $("pb-overlay-backdrop").addEventListener("click", () => {
    overlay.hidden = true;
  });

  /* --- header version --- */
  fetch("version.json")
    .then((r) => (r.ok ? r.json() : null))
    .then((v) => {
      if (v) {
        $("pb-version").textContent =
          "v" + v.pyxelbasic + " / pyxel " + v.pyxelWasm;
      }
    })
    .catch(() => {});

  /* --- banner (fatal errors, non-persistent storage) --- */
  function showBanner(msg) {
    const b = $("pb-banner");
    b.textContent = msg;
    b.hidden = false;
  }
  if (!storage.persistent) {
    showBanner("Browser storage is unavailable (private mode?). " +
               "SAVE will not survive a reload.");
  }
  storage.onWriteError = (msg) => {
    showBanner("Storage write failed - recent changes may not persist (" +
               msg + ")");
  };
  window.addEventListener("error", () => {
    const ctx = window.pyxelContext;
    if (ctx && ctx.hasFatalError) {
      showBanner("PyxelBasic stopped with an error - " +
                 "see the browser console for details.");
    }
  });

  /* --- storage panel --- */
  function fmtBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
    return (n / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  }

  // The storage quota is only knowable asynchronously; the meter renders
  // without it first and again once the estimate arrives.
  let quotaNote = "";
  if (navigator.storage && navigator.storage.estimate) {
    navigator.storage.estimate().then((est) => {
      if (est && est.quota) {
        quotaNote = " (quota ~" + fmtBytes(est.quota) + ")";
        renderFiles();
      }
    }).catch(() => {});
  }

  function storageMsg(text, isError) {
    const el = $("pb-storage-msg");
    el.textContent = text;
    el.classList.toggle("pb-error", !!isError);
  }

  function renderFiles() {
    const names = storage.listNames().sort(
      (a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
    const list = $("pb-file-list");
    list.textContent = "";
    for (const name of names) {
      const li = document.createElement("li");
      const label = document.createElement("span");
      label.className = "pb-file-name";
      label.textContent = name;
      label.title = name + " (" + fmtBytes((storage.getFile(name) || "").length) + ")";
      const dl = document.createElement("button");
      dl.textContent = "Download";
      dl.addEventListener("click", () => storage.downloadFile(name));
      const del = document.createElement("button");
      del.textContent = "Delete";
      del.addEventListener("click", () => {
        if (window.confirm('Delete "' + name + '" from browser storage?')) {
          storage.deleteFile(name);
        }
      });
      li.append(label, dl, del);
      list.appendChild(li);
    }
    $("pb-usage").textContent =
      names.length + " files, " + fmtBytes(storage.usedBytes()) +
      " in browser storage" + quotaNote;
    renderLoadOptions(names);
  }

  /* --- drag & drop / file picker --- */
  const dropzone = $("pb-dropzone");
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("pb-dragging");
  });
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("pb-dragging");
  });
  dropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropzone.classList.remove("pb-dragging");
    // A dropped .zip is a disk image, not a program text; route it to the
    // image import (with its replace confirmation) instead of storing the
    // raw bytes as a file.
    const dropped = Array.from(e.dataTransfer.files);
    const images = dropped.filter((f) => /\.zip$/i.test(f.name));
    const texts = dropped.filter((f) => !/\.zip$/i.test(f.name));
    try {
      if (texts.length) {
        const names = await storage.importFiles(texts);
        storageMsg("Imported: " + names.join(", "));
      }
    } catch (err) {
      storageMsg("Import failed: " + err.message, true);
    }
    for (const image of images) {
      await importImage(image);
    }
  });
  $("pb-file-input").addEventListener("change", async (e) => {
    try {
      const names = await storage.importFiles(e.target.files);
      storageMsg("Imported: " + names.join(", "));
    } catch (err) {
      storageMsg("Import failed: " + err.message, true);
    }
    e.target.value = "";
  });

  /* --- URL import --- */
  $("pb-url-btn").addEventListener("click", async () => {
    const url = $("pb-url-input").value.trim();
    if (!url) return;
    storageMsg("Fetching...");
    try {
      const name = await storage.importFromUrl(url);
      storageMsg('Imported as "' + name + '"');
    } catch (err) {
      storageMsg("Import failed (the host must allow CORS): " + err.message,
                 true);
    }
  });

  /* --- disk image (whole-storage ZIP export/import) ---
     The floppy/USB metaphor: export packs every stored file into one ZIP,
     import replaces the whole storage with an image's contents (after a
     confirmation). Only files travel in an image; meta (theme etc.) is a
     setting of this "machine" and survives an import. Everything goes
     through the public storage surface, so the alternative backends under
     web/alt/ keep working unchanged. */
  /* The blob URL must outlive the whole download: with "ask where to save"
     the browser reads the blob only after the user picks a location.
     Revoking the previous URL when the next export starts still killed an
     export whose dialog was open (double click), so export URLs are never
     revoked; they are released with the document. */

  $("pb-image-export").addEventListener("click", async () => {
    const names = storage.listNames().sort(
      (a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
    if (!names.length) {
      storageMsg("No files to export.");
      return;
    }
    try {
      const entries = names.map(
        (name) => ({ name, text: storage.getFile(name) }));
      const blob = await window.pyxelbasicZip.build(entries);
      const d = new Date();
      const pad = (n) => String(n).padStart(2, "0");
      const zipName = "pyxelbasic-" + d.getFullYear() + pad(d.getMonth() + 1) +
        pad(d.getDate()) + "-" + pad(d.getHours()) + pad(d.getMinutes()) +
        ".zip";
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = zipName;
      a.click();
      storageMsg("Exported " + names.length + " files as " + zipName);
    } catch (err) {
      storageMsg("Export failed: " + err.message, true);
    }
  });

  async function importImage(file) {
    try {
      const image = await window.pyxelbasicZip.read(await file.arrayBuffer());
      if (!image.files.length) {
        storageMsg('No files in "' + file.name + '" - storage not changed.',
                   true);
        return;
      }
      const current = storage.listNames();
      if (!window.confirm(
            "Replace the " + current.length + " files in browser storage " +
            "with the " + image.files.length + ' files in "' + file.name +
            '"?')) {
        storageMsg("Import cancelled.");
        return;
      }
      for (const name of current) storage.deleteFile(name);
      for (const entry of image.files) storage.putFile(entry.name, entry.text);
      let msg = "Imported " + image.files.length + ' files from "' +
                file.name + '"';
      if (image.skipped.length) {
        msg += " (skipped " + image.skipped.length + " in subfolders)";
      }
      storageMsg(msg);
    } catch (err) {
      storageMsg("Import failed: " + err.message, true);
    }
  }

  $("pb-image-input").addEventListener("change", async (e) => {
    if (e.target.files.length) {
      await importImage(e.target.files[0]);
    }
    e.target.value = "";
  });

  /* --- options panel --- */
  function renderLoadOptions(names) {
    const sel = $("pb-opt-load");
    const current = sel.value || params.get("load") || "";
    sel.textContent = "";
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "(none)";
    sel.appendChild(none);
    for (const name of names) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    }
    sel.value = names.includes(current) ? current : "";
  }

  $("pb-opt-run").checked = params.get("run") === "1";
  $("pb-opt-fps").checked = params.get("fps") === "1";
  if (params.get("spf")) $("pb-opt-spf").value = params.get("spf");

  $("pb-opt-apply").addEventListener("click", () => {
    const q = new URLSearchParams();
    const load = $("pb-opt-load").value;
    if (load) q.set("load", load);
    if ($("pb-opt-run").checked && load) q.set("run", "1");
    const spf = $("pb-opt-spf").value;
    if (spf) q.set("spf", spf);
    if ($("pb-opt-fps").checked) q.set("fps", "1");
    const qs = q.toString();
    window.location.search = qs ? "?" + qs : "";
  });

  /* Keep keys typed into the overlay panel away from the Pyxel canvas (SDL
     listens at the document level); without this, typing a URL would also
     type into BASIC. */
  for (const type of ["keydown", "keyup", "keypress"]) {
    $("pb-panel").addEventListener(type, (e) => e.stopPropagation());
  }

  /* While typing into BASIC (focus not on a sidebar form control), stop the
     browser's own reaction to navigation keys: Tab must not move the focus
     (and draw focus rings), End/Home/PageUp/PageDown/arrows must not scroll
     the page. preventDefault does not stop SDL's listeners, so BASIC still
     receives every key. */
  const NAV_KEYS = new Set([
    "Tab", "Home", "End", "PageUp", "PageDown",
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
  ]);
  const isFormControl = (el) =>
    el instanceof HTMLElement &&
    /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(el.tagName);
  document.addEventListener("keydown", (e) => {
    if (NAV_KEYS.has(e.key) && !isFormControl(e.target)) {
      e.preventDefault();
    }
  }, true);

  /* Clicking a panel button must not park the keyboard focus there: the
     panel swallows keys (see above), so a focused button would eat all
     typing until the canvas is clicked again. Release the focus on click. */
  $("pb-panel").addEventListener("click", (e) => {
    if (e.target instanceof HTMLButtonElement) {
      e.target.blur();
    }
  });

  storage.subscribe(renderFiles);
  renderFiles();
})();
