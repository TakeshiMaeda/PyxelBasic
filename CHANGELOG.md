# Changelog

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
