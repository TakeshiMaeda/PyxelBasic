# Changelog

## 0.2.0
- Added the web version: the same source code runs in the browser (WASM, Pyxel's web runtime) via the new `web/` set (build script and publishable page)
- The web version's `SAVE` / `LOAD` / `FILES` access the browser's storage, with a storage UI on the page
- Added shareable links that run a program just by opening them (`?src=URL&run=1`) and startup query parameters (`load` / `run` / `spf` / `fps`)
- Split the `SAVE` / `LOAD` / `FILES` file access into a storage layer (`pyxelbasic/filestore.py`); desktop behavior is unchanged
- Added error code 503 for file write failures
- Added a sprite particle fountain sample `particle.bas`

## 0.1.8
- Added the `PALETTE` statement to change palette colors (`PALETTE no, rgb` / `PALETTE no, R, G, B` / `PALETTE RESET`)
- Added the `--ext` startup option to register program extensions in priority order (default `.bas,.pxbas`)
- Reworked `SAVE` / `LOAD` / `FILES` to handle extensions other than `.bas`
- Fixed a regression where `VSYNC IF ON` did not fire on stored-program `IF` lines

## 0.1.7-hotfix
- Fixed `GOSUB` inside an `IF ... THEN` / `ELSE` clause returning to the next line after `RETURN` instead of executing the rest of the clause
- Fixed `FOR ... NEXT` / `INPUT` inside a clause not working correctly within the clause (same root cause)

## 0.1.7
- Added the `FILES` command to list the `.bas` files in the working directory (`FILES "pattern"` filters the list)
- Documented that file name casing follows the host filesystem

## 0.1.6
- Added `TRI` / `TRIF` to draw a triangle / filled triangle
- Renamed the filled-circle statement `CIRCLEBF` to `CIRCLEF` (filled shapes now use the `F` suffix)
- Added a 3D cube puzzle sample `puzzle.bas`
- Added a 3D wireframe cube sample `cube.bas`
- Changed the default cap on statements run per frame in main mode (`--steps-per-frame`) from 800 to 8000

### Thanks

- Thanks to @harukaappscreate for contributing the original `TRI` / `TRIF` implementation and the 3D puzzle sample (PR #1)
- Thanks to @yukizokin (X) for contributing the 3D wireframe cube sample `cube.bas`

## 0.1.5
- Flush the typeahead buffer when a run starts (the just-typed `RUN` used to leak into `INKEY$`)
- `RENUM` now also updates the line numbers after `ELSE` (an implicit GOTO) and `RESTORE`
- `Ctrl+C` now interrupts a program waiting at an `INPUT` prompt
- Fixed `LEFT$` / `MID$` returning wrong results for a count of 0 or less, or a start below 1
- Assigning a string to a numeric array element is now an error
- `ROUND` now rounds a .5 fraction away from zero
- Fixed keys released while the quit dialog is open staying "held" afterwards

## 0.1.4
- Added sound: `PLAY` to play MML on Pyxel's 4 channels
- Added the `PLAY(ch)` function returning whether a channel is playing
- Added sprites: a Sprite plane between the Graphic and Text planes
- Added hexadecimal integer literals with the `&H` prefix (e.g. `&HFF`)
- Added the `HEX$(n)` function
- Fixed a crash when a function was called with the wrong number of arguments
- `CLS` now errors when the mask is outside 1-3
- Added the `play.bas` sample
- Added the `sprite.bas` sample
- Added the `jumpman.bas` sample

## 0.1.3
- Added the `brickbreaker.bas` sample
- Fixed a crash in `POINT` in thread mode

## 0.1.2
- Added an argument to `CLS`
- Added line-numberless range forms to `LIST`: `LIST -100`, `LIST 200-`
- Added `LINEB` / `LINEBF` to draw a rectangle / filled rectangle
- Added the `POINT(x, y)` function returning the color at a coordinate
- Added `CIRCLE` / `CIRCLEBF` to draw an ellipse / filled ellipse

## 0.1.1
- Added `--exec-mode {main,thread}` to switch the execution model (default main)
- main mode: the Pyxel main loop drives the VM each frame, with VSYNC frame-break active
- thread mode: the VM runs on a separate thread (same as 0.1.0); VSYNC is a no-op
- Added `--steps-per-frame` to set the statements run per frame in main mode
- Dropped "prototype" from the version label

## 0.1.0
- Major change: the BASIC VM now runs on a separate thread from Pyxel's render/input loop
- Split the interpreter, editor, and text screen into Pyxel-independent modules
- `VSYNC` is now a no-op kept for backward compatibility; only `VSYNC LIST` prints `FRAME BREAK: (none)`
- Added the execution-pacing startup options `--vm-cycle-steps` / `--vm-cycle-ms` / `--debug-throttle`, and `--gfx-queue-size`
- Changed `INKEY$` to a type-ahead model (returns buffered characters one at a time)

## 0.0.6
- Added `ELSE` support to `IF ... THEN`
- Added one-line multiple statements separated by `:`
- Added `RESTORE line`
- Fixed a bug where a negative number defined in `DATA` was not read correctly
- Unquoted text in `DATA` now reports a clear error
- Fixed a bug where `READ` could not assign into an array element such as `A(I)`


## 0.0.5
- Line-numbered, classic-style BASIC interpreter running on Pyxel.
- Full-screen editor with in-place editing (arrow keys, `Home`/`End`, insert/overtype, `Backspace`/`Delete`, logical-line reflow); `Enter` submits the logical line under the cursor.
- Control flow: `GOTO`, `GOSUB`/`RETURN`, `IF...THEN`, `FOR...NEXT`.
- Numeric and string variables, and multi-dimensional arrays.
- Built-in functions for strings, math, random numbers, and input.
- Point and line graphics plus a text screen; flexible frame control with `VSYNC` (sync points can be toggled per keyword).
- `DATA`/`READ`/`RESTORE`; `SAVE`/`LOAD` programs to files.
- Startup options (`--load`, `--workdir`, `--run`, `--showfps`, `--version`) and coded error messages.
- `Ctrl+C` interrupts a running program; `Esc` shows a quit-confirmation dialog.
- Bundled samples (`hello`, `count`, `graph`, `stick`, `meteo`, `alltest`) and a headless test suite.
