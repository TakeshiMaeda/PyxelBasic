# Changelog

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
