# Changelog

English | [日本語](CHANGELOG.ja.md)

All notable changes to PyxelBasic are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is a `0.0.x` prototype, breaking changes may occur between releases.

## [Unreleased]

### Added
- `IF ... THEN ... ELSE ...`: the false branch of `IF` is now supported. Each
  side may be a line number (implicit `GOTO`) or one or more statements.
- Multiple statements per line separated by `:`. The program counter is
  statement-granular during `RUN`, so a one-line `FOR ... : ... : NEXT` loop and
  continuing a line after `GOSUB` returns (`GOSUB 100 : PRINT "BACK"`) both work.
- `samples/meteo.bas`: dodge meteors falling from the top with the arrow keys
  (no collision detection).

### Changed
- Documentation: rewrote the READMEs for the full-screen editor (dropped the
  obsolete `]` prompt; documented in-place editing and `Ctrl+C` interrupt) and
  added the editor to the feature list. Listed every bundled sample.

### Known limitations
- One-line `FOR`/`NEXT` loops do not work in direct mode (only during `RUN`).
- For a nested `IF ... THEN IF ... THEN ... ELSE ...` on one line, which `IF` the
  `ELSE` binds to is not guaranteed (best-effort).

## [0.0.5] - 2026-06-14

### Added
- `--showfps` option: show the window's real frame rate in the title bar
  (updated about twice a second). No measurement overhead when omitted.

### Changed
- Upper-case the code part of a line on entry, while keeping string literals and
  `REM` comment text as typed.
- `RENUM` keeps `REM` lines.
- Renamed `samples/game.bas` to `samples/stick.bas`.

## [0.0.4] - 2026-06-14

### Added
- `Ctrl+C` interrupts a running program (or an `INPUT` wait): `BREAK in line N`
  is shown and control returns to edit mode with the program intact.
- `Esc` opens a quit-confirmation dialog (`Y` quits, `N`/`Esc` cancels); Pyxel's
  built-in Esc-to-quit is disabled.
- `VSYNC CLEAR` drops every automatic frame-break target (only an explicit
  `VSYNC` breaks afterwards).

### Changed
- Optimized text rendering: text is drawn from a baked image with a dirty flag,
  so a normal frame is two `blt`s instead of thousands of per-character calls.
  The per-frame cost stays constant as the screen fills.

### Fixed
- `MOD` by a fraction (`0 < |b| < 1`) integerized the divisor to 0 and crashed
  with a Python `ZeroDivisionError`; it now raises a BASIC division error.

## [0.0.3] - 2026-06-14

### Added
- Full-screen screen editor: a single cursor is shared by output and editing
  (`PRINT` flows from it, `LOCATE` moves it). Arrow keys, `Home`/`End`,
  insert/overtype (toggled with `Insert`), `Backspace` and `Delete` edit in
  place; logical lines wrap and reflow. `Enter` submits the logical line under
  the cursor. The `]` prompt was removed.
- Startup options via `argparse` in `main.py`: `--load`, `--workdir` (fixed
  SAVE/LOAD directory), `--run`, `--version`, plus a positional shorthand. The
  version string lives in `pyxelbasic/version.py` and `App` is imported lazily,
  so `--version` needs neither Pyxel nor a display.
- Coded error system: every message lives in `pyxelbasic/errors.py` as a single
  source of truth, grouped by hundreds and shown in the output.
- `samples/alltest.bas`: a self-checking program that exercises every statement
  and function; it is also run from the test suite.

### Changed
- A bare line that is not a valid statement reports a syntax error instead of
  `Expected '='`.

## [0.0.1] - 2026-06-14

### Added
- Initial prototype of the line-numbered BASIC interpreter on Pyxel
  (work in progress).
- Data-driven keyword dispatch: reserved words map to handler methods in
  `pyxelbasic/keywords.py` as the single source of truth.

[Unreleased]: https://github.com/TakeshiMaeda/PyxelBasic/compare/v0.0.5...HEAD
[0.0.5]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.5
[0.0.4]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.4
[0.0.3]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.3
[0.0.1]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.1
