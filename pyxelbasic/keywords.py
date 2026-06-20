# -*- coding: utf-8 -*-
"""Reserved-word definitions for PyxelBasic.

Single source of truth for the language's keywords. Each keyword appears exactly
once here, mapped to the name of the handler method that implements it; the
keyword *sets* (STATEMENTS / FUNCTIONS / KEYWORDS) and the math table are derived
from these maps. Adding a keyword means editing one line in one place.

Handlers are wired by method name (a string), not by direct reference, because
this module is imported by interpreter.py before its classes exist. interpreter.py
asserts at import time that every named handler actually exists (a fail-fast,
interface-style consistency check).
"""

import math


# Statement keyword -> Interpreter method name.
STATEMENT_HANDLERS = {
    "PRINT":     "_do_print",
    "INPUT":     "_do_input",
    "LET":       "_do_let",
    "GOTO":      "_do_goto",
    "GOSUB":     "_do_gosub",
    "RETURN":    "_do_return",
    "IF":        "_do_if",
    "FOR":       "_do_for",
    "NEXT":      "_do_next",
    "DIM":       "_do_dim",
    "REM":       "_do_noop",
    "DATA":      "_do_noop",
    "RESTORE":   "_do_restore",
    "CLS":       "_do_cls",
    "LOCATE":    "_do_locate",
    "COLOR":     "_do_color",
    "PSET":      "_do_pset",
    "LINE":      "_do_line",
    "LINEB":     "_do_lineb",
    "LINEBF":    "_do_linebf",
    "CIRCLE":    "_do_circle",
    "CIRCLEBF":  "_do_circlebf",
    "END":       "_do_end",
    "STOP":      "_do_end",
    "READ":      "_do_read",
    "RANDOMIZE": "_do_randomize",
    "VSYNC":     "_do_vsync",
}

# Function keyword -> (Evaluator method name, raw).
# raw=True : the handler parses its own arguments (receives only the Evaluator).
# raw=False: the arglist is pre-evaluated; the handler receives (evaluator, args).
FUNCTION_HANDLERS = {
    "RND":    ("_fn_rnd",    True),
    "INKEY$": ("_fn_inkey",  True),
    "LEN":    ("_fn_len",    False),
    "LEFT$":  ("_fn_left",   False),
    "RIGHT$": ("_fn_right",  False),
    "MID$":   ("_fn_mid",    False),
    "CHR$":   ("_fn_chr",    False),
    "ASC":    ("_fn_asc",    False),
    "STR$":   ("_fn_str",    False),
    "VAL":    ("_fn_val",    False),
    "STICK":  ("_fn_stick",  False),
    "BUTTON": ("_fn_button", False),
    "POINT":  ("_fn_point",  False),
}

# Single-argument math functions: keyword -> callable applied to one number.
MATH1 = {
    "SIN": math.sin, "COS": math.cos, "TAN": math.tan, "ATN": math.atan,
    "RAD": math.radians, "DEG": math.degrees,
    "EXP": math.exp, "LOG": math.log, "LOG10": math.log10, "SQR": math.sqrt,
    "ABS": abs, "INT": math.floor, "FIX": math.trunc, "ROUND": round,
    "SGN": lambda v: (v > 0) - (v < 0),
}

# Immediate (direct) mode commands (handled by App, not the interpreter core).
DIRECT = {"RUN", "LIST", "NEW", "RENUM", "SAVE", "LOAD"}

# Syntactic keywords (neither operators nor statements).
SYNTAX = {"THEN", "ELSE", "TO", "STEP"}

# Word-form operators.
WORD_OPS = {"MOD", "AND", "OR", "NOT", "XOR"}

# --- Abstract input key identifiers (platform-independent) ---
# The frontend (Pyxel side) translates real device keys into these IDs and emits
# them as input events; the VM-side input layer derives STICK/BUTTON/INKEY$ from
# the resulting event stream. Defined here so the keys live in one place, the
# same way reserved words do (the Pyxel key mapping itself stays in the frontend).
KEY_UP = "UP"
KEY_DOWN = "DOWN"
KEY_LEFT = "LEFT"
KEY_RIGHT = "RIGHT"
KEY_HOME = "HOME"
KEY_END = "END"
KEY_INSERT = "INSERT"
KEY_DELETE = "DELETE"
KEY_BACKSPACE = "BACKSPACE"
KEY_RETURN = "RETURN"
KEY_BTN0 = "BTN0"
KEY_BTN1 = "BTN1"
KEY_BTN2 = "BTN2"
KEY_BTN3 = "BTN3"

# STICK direction bits (numpad style) and BUTTON order, derived from key state.
STICK_BITS = ((KEY_UP, 1), (KEY_DOWN, 2), (KEY_LEFT, 4), (KEY_RIGHT, 8))
BUTTON_KEYS = (KEY_BTN0, KEY_BTN1, KEY_BTN2, KEY_BTN3)

# --- Initial frame-break configuration (main-driven execution mode) ---
# When any reserved word listed here is executed (as a statement) or evaluated
# (as a function), the current frame is cut off and resumed on the next frame.
# This is only used by the main-driven execution mode (VSYNC enabled); the
# threaded mode runs with an empty frame-break set so VSYNC stays a no-op. At
# runtime the set can be adjusted with VSYNC <word> ON|OFF (Interpreter.frame_break).
FRAME_BREAK = {
    "PRINT",            # screen output
    "PSET", "LINE",     # drawing statements
    "LINEB", "LINEBF",  # rectangle drawing
    "CIRCLE", "CIRCLEBF",  # circle / ellipse drawing
    "STICK", "BUTTON",  # input polling (functions)
}

# --- Derived sets (generated from the maps above; do not hand-edit) ---
STATEMENTS = set(STATEMENT_HANDLERS)
FUNCTIONS = set(FUNCTION_HANDLERS) | set(MATH1)
KEYWORDS = STATEMENTS | DIRECT | FUNCTIONS | SYNTAX
