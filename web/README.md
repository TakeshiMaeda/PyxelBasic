# PyxelBasic Web

English | [日本語](README.ja.md)

Run PyxelBasic in a browser. The same `pyxelbasic` package as the desktop
version runs unmodified on top of Pyxel's official web runtime. No installation
needed: open the page and click the screen to start.

> Live page: https://takeshimaeda.github.io/PyxelBasic/

This page explains how to use the web version and how it differs from the
desktop version.

## Page features

- **Storage panel** — BASIC's `SAVE` / `LOAD` / `FILES` use the browser's
  storage (IndexedDB). The panel lists files and supports download, delete,
  drag & drop import and URL import. The sample programs are set up
  automatically on the first visit.
- **Disk image** — the "Disk image" row in the Storage panel exports every
  stored file as one ZIP (Export) and imports a ZIP to replace the whole
  storage contents (Import, with a confirmation dialog). Think of it as a
  floppy disk or USB stick image, for backups or carrying files to another
  browser. The exported file is an ordinary ZIP that opens with the standard
  OS tools, and a ZIP made by the OS (a bundle of .bas files) imports fine
  in return. Dropping a `.zip` on the drop zone also imports it as an image.
  Page settings such as the theme are not part of an image and survive an
  import.
- **Options panel** — set load-on-start, autorun, steps per frame and the FPS
  display, then relaunch with "Apply and Restart".
- **Theme panel** — change the page's colors with a preset or per-color
  overrides; the setting is saved in the browser.
- **Query parameters** — the URL can control the startup behavior:

| Parameter | Meaning |
|---|---|
| `?load=NAME` | load NAME from storage on startup |
| `&run=1` | run the loaded program automatically |
| `&spf=N` | BASIC statements per frame (default 8000) |
| `&fps=1` | show the frame rate in the title |
| `&src=URL` | import a remote program into storage before boot (it becomes the load target unless `load=` is also given) |
| `&name=NAME` | storage name for `src=` (default: the URL's file name) |

A shareable link that runs a program just by opening it:

```
https://takeshimaeda.github.io/PyxelBasic/?src=https://raw.githubusercontent.com/.../game.bas&run=1
```

The `src=` source must be a CORS-enabled host
(raw.githubusercontent.com, gists and jsdelivr all work).

## Differences from the desktop version

- The execution mode is fixed to main (no threads in the browser, so thread
  mode is unavailable)
- `SAVE` / `LOAD` / `FILES` use browser storage (no `--workdir` / `--ext`
  equivalents, extensions fixed to `.bas,.pxbas`, file names are
  case-sensitive)
- Quitting via the ESC dialog leaves the screen frozen (reload the page to
  restart)
- When browser storage is unavailable (private browsing etc.), the storage is
  a temporary in-memory one and the page shows a warning
