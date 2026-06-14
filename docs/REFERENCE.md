# PyxelBasic Language Reference

English | [日本語](REFERENCE.ja.md)

This document comprehensively describes the language features **currently implemented** in PyxelBasic.
Items not yet supported are summarized in "Not Yet Implemented / Limitations".

- Target version: prototype v0.0.5
- Runtime: Python 3.10+ with Pyxel
- Encoding: UTF-8 for both source and data files

---

## Table of Contents

1. [Overview](#1-overview)
2. [Startup and Screen](#2-startup-and-screen)
3. [Execution Model](#3-execution-model)
4. [Direct Commands](#4-direct-commands)
5. [Data Types](#5-data-types)
6. [Variables and Arrays](#6-variables-and-arrays)
7. [Operators](#7-operators)
8. [Statements](#8-statements)
9. [Built-in Functions](#9-built-in-functions)
10. [Frame Control (VSYNC)](#10-frame-control-vsync)
11. [Graphics and Text Screen](#11-graphics-and-text-screen)
12. [Keyboard Input](#12-keyboard-input)
13. [Error Messages](#13-error-messages)
14. [Not Yet Implemented / Limitations](#14-not-yet-implemented--limitations)
15. [Appendix: Color Palette](#15-appendix-color-palette)

---

## 1. Overview

PyxelBasic is a line-numbered, classic-style BASIC interpreter that runs on Pyxel.

- Line numbers are required. The program runs in line-number order.
- One statement per line (multi-statement `:` is not supported).
- Case-insensitive (`print` and `PRINT` are the same). Statement, function, and variable names are uppercased internally.
- Programs can be saved to and loaded from text files (`.bas`).

---

## 2. Startup and Screen

```
python main.py            start normally (edit mode)
python main.py hello      load samples/hello.bas on startup
```

- Screen size: 256 x 256 pixels, 60 FPS.
- Each character is 4 x 6 pixels. The text screen is **64 columns x 42 rows**.
- The screen is a full-screen editor: text written to it stays, and a single
  cursor is shared by output (`PRINT` flows from it, `LOCATE` moves it) and editing.

### 2.1 Screen Editing

Move the cursor anywhere with the arrow keys and edit in place; pressing Enter
submits the **logical line** under the cursor (a logical line may wrap across
several screen rows). This makes the classic edit-by-`LIST` workflow possible:
`LIST` the program, move the cursor up to a line, change part of it, and press
Enter to update that line.

| Key | Action |
|---|---|
| Arrow keys | Move the cursor |
| Printable keys | Type a character at the cursor |
| `Insert` | Toggle insert / overtype mode (the cursor shape changes: underline = insert, box = overtype) |
| `Backspace` | Delete the character before the cursor |
| `Delete` | Delete the character at the cursor |
| `Home` / `End` | Move to the start / end of the logical line |
| `Enter` | Submit the logical line under the cursor, then move down one logical line |
| `Esc` | Show a quit-confirmation dialog (`Y` quits, `N` / `Esc` cancels) |

---

## 3. Execution Model

### 3.1 Entering and Editing Lines

When Enter is pressed, the logical line under the cursor is handled according to
its content.

| Input | Behavior |
|---|---|
| Line number + statement (e.g. `10 PRINT "HI"`) | Stores a program line at that line number |
| Re-entering the same line number | Overwrites that line |
| Line number only (e.g. `10`) | Deletes that line |
| Statement / command only (no line number) | Executes immediately as a direct command (output flows from the cursor) |

When a numbered line is stored, its code is upper-cased (keywords, variable and
function names, operators). String literals (`"..."`) and the comment text after
`REM` are kept exactly as typed.

### 3.2 Run Model

- `RUN` executes the program in line-number order.
- Execution advances up to 800 statements per frame. When it reaches a frame-break statement such as `PRINT`, or a `VSYNC`, it ends execution for that frame and continues on the next frame (see [Frame Control](#10-frame-control-vsync)).
- When `INPUT` is reached, execution waits for input; it resumes after the user types a line and presses Enter.
- When `END` / `STOP` is reached, or the last line is passed, execution ends, `OK` is displayed, and it returns to edit mode.
- Pressing **Ctrl+C** during a run (or while waiting for `INPUT`) interrupts it: `BREAK in line <line>` is displayed and it returns to edit mode. The program is kept, so you can edit and re-run.
- If an error occurs during execution, `?ERROR <code> in line <line>: <message>` is displayed and execution stops (see Section 13 for codes).

---

## 4. Direct Commands

Management commands entered at the prompt without a line number.

| Command | Description |
|---|---|
| `RUN` | Run the program from the beginning |
| `LIST` | Display the whole program |
| `LIST n` | Display only line n |
| `LIST n,m` | Display lines n through m |
| `NEW` | Erase the entire program (also resets the frame-break settings) |
| `RENUM` | Renumber lines starting at 10 in steps of 10 |
| `RENUM start` | Renumber from `start` in steps of 10 |
| `RENUM start,step` | Renumber from `start` in steps of `step` |
| `SAVE "name"` | Save to `samples/name.bas` |
| `LOAD "name"` | Load `samples/name.bas` (discards the current program) |

- `RENUM` also updates line numbers that appear right after `GOTO` / `GOSUB` / `THEN`.
- If the `SAVE` / `LOAD` file name has no extension, `.bas` is appended. Files are stored in the `samples/` directory.
- Other statements (`PRINT`, assignments, etc.) can also be executed directly at the prompt.

---

## 5. Data Types

| Type | Description | Boolean |
|---|---|---|
| Number | Integers and reals are not distinguished (follows Python int / float) | True = -1, False = 0 |
| String | A sequence of characters, handled by variables/functions ending in `$` | - |

- Comparison and logical operations return **True = -1, False = 0**.
- A real number with an integer value is displayed as an integer (e.g. `4.0` → `4`).

---

## 6. Variables and Arrays

### 6.1 Variables

- **Numeric variable**: a name starting with a letter followed by alphanumerics (e.g. `A`, `X1`, `COUNT`). Default value is `0`.
- **String variable**: append `$` to the name (e.g. `A$`, `NAME$`). Default value is `""`.
- Assignment may use `LET` or omit it.

```basic
10 LET A = 10
20 B = A * 2
30 N$ = "HELLO"
```

- Assigning a string to a numeric variable is an error.
- Assigning a number to a string variable converts it to a string automatically.

### 6.2 Arrays

- Declared with `DIM`. Subscripts are **0-based**. `DIM A(10)` has 11 elements `A(0)`–`A(10)`.
- Multi-dimensional arrays are allowed. `DIM M(3,3)` has 16 elements `M(0,0)`–`M(3,3)`.
- Numeric arrays are initialized to `0`; string arrays (ending in `$`) to `""`.
- Referencing or assigning an array without `DIM` allocates it **implicitly** with size 10 (0–10) for each dimension.
- A subscript out of range is an error.
- A scalar variable and an array with the same name are treated as separate (`A` and `A(0)` are unrelated).

```basic
10 DIM A(5)
20 FOR I = 0 TO 5
30 A(I) = I * I
40 NEXT I
50 PRINT A(3)        ' prints 9
```

---

## 7. Operators

### 7.1 List

| Category | Operators |
|---|---|
| Arithmetic | `+` `-` `*` `/` `MOD` `^` |
| Comparison | `=` `<>` `<` `<=` `>` `>=` |
| Logical | `AND` `OR` `NOT` `XOR` |

### 7.2 Precedence (lowest to highest)

1. `OR` `XOR`
2. `AND`
3. `NOT` (unary)
4. Comparison `=` `<>` `<` `<=` `>` `>=`
5. `+` `-`
6. `*` `/` `MOD`
7. `^` (exponent, right-associative)
8. Unary `-` `+`
9. Number / string / `( )` / function / array reference / variable

### 7.3 Behavior of Each Operator

- `+`: addition for numbers. If either side is a string, both sides are stringified and concatenated.
- `-` `*`: numeric operations.
- `/`: real division (always a real result). Dividing by 0 is an error.
- `MOD`: integer remainder (both sides are integerized). Dividing by 0 is an error.
- `^`: exponentiation (right-associative). `2 ^ 3 ^ 2` means `2 ^ (3 ^ 2)`.
- Comparison: result is `-1` (true) / `0` (false). String-to-string comparison is allowed. Comparing a number with a string is an error.
- Logical: values are integerized and bitwise operations are applied (`AND`=bitwise AND, `OR`=bitwise OR, `XOR`=exclusive OR, `NOT`=bitwise NOT). Combined with the boolean values -1 / 0, they work as logical operators.

```basic
10 IF A > 0 AND A < 10 THEN PRINT "single digit"
20 PRINT 7 MOD 3          ' 1
30 PRINT 2 ^ 10           ' 1024
40 PRINT "AB" + "CD"      ' ABCD
```

---

## 8. Statements

### LET (assignment)
```
[LET] variable = expression
[LET] array(subscript, ...) = expression
```
`LET` is optional.

### PRINT
```
PRINT [expr] [ ; | , [expr] ] ...
```
- `;` (semicolon): concatenate with no separator.
- `,` (comma): advance to the next tab stop (tab width 8 columns), then print the next item.
- If the line ends with an expression, a newline is output. If it ends with `;` or `,`, no newline is output.

```basic
10 PRINT "X="; X          ' concatenate without separator, then newline
20 PRINT A, B             ' tab-separated
30 PRINT "WAIT";          ' no newline
```

### INPUT
```
INPUT ["prompt" ; | ,] variable [, variable ...]
```
- If the prompt string is omitted, `? ` is displayed.
- When multiple variables are given, the input is split by commas.
- Numeric variables receive a converted number (0 if conversion fails); string variables receive the text as is.

```basic
10 INPUT "NAME"; N$
20 INPUT "X,Y"; X, Y
```

### GOTO
```
GOTO line-number
```
Unconditional jump to the given line. The line number can be an expression (integerized).

### GOSUB / RETURN
```
GOSUB line-number
...
RETURN
```
`GOSUB` calls a subroutine; `RETURN` returns to the line after the call. Nesting is allowed.

### IF ... THEN
```
IF condition THEN line-number
IF condition THEN statement
```
- When the condition is true (non-zero), the part after `THEN` is executed.
- If only a line number follows `THEN`, it jumps to that line (implicit GOTO).
- If a statement follows `THEN`, that statement is executed.
- `ELSE` is **not supported**.

```basic
10 IF A = 0 THEN 100
20 IF A > 0 THEN PRINT "PLUS"
```

### FOR ... NEXT
```
FOR variable = start TO end [STEP increment]
...
NEXT [variable]
```
- The default increment when `STEP` is omitted is 1.
- The loop ends when the variable exceeds `end` for a positive increment, or falls below `end` for a negative increment.
- Specifying a variable on `NEXT` unwinds to that variable's loop (supports nested loops).

```basic
10 FOR I = 1 TO 10
20 PRINT I
30 NEXT I

40 FOR Y = 10 TO 0 STEP -2
50 PRINT Y
60 NEXT Y
```

### DIM
```
DIM array(size [, size ...]) [, array(...) ...]
```
Declares arrays (see [Arrays](#62-arrays)).

### REM
```
REM comment
```
Treats the rest of the line as a comment and ignores it.

### DATA / READ / RESTORE
```
DATA constant [, constant ...]
READ variable [, variable ...]
RESTORE
```
- `DATA` defines a list of numeric/string constants (all `DATA` lines are collected before execution).
- `READ` reads values from `DATA` in order and assigns them to variables.
- `RESTORE` resets the read position to the beginning.

```basic
10 DATA 10, 20, "HELLO"
20 READ A, B
30 READ C$
40 PRINT A + B; " "; C$    ' 30 HELLO
```

### CLS
```
CLS
```
Clears the text screen and graphics, and moves the cursor to the top-left.

### LOCATE
```
LOCATE X, Y
```
Sets the cursor position (column X, row Y, both 0-based). Clamped to the screen range.

### COLOR
```
COLOR color-number
```
Sets the color of text output from here on (see [Color Palette](#15-appendix-color-palette)).

### PSET
```
PSET (X, Y) [, color]
PSET (X, Y, color)
```
Draws a point. If the color is omitted, the current `COLOR` color is used.

### LINE
```
LINE (X1, Y1)-(X2, Y2) [, color]
```
Draws a line. If the color is omitted, the current `COLOR` color is used.

### RANDOMIZE
```
RANDOMIZE [seed]
```
Initializes the random number generator. If the seed is omitted, it is initialized from the current time, etc.

### VSYNC
Frame control statement. See [Frame Control](#10-frame-control-vsync).

### END / STOP
```
END
STOP
```
Ends program execution.

---

## 9. Built-in Functions

### 9.1 String Functions

| Function | Returns |
|---|---|
| `LEN(s)` | Length of string s |
| `LEFT$(s, n)` | Leftmost n characters of s |
| `RIGHT$(s, n)` | Rightmost n characters of s (empty if n ≤ 0) |
| `MID$(s, start [, len])` | len characters from position start (**1-based**) in s. To the end if len omitted |
| `CHR$(n)` | Character for character code n |
| `ASC(s)` | Character code of the first character of s (0 if empty) |
| `STR$(n)` | Stringified number n |
| `VAL(s)` | Numeric value of string s (0 if not convertible, real if it contains `.`) |

```basic
10 A$ = "PYXELBASIC"
20 PRINT LEFT$(A$, 5)      ' PYXEL
30 PRINT MID$(A$, 6, 3)    ' BAS
40 PRINT CHR$(65)          ' A
```

### 9.2 Math Functions

| Function | Returns |
|---|---|
| `ABS(n)` | Absolute value |
| `SGN(n)` | Sign (1 if n>0, 0 if n=0, -1 if n<0) |
| `INT(n)` | Largest integer ≤ n (floor, toward negative) |
| `FIX(n)` | Truncates the fractional part (toward zero) |
| `ROUND(n)` | Rounds to the nearest integer |
| `SIN(n)` `COS(n)` `TAN(n)` | Trigonometric functions (radians) |
| `ATN(n)` | Arctangent |
| `RAD(n)` | Degrees → radians |
| `DEG(n)` | Radians → degrees |
| `EXP(n)` | e to the power of n |
| `LOG(n)` | Natural logarithm |
| `LOG10(n)` | Common logarithm |
| `SQR(n)` | Square root |

> `INT` and `FIX` differ for negative numbers. `INT(-1.5)` is `-2`; `FIX(-1.5)` is `-1`.

### 9.3 Random Numbers

| Function | Returns |
|---|---|
| `RND` | A real in [0, 1) |
| `RND(n)` | A real in [0, n) |

- For an integer random number, use `INT(RND(n))` to get 0 to n-1.
- Seed it with the `RANDOMIZE` statement.

### 9.4 Input Functions

| Function | Returns |
|---|---|
| `INKEY$` | The character typed in the most recent frame (empty if none) |
| `STICK(n)` | The direction-key state as a bit sum (see below) |
| `BUTTON(n)` | 1 if button n is pressed, otherwise 0 |

`STICK` return value (multiple directions are summed):

| Direction | Value |
|---|---|
| Up | 1 |
| Down | 2 |
| Left | 4 |
| Right | 8 |

> In the current implementation, the argument n of `STICK(n)` is ignored, and it always returns the arrow-key state.

`BUTTON(n)` key assignments:

| n | Key |
|---|---|
| 0 | Z |
| 1 | X |
| 2 | C |
| 3 | Space |

```basic
10 IF STICK(0) AND 1 THEN Y = Y - 1     ' up key moves up
20 IF BUTTON(0) THEN PRINT "Z PRESSED"
```

---

## 10. Frame Control (VSYNC)

PyxelBasic runs at 60 FPS. By ending execution for the current frame at a specified statement/function and continuing on the next frame, it avoids missing screen updates and input.

### 10.1 How Frame Breaks Work

- Executing (a statement) or evaluating (a function) a frame-break keyword breaks the frame there.
- Keywords that are frame-break targets by default: **`PRINT` `PSET` `LINE` `STICK` `BUTTON`**.
- The set of targets can be changed at runtime with the `VSYNC` command.

### 10.2 VSYNC Command

| Syntax | Behavior |
|---|---|
| `VSYNC` | Break the frame here (an explicit sync point) |
| `VSYNC keyword ON` | Add the keyword to the frame-break targets |
| `VSYNC keyword OFF` | Remove the keyword from the frame-break targets |
| `VSYNC RESET` | Reset the frame-break settings to their initial state |
| `VSYNC CLEAR` | Remove every automatic frame-break target (afterwards only an explicit `VSYNC` breaks a frame) |
| `VSYNC LIST` | List the current frame-break targets |

- An invalid keyword (an undefined word) is an error.
- Settings persist across runs and return to the initial state with `VSYNC RESET` or `NEW`.
- Writing `VSYNC RESET` at the start of a program lets it run with the default settings, unaffected by prior changes.

```basic
10 VSYNC PRINT OFF       ' don't break on PRINT (fast batch output)
20 FOR I = 1 TO 100
30 PRINT I
40 NEXT I
50 VSYNC RESET
```

In a game main loop, since `PSET` and `STICK` are frame-break targets, it runs frame by frame even without an explicit `VSYNC`.

---

## 11. Graphics and Text Screen

### 11.1 Coordinate System

- The top-left of the screen is `(0, 0)`. X increases to the right, Y increases downward.
- The screen size is 256 x 256 pixels.

### 11.2 Graphics

- Drawing statements: `PSET`, `LINE`.
- Graphics are drawn to a dedicated layer and retained until `CLS` (no need to re-run every frame).

### 11.3 Text Output and Control Characters

- `PRINT` outputs characters to the text screen. When it reaches the bottom edge, the screen scrolls upward.
- Including the following control characters (character codes) in a string takes effect on output.

| Character code | How to get it | Effect |
|---|---|---|
| Newline (10) | `CHR$(10)` | Newline (to the start of the next line) |
| Carriage return (13) | `CHR$(13)` | Return to the start of the line (no newline) |
| Tab (9) | `CHR$(9)` | Move to the next tab stop (tab width 8 columns) |

> Backslash escapes such as `\n` `\l` `\cN` are not supported. Use `CHR$(10)` for a newline.

---

## 12. Keyboard Input

| Purpose | Method |
|---|---|
| One-line input | `INPUT` (confirmed with Enter) |
| Real-time single character | `INKEY$` (empty if no key is pressed) |
| Direction keys | `STICK(n)` |
| Buttons | `BUTTON(n)` (Z / X / C / Space) |

For edit-mode key operations (cursor movement, insert / overtype toggle, Home/End, Backspace/Delete, submitting a line with Enter, etc.), see [Screen Editing](#21-screen-editing).

---

## 13. Error Messages

Errors during execution are shown as `?ERROR <code> in line <line>: <message>`, and during direct execution as `?ERROR <code>: <message>`. Each error has a numeric code, grouped by hundreds: 1xx syntax/parse, 2xx type, 3xx runtime/control flow, 4xx array/data, 5xx file/command. Codes and messages are defined in one place, `pyxelbasic/errors.py`.

| Code | Message | Common cause |
|---|---|---|
| 101 | `Syntax error` | A line that is not a valid statement (e.g. arbitrary text, or an implied assignment with no `=`) |
| 102 | `Unsupported statement: x` | An unimplemented statement keyword |
| 103 | `Invalid expression` | A syntax error in an expression |
| 104 | `Expected '('` | A `(` was required |
| 105 | `Expected ')'` | A `)` was required |
| 106 | `Expected '='` | No `=` in an assignment |
| 107 | `Assignment target is not a variable` | Left side of `=` is not a variable |
| 108 | `Expected THEN` | No `THEN` in an `IF` |
| 109 | `Nothing after THEN` | `IF ... THEN` with nothing after `THEN` |
| 110 | `Missing FOR variable` | `FOR` without a loop variable |
| 111 | `Expected '=' in FOR` | Syntax error in a `FOR` |
| 112 | `Expected TO in FOR` | Syntax error in a `FOR` |
| 113 | `Invalid DIM syntax` | Syntax error in a `DIM` |
| 114 | `Invalid LOCATE syntax` | Syntax error in a `LOCATE` |
| 115 | `Invalid LINE syntax ('-' required)` | Syntax error in a `LINE` |
| 116 | `VSYNC: keyword required` | A `VSYNC` form needs a keyword |
| 117 | `VSYNC: ON or OFF required` | `VSYNC <word>` needs `ON`/`OFF` |
| 118 | `Unterminated string` | A `"` is not closed |
| 119 | `Invalid character: 'x'` | An uninterpretable character |
| 120 | `Invalid comparison operator` | Internal: bad comparison operator |
| 201 | `Number required` | A string was used in a numeric operation |
| 202 | `Type mismatch in comparison` | A number was compared with a string |
| 203 | `Cannot assign string to numeric variable: name` | Type mismatch on assignment |
| 301 | `Division by zero` | Division by 0 (`/` or `MOD`) |
| 302 | `Line n not found` | The jump target line does not exist |
| 303 | `RETURN without GOSUB` | An extra `RETURN` |
| 304 | `NEXT without FOR` | An extra `NEXT` |
| 305 | `NEXT name without FOR` | `NEXT var` with no matching `FOR` |
| 401 | `Subscript out of range: name` | Array subscript out of range |
| 402 | `Out of DATA` | `DATA` has been exhausted |
| 501 | `SAVE requires a file name` | `SAVE` without a file name |
| 502 | `LOAD requires a file name` | `LOAD` without a file name |

`?FILE NOT FOUND "name"` is a separate notice printed by `LOAD` when the file is missing; it is not a coded error.

---

## 14. Not Yet Implemented / Limitations

Items not yet supported in the current prototype:

- **Control structures**: `ELSE` (the false branch of `IF`), multi-statement lines (`:`), `WHILE`/`DO`
- **Graphics**: `BOX`, `CIRCLE`, `FILLCIRCLE`, `SPRITE`, `SPRITEDEF`, `PCG`, `PALETTE`
- **Sound**: `PLAY` (MML), `MUSIC`
- **String escapes**: `\n` `\l` `\t` `\cN`, retro-style newline via `CHR$(12)`, the `\cN` escape for `COLOR`
- **Other**: The PyxelBasic standard font is ASCII-only. Japanese display is not supported.

---

## 15. Appendix: Color Palette

Colors are specified by Pyxel's standard 16-color palette (numbers 0 to 15). Representative colors:

| No. | Color | No. | Color |
|---|---|---|---|
| 0 | Black | 8 | Red |
| 1 | Dark blue | 9 | Orange |
| 2 | Purple | 10 | Yellow |
| 3 | Green | 11 | Yellow-green |
| 4 | Brown | 12 | Light blue |
| 5 | Dark blue-gray | 13 | Gray |
| 6 | Light blue-gray | 14 | Pink |
| 7 | White | 15 | Peach |

> The actual colors follow the version and palette settings of the Pyxel you are using.

---

## Appendix: Sample Programs

The `samples/` directory includes the following.

| File | Description |
|---|---|
| `hello.bas` | HELLO WORLD |
| `count.bas` | Using FOR/NEXT and expressions |
| `graph.bas` | Graphics with lines and points |
| `stick.bas` | Move a dot with the arrow keys (STICK input) |
