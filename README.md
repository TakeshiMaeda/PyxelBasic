# PyxelBasic

English | [日本語](README.ja.md)

A line-numbered, classic-style BASIC interpreter that runs on [Pyxel](https://github.com/kitao/pyxel).
It recreates the feel of retro BASIC while letting you use Pyxel's screen, graphics, and input.

> This is a prototype (v0.0.5).

## Features

- Full-screen editor: move the cursor anywhere and edit lines in place (insert / overtype, Home/End, Backspace/Delete)
- Line-numbered program editing (insert / overwrite / delete, `LIST` / `RENUM`)
- Control structures such as `GOTO` / `GOSUB` / `IF...THEN` / `FOR...NEXT`
- Numeric and string variables, and multi-dimensional arrays
- Built-in functions for strings, math, random numbers, and input
- Point and line graphics plus a text screen
- Flexible frame control with `VSYNC` (sync points can be toggled per keyword)
- Save / load programs to files (`SAVE` / `LOAD`)

## Requirements

- Python 3.10 or later
- [Pyxel](https://github.com/kitao/pyxel)

```
pip install pyxel
```

## Installation

```
git clone https://github.com/TakeshiMaeda/PyxelBasic.git
cd PyxelBasic
```

## Usage

```
python main.py                      start normally (edit mode)
python main.py hello                load hello.bas on startup (shorthand)
python main.py --load hello         same as above
python main.py --load stick --run   load and run automatically
python main.py --workdir ./mybas    set the SAVE/LOAD directory
python main.py --showfps            show the frame rate in the title bar
python main.py --version            print the version and exit
python main.py --help               show help and exit
```

Options:

- `--load FILE` program to load on startup.
- `--workdir DIR` directory used by SAVE/LOAD. Fixed at startup; it cannot be
  changed from inside the interpreter. Defaults to the bundled `samples/`.
- `--run` run the loaded program automatically (requires `--load`).
- `--showfps` show the real frame rate in the window title bar.
- `--version` print the version and exit without opening a window.
- `-h`, `--help` show the help message and exit.

On startup you get a full-screen editor. Type a line anywhere and press Enter to
submit the logical line under the cursor.

```
10 PRINT "HELLO, WORLD!"
20 FOR I = 1 TO 3
30 PRINT "COUNT="; I
40 NEXT I
RUN
```

- A line entered with a line number is added to the program (re-enter the same number to overwrite; enter the number alone to delete).
- Move the cursor freely with the arrow keys and edit in place: `Insert` toggles insert / overtype, `Home` / `End` jump to the start / end of the line, and `Backspace` / `Delete` remove characters. To fix an existing line, `LIST` it, move the cursor onto the line, change it, and press Enter.
- `RUN` to execute, `LIST` to list, `NEW` to clear everything. Press `Ctrl+C` during a run to interrupt it and return to edit mode.
- `SAVE "name"` / `LOAD "name"` save and load under the `samples/` directory.

## Samples

| File | Description |
|---|---|
| `samples/hello.bas` | HELLO WORLD |
| `samples/count.bas` | Using FOR/NEXT and expressions |
| `samples/graph.bas` | Graphics with lines and points |
| `samples/stick.bas` | Move a dot with the arrow keys (STICK input) |
| `samples/meteo.bas` | Dodge meteors falling from the top with the arrow keys (no collision detection) |

Example of loading and running:

```
LOAD "graph"
RUN
```

## Language Specification

For the **complete reference** of implemented statements, functions, and operators, see [docs/REFERENCE.md](docs/REFERENCE.md).

Main elements:

- Statements: `PRINT` `INPUT` `LET` `GOTO` `GOSUB`/`RETURN` `IF...THEN` `FOR...NEXT` `DIM` `DATA`/`READ`/`RESTORE` `CLS` `LOCATE` `COLOR` `PSET` `LINE` `RANDOMIZE` `VSYNC` `END`/`STOP`
- Functions: `LEN` `LEFT$` `RIGHT$` `MID$` `CHR$` `ASC` `STR$` `VAL` / `ABS` `SGN` `INT` `FIX` `ROUND` `SIN` `COS` `TAN` `ATN` `RAD` `DEG` `EXP` `LOG` `LOG10` `SQR` / `RND` `INKEY$` `STICK` `BUTTON`
- Operators: `+` `-` `*` `/` `MOD` `^` / `=` `<>` `<` `<=` `>` `>=` / `AND` `OR` `NOT` `XOR`

## Project Layout

```
PyxelBasic/
├── main.py                launcher
├── pyxelbasic/
│   ├── interpreter.py     interpreter core (lexer, expression evaluator, execution engine; Pyxel-independent)
│   ├── console.py         Pyxel text console and graphics surface
│   └── app.py             integration of edit/run/input modes and the main loop
├── samples/               sample programs (.bas)
├── tests/
│   └── test_core.py       headless tests for the core
└── docs/
    └── REFERENCE.md       complete language reference
```

## Development & Tests

The interpreter core does not depend on Pyxel, so it can be tested headlessly.

```
python tests/test_core.py
```

This covers lexing, expression evaluation, control structures, arrays, string functions, INPUT, graphics commands, frame control, RENUM, and more.

## Not Yet Implemented (planned)

- Graphics: `BOX` / `CIRCLE` / `FILLCIRCLE` / `SPRITE` / `SPRITEDEF` / `PCG` / `PALETTE`
- Sound: `PLAY` (MML)
- Control structures: `ELSE`, multi-statement lines (`:`)
- String escapes (`\n`, `\cN`, etc.), Japanese fonts

For details, see "Not Yet Implemented" in [docs/REFERENCE.md](docs/REFERENCE.md).

## License

Released under the [MIT License](LICENSE).

Copyright (c) 2025-2026 Takeshi Maeda (SPSoft)

## Acknowledgments

This project runs on [Pyxel](https://github.com/kitao/pyxel) (MIT License, © Takashi Kitao).
Thank you for publishing such a wonderful retro game engine.

PyxelBasic is an **unofficial** project that uses Pyxel and is not affiliated with Pyxel or its developer.
The name "Pyxel" belongs to its original author.
