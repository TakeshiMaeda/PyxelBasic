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

### Known limitations
- One-line `FOR`/`NEXT` loops do not work in direct mode (only during `RUN`).
- For a nested `IF ... THEN IF ... THEN ... ELSE ...` on one line, which `IF` the
  `ELSE` binds to is not guaranteed (best-effort).

## [0.0.5] - 2026-06-14

Initial public release.

- Line-numbered, classic-style BASIC interpreter running on Pyxel.
- Full-screen editor with in-place editing (arrow keys, `Home`/`End`,
  insert/overtype, `Backspace`/`Delete`, logical-line reflow); `Enter` submits
  the logical line under the cursor.
- Control flow: `GOTO`, `GOSUB`/`RETURN`, `IF...THEN`, `FOR...NEXT`.
- Numeric and string variables, and multi-dimensional arrays.
- Built-in functions for strings, math, random numbers, and input.
- Point and line graphics plus a text screen; flexible frame control with
  `VSYNC` (sync points can be toggled per keyword).
- `DATA`/`READ`/`RESTORE`; `SAVE`/`LOAD` programs to files.
- Startup options (`--load`, `--workdir`, `--run`, `--showfps`, `--version`) and
  coded error messages.
- `Ctrl+C` interrupts a running program; `Esc` shows a quit-confirmation dialog.
- Bundled samples (`hello`, `count`, `graph`, `stick`, `meteo`, `alltest`) and a
  headless test suite.

[Unreleased]: https://github.com/TakeshiMaeda/PyxelBasic/compare/v0.0.5...HEAD
[0.0.5]: https://github.com/TakeshiMaeda/PyxelBasic/releases/tag/v0.0.5
