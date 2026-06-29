# -*- coding: utf-8 -*-
"""PyxelBasic interpreter core.

Bundles the lexer, expression evaluator and execution engine.
Screen I/O goes through the IOTarget interface, so this module does not
depend on Pyxel (easy to test or to swap the console out).
"""

import math
import random

from .errors import BasicError, Err
from .keywords import (
    STATEMENT_HANDLERS, FUNCTION_HANDLERS, MATH1,
    KEYWORDS, WORD_OPS, FUNCTIONS, FRAME_BREAK,
)


# Reserved-word definitions (keyword sets, handler maps, the math table and the
# initial frame-break set) live in keywords.py and are imported at the top of
# this module. Statements/functions are dispatched by looking up the handler
# method name there and resolving it with getattr.


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

class HexInt(int):
    """An integer that was written as an &H hex literal.

    Behaves exactly like int for evaluation, arithmetic and PRINT (so &HFF is
    just 255 everywhere), but remembers the original hex digits so detokenize()
    can round-trip it back to &H form. RENUM rewrites a line through
    tokenize()/detokenize(); without this, &HFF on a renumbered line would come
    back as the decimal 255.
    """

    def __new__(cls, digits):
        obj = super().__new__(cls, int(digits, 16))
        obj.digits = digits
        return obj


def tokenize(src):
    """Convert one line into a token list.

    A token is a (kind, value) tuple.
    Kinds: NUM / STR / VAR / KW / OP / LP / RP / COMMA / SEMI / COLON
    """
    tokens = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        # Skip whitespace
        if c in " \t":
            i += 1
            continue
        # String literal
        if c == '"':
            j = i + 1
            buf = []
            while j < n and src[j] != '"':
                buf.append(src[j])
                j += 1
            if j >= n:
                raise BasicError(Err.UNTERMINATED_STRING)
            tokens.append(("STR", "".join(buf)))
            i = j + 1
            continue
        # Hex literal: &H followed by hex digits (classic BASIC style)
        if c == "&" and i + 1 < n and src[i + 1] in "Hh":
            j = i + 2
            buf = []
            while j < n and src[j] in "0123456789abcdefABCDEF":
                buf.append(src[j])
                j += 1
            if not buf:
                raise BasicError(Err.INVALID_HEX_LITERAL)
            tokens.append(("NUM", HexInt("".join(buf))))
            i = j
            continue
        # Number
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i
            buf = []
            seen_dot = False
            while j < n and (src[j].isdigit() or (src[j] == "." and not seen_dot)):
                if src[j] == ".":
                    seen_dot = True
                buf.append(src[j])
                j += 1
            text = "".join(buf)
            val = float(text) if seen_dot else int(text)
            tokens.append(("NUM", val))
            i = j
            continue
        # Identifier (variable / reserved word / function)
        if c.isalpha():
            j = i
            buf = []
            while j < n and src[j].isalnum():
                buf.append(src[j])
                j += 1
            # A trailing $ is part of the name
            if j < n and src[j] == "$":
                buf.append("$")
                j += 1
            word = "".join(buf)
            up = word.upper()
            i = j
            if up == "REM":
                # Everything after REM is a comment until end of line
                break
            if up in KEYWORDS:
                tokens.append(("KW", up))
            elif up in WORD_OPS:
                tokens.append(("OP", up))
            else:
                tokens.append(("VAR", up))
            continue
        # Two-character operators
        two = src[i:i + 2]
        if two in ("<=", ">=", "<>"):
            tokens.append(("OP", two))
            i += 2
            continue
        # One-character operators / symbols
        if c in "+-*/^=<>":
            tokens.append(("OP", c))
            i += 1
            continue
        if c == "(":
            tokens.append(("LP", c)); i += 1; continue
        if c == ")":
            tokens.append(("RP", c)); i += 1; continue
        if c == ",":
            tokens.append(("COMMA", c)); i += 1; continue
        if c == ";":
            tokens.append(("SEMI", c)); i += 1; continue
        if c == ":":
            tokens.append(("COLON", c)); i += 1; continue
        raise BasicError(Err.INVALID_CHAR, c)
    return tokens


def split_statements(toks):
    """Split a line's token list into separate statements at top-level COLON.

    Most ':' tokens are statement separators. Two keywords instead consume the
    rest of the line as a single statement (no further splitting):
      IF   - its THEN / ELSE / ':' clauses are handled inside _do_if.
      DATA - reads to end of line (matches _collect_data).
    (REM never reaches here: the tokenizer stops at REM and emits no COLON.)

    Empty statements (a leading / trailing ':' or '::') are skipped.
    """
    stmts = []
    cur = []
    i = 0
    n = len(toks)
    while i < n:
        kind, val = toks[i]
        if not cur and kind == "KW" and val in ("IF", "DATA"):
            # This statement takes the entire remainder of the line.
            stmts.append(toks[i:])
            return stmts
        if kind == "COLON":
            if cur:
                stmts.append(cur)
                cur = []
            i += 1
            continue
        cur.append(toks[i])
        i += 1
    if cur:
        stmts.append(cur)
    return stmts


def normalize_line(text):
    """Upper-case the code part of a source line for storage.

    Keywords, variable / function names and operators become upper-case, while
    string literals ("...") and the comment text after REM are kept exactly as
    typed. Spacing is preserved (this is a source scan, not tokenize/detokenize).
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            # Copy the string literal verbatim, including the quotes.
            j = i + 1
            while j < n and text[j] != '"':
                j += 1
            if j < n:
                j += 1            # include the closing quote
            out.append(text[i:j])
            i = j
            continue
        if c.isalpha():
            j = i
            while j < n and (text[j].isalnum() or text[j] == "$"):
                j += 1
            word = text[i:j]
            if word.upper() == "REM":
                # Keep the comment after REM exactly as typed.
                out.append("REM")
                out.append(text[j:])
                return "".join(out)
            out.append(word.upper())
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


def basic_str(v):
    """BASIC-style stringification. A float with an integer value prints as an integer."""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "-1" if v else "0"
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return repr(v)
    return str(v)


def to_bool_num(b):
    """Convert a Python boolean to a BASIC truth value (-1/0)."""
    return -1 if b else 0


# ---------------------------------------------------------------------------
# Expression evaluation (recursive descent)
# ---------------------------------------------------------------------------

class Evaluator:
    """Evaluates part of a token list as an expression.

    Advances pos while evaluating; the caller can read the resulting pos.
    """

    def __init__(self, tokens, interp, start=0):
        self.toks = tokens
        self.pos = start
        self.interp = interp

    def peek(self):
        if self.pos < len(self.toks):
            return self.toks[self.pos]
        return (None, None)

    def advance(self):
        t = self.peek()
        self.pos += 1
        return t

    def expect_rp(self):
        if self.peek()[0] != "RP":
            raise BasicError(Err.EXPECTED_RPAREN)
        self.advance()

    # From lowest precedence downward
    def parse(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek() == ("OP", "OR") or self.peek() == ("OP", "XOR"):
            op = self.advance()[1]
            right = self.parse_and()
            a, b = int(self._num(left)), int(self._num(right))
            left = (a | b) if op == "OR" else (a ^ b)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek() == ("OP", "AND"):
            self.advance()
            right = self.parse_not()
            left = int(self._num(left)) & int(self._num(right))
        return left

    def parse_not(self):
        if self.peek() == ("OP", "NOT"):
            self.advance()
            v = self.parse_not()
            return ~int(self._num(v))
        return self.parse_compare()

    def parse_compare(self):
        left = self.parse_add()
        ops = {"=", "<>", "<", "<=", ">", ">="}
        while self.peek()[0] == "OP" and self.peek()[1] in ops:
            op = self.advance()[1]
            right = self.parse_add()
            left = self._compare(left, op, right)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek()[0] == "OP" and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            right = self.parse_mul()
            if op == "+":
                # Allow string concatenation too
                if isinstance(left, str) or isinstance(right, str):
                    left = basic_str(left) + basic_str(right)
                else:
                    left = left + right
            else:
                left = self._num(left) - self._num(right)
        return left

    def parse_mul(self):
        left = self.parse_pow()
        while self.peek()[0] == "OP" and self.peek()[1] in ("*", "/", "MOD"):
            op = self.advance()[1]
            right = self.parse_pow()
            a, b = self._num(left), self._num(right)
            if op == "*":
                left = a * b
            elif op == "/":
                if b == 0:
                    raise BasicError(Err.DIVISION_BY_ZERO)
                left = a / b
            else:  # MOD (both sides are integerized)
                ib = int(b)
                if ib == 0:   # also catches 0 < |b| < 1, where int(b) == 0
                    raise BasicError(Err.DIVISION_BY_ZERO)
                left = int(a) % ib
        return left

    def parse_pow(self):
        left = self.parse_unary()
        if self.peek() == ("OP", "^"):
            self.advance()
            right = self.parse_pow()  # right associative
            return self._num(left) ** self._num(right)
        return left

    def parse_unary(self):
        if self.peek() == ("OP", "-"):
            self.advance()
            return -self._num(self.parse_unary())
        if self.peek() == ("OP", "+"):
            self.advance()
            return self._num(self.parse_unary())
        return self.parse_primary()

    def parse_primary(self):
        t = self.peek()
        kind = t[0]
        if kind == "NUM" or kind == "STR":
            self.advance()
            return t[1]
        if kind == "LP":
            self.advance()
            v = self.parse()
            self.expect_rp()
            return v
        if kind == "KW" and t[1] in FUNCTIONS:
            return self.parse_function(t[1])
        if kind == "VAR":
            self.advance()
            name = t[1]
            if self.peek()[0] == "LP":
                # Array reference
                idx = self.parse_arglist()
                return self.interp.get_array(name, idx)
            return self.interp.get_var(name)
        raise BasicError(Err.INVALID_EXPRESSION)

    def parse_arglist(self):
        """Read ( arg, arg, ... ) and return a list of values."""
        if self.peek()[0] != "LP":
            raise BasicError(Err.EXPECTED_LPAREN)
        self.advance()
        args = []
        if self.peek()[0] != "RP":
            args.append(self.parse())
            while self.peek()[0] == "COMMA":
                self.advance()
                args.append(self.parse())
        self.expect_rp()
        return args

    def parse_function(self, name):
        self.advance()  # function name

        # Frame-break target (main-driven mode only): break the frame on evaluation.
        if name in self.interp.frame_break:
            self.interp.yield_frame = True

        spec = self.interp._func_dispatch.get(name)
        if spec is not None:
            fn, raw, lo, hi = spec
            if raw:
                return fn(self)
            args = self.parse_arglist()
            if not (lo <= len(args) <= hi):
                raise BasicError(Err.WRONG_ARG_COUNT, name)
            return fn(self, args)
        # Single-argument math function (name guaranteed to be in MATH1 here)
        args = self.parse_arglist()
        if len(args) != 1:
            raise BasicError(Err.WRONG_ARG_COUNT, name)
        return MATH1[name](self._num(args[0]))

    # --- Function handlers (wired by name in keywords.FUNCTION_HANDLERS) ---
    # raw handlers parse their own arguments; the rest receive a pre-evaluated
    # argument list. Single-argument math functions are handled via keywords.MATH1.

    def _fn_rnd(self):
        if self.peek()[0] == "LP":
            args = self.parse_arglist()
            n = self._num(args[0]) if args else 1
            return random.random() * n
        return random.random()

    def _fn_inkey(self):
        return self.interp.io.inkey()

    def _fn_len(self, args):
        return len(basic_str(args[0]))

    def _fn_left(self, args):
        return basic_str(args[0])[:int(self._num(args[1]))]

    def _fn_right(self, args):
        k = int(self._num(args[1]))
        return basic_str(args[0])[-k:] if k > 0 else ""

    def _fn_mid(self, args):
        s = basic_str(args[0])
        start = int(self._num(args[1])) - 1  # 1-based
        if len(args) >= 3:
            length = int(self._num(args[2]))
            return s[start:start + length]
        return s[start:]

    def _fn_chr(self, args):
        return chr(int(self._num(args[0])))

    def _fn_asc(self, args):
        t = basic_str(args[0])
        return ord(t[0]) if t else 0

    def _fn_str(self, args):
        return basic_str(self._num(args[0]))

    def _fn_hex(self, args):
        # Uppercase hex string of the integerized value. Negatives keep a '-'
        # sign (no fixed-width two's complement, since values are arbitrary int).
        return format(int(self._num(args[0])), "X")

    def _fn_val(self, args):
        txt = basic_str(args[0]).strip()
        try:
            # A leading &H is read as hexadecimal (matches the &H literal form).
            if len(txt) > 2 and txt[0] == "&" and txt[1] in "Hh":
                return int(txt[2:], 16)
            return float(txt) if "." in txt else int(txt)
        except ValueError:
            return 0

    def _fn_stick(self, args):
        return self.interp.io.stick(int(self._num(args[0])))

    def _fn_button(self, args):
        return self.interp.io.button(int(self._num(args[0])))

    def _fn_point(self, args):
        x = int(self._num(args[0]))
        y = int(self._num(args[1]))
        return self.interp.io.point(x, y)

    def _fn_play(self, args):
        ch = int(self._num(args[0]))
        if not 0 <= ch <= 3:
            raise BasicError(Err.PLAY_CHANNEL_OUT_OF_RANGE, ch)
        return self.interp.io.playing(ch)

    # --- Helpers ---
    def _num(self, v):
        if isinstance(v, str):
            raise BasicError(Err.NUMBER_REQUIRED)
        return v

    def _compare(self, a, op, b):
        # When types are mixed, only string-to-string comparison is allowed
        if isinstance(a, str) != isinstance(b, str):
            raise BasicError(Err.TYPE_MISMATCH)
        if op == "=":
            return to_bool_num(a == b)
        if op == "<>":
            return to_bool_num(a != b)
        if op == "<":
            return to_bool_num(a < b)
        if op == "<=":
            return to_bool_num(a <= b)
        if op == ">":
            return to_bool_num(a > b)
        if op == ">=":
            return to_bool_num(a >= b)
        raise BasicError(Err.INVALID_COMPARISON_OP)


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------

class Interpreter:
    """Holds and runs the program.

    States:
      EDIT  : edit mode (stopped)
      RUN   : running
      INPUT : waiting for INPUT
      END   : finished
    """

    def __init__(self, io, vsync_enabled=False):
        self.io = io                  # I/O target
        # Frame-break (VSYNC) is only active in the main-driven execution mode.
        # When disabled (threaded mode) the set stays empty, so the frame-break
        # checks never fire and VSYNC is a no-op.
        self.vsync_enabled = vsync_enabled
        self.frame_break = set(FRAME_BREAK) if vsync_enabled else set()
        self.program = {}             # line number -> source string
        # Resolve keyword -> handler once here, so dispatch costs no getattr per
        # step. Statement handlers are bound Interpreter methods; function handlers
        # are unbound Evaluator functions (called with the live Evaluator as self).
        self._stmt_dispatch = {
            kw: getattr(self, name) for kw, name in STATEMENT_HANDLERS.items()
        }
        self._func_dispatch = {
            kw: (getattr(Evaluator, name), raw, lo, hi)
            for kw, (name, raw, lo, hi) in FUNCTION_HANDLERS.items()
        }
        self.reset_runtime()
        self.state = "EDIT"

    # --- Program editing ---
    def store_line(self, line_no, text):
        """Store a line. An empty text deletes it."""
        if text.strip() == "":
            self.program.pop(line_no, None)
        else:
            self.program[line_no] = normalize_line(text)

    def list_lines(self, start=None, end=None):
        result = []
        for ln in sorted(self.program):
            if start is not None and ln < start:
                continue
            if end is not None and ln > end:
                continue
            result.append((ln, self.program[ln]))
        return result

    def renum(self, start=10, step=10):
        old = sorted(self.program)
        mapping = {}
        new_no = start
        for ln in old:
            mapping[ln] = new_no
            new_no += step
        # Renumber the line numbers referenced by GOTO / GOSUB / THEN
        new_prog = {}
        for ln in old:
            new_prog[mapping[ln]] = self._renum_refs(self.program[ln], mapping)
        self.program = new_prog

    def _renum_refs(self, text, mapping):
        # Simple pass that replaces the number right after a line-referencing statement
        toks = tokenize(text)
        # Only lines that actually reference a line number are rewritten; every
        # other line is kept verbatim. This preserves REM comments (tokenize()
        # drops the comment text, so round-tripping them through detokenize would
        # blank the line) and the original formatting of plain statements.
        refkw = (("KW", "GOTO"), ("KW", "GOSUB"), ("KW", "THEN"))
        if not any(t in refkw for t in toks):
            return text
        out = []
        i = 0
        while i < len(toks):
            kind, val = toks[i]
            out.append((kind, val))
            if (kind, val) in (("KW", "GOTO"), ("KW", "GOSUB"), ("KW", "THEN")):
                if i + 1 < len(toks) and toks[i + 1][0] == "NUM":
                    target = toks[i + 1][1]
                    out.append(("NUM", mapping.get(target, target)))
                    i += 2
                    continue
            i += 1
        return detokenize(out)

    def new_program(self):
        self.program = {}
        # Reset the frame-break config too (only populated in main-driven mode).
        self.frame_break = set(FRAME_BREAK) if self.vsync_enabled else set()
        self.reset_runtime()
        self.state = "EDIT"

    # --- Run preparation ---
    def reset_runtime(self):
        self.vars = {}
        self.arrays = {}
        self.for_stack = []
        self.gosub_stack = []
        self.data = []
        self.data_ptr = 0
        self.data_lines = {}    # DATA line number -> start index into self.data
        self.code = []          # [(line number, token list)]
        self.line_index = {}    # line number -> index into code
        self.pc = 0
        self.jumped = False
        self.input_targets = []
        self.cur_line = 0           # line number of the statement last executed
        self.yield_frame = False    # set by frame-break/VSYNC; read by the main-driven driver

    def prepare_run(self):
        self.reset_runtime()
        self.code = []
        # Flatten the program into one entry per statement. A line with ':' yields
        # several entries; the program counter is therefore statement-granular, so
        # FOR/NEXT, GOSUB/RETURN and GOTO all work within a single line.
        for ln in sorted(self.program):
            toks = tokenize(self.program[ln])
            stmts = split_statements(toks)
            if not stmts:
                # Keep empty / REM-only lines addressable (e.g. as a GOTO target).
                stmts = [[]]
            for stmt in stmts:
                self.code.append((ln, stmt))
        # A line number maps to the index of its FIRST statement.
        self.line_index = {}
        for i, (ln, _) in enumerate(self.code):
            if ln not in self.line_index:
                self.line_index[ln] = i
        self._collect_data()
        self.pc = 0
        self.state = "RUN"

    def _collect_data(self):
        """Collect DATA statements ahead of time.

        Each comma-separated item must be a numeric literal (with an optional
        leading + / - sign) or a quoted string. Unquoted text such as
        ``DATA HELLO`` is rejected with a clear error instead of being silently
        dropped (which used to surface later as a confusing "Out of DATA").
        """
        self.data = []
        self.data_lines = {}
        for ln, toks in self.code:
            if not (toks and toks[0] == ("KW", "DATA")):
                continue
            body = toks[1:]
            if not body:
                continue            # bare DATA: no items
            # Remember where this line's data starts so RESTORE <line> can seek
            # to it (first DATA statement on a line wins).
            self.data_lines.setdefault(ln, len(self.data))
            # Split the body on top-level commas into items, then convert each.
            item = []
            for t in body:
                if t[0] == "COMMA":
                    self.data.append(self._data_value(item))
                    item = []
                else:
                    item.append(t)
            self.data.append(self._data_value(item))

    @staticmethod
    def _data_value(item):
        """Convert one DATA item (a run of tokens) into its stored value.

        Accepts a quoted string, a numeric literal, or a numeric literal with a
        single leading + / - sign. Anything else is a DATA error.
        """
        if len(item) == 1 and item[0][0] in ("STR", "NUM"):
            return item[0][1]
        if (len(item) == 2 and item[0] in (("OP", "+"), ("OP", "-"))
                and item[1][0] == "NUM"):
            val = item[1][1]
            return -val if item[0][1] == "-" else val
        text = " ".join(str(v) for _, v in item) if item else "(empty)"
        raise BasicError(Err.INVALID_DATA, text)

    # --- Variable access ---
    def get_var(self, name):
        if name in self.vars:
            return self.vars[name]
        # Undefined: empty string for string vars, 0 for numeric vars
        return "" if name.endswith("$") else 0

    def set_var(self, name, value):
        if name.endswith("$") and not isinstance(value, str):
            value = basic_str(value)
        if not name.endswith("$") and isinstance(value, str):
            raise BasicError(Err.STRING_TO_NUMERIC, name)
        self.vars[name] = value

    def dim_array(self, name, dims):
        size = [int(d) + 1 for d in dims]  # 0-based, so +1
        fill = "" if name.endswith("$") else 0
        self.arrays[name] = (size, _make_nd(size, fill))

    def _ensure_array(self, name, indices):
        if name not in self.arrays:
            # Implicit DIM (10 per dimension)
            self.dim_array(name, [10] * len(indices))
        return self.arrays[name]

    def get_array(self, name, indices):
        size, data = self._ensure_array(name, [int(i) for i in indices])
        return _nd_get(data, size, [int(i) for i in indices], name)

    def set_array(self, name, indices, value):
        if name.endswith("$") and not isinstance(value, str):
            value = basic_str(value)
        size, data = self._ensure_array(name, [int(i) for i in indices])
        _nd_set(data, size, [int(i) for i in indices], value, name)

    # --- Single-statement execution ---
    def step(self):
        if self.state != "RUN":
            return
        if self.pc >= len(self.code):
            self.state = "END"
            return
        line_no, toks = self.code[self.pc]
        self.cur_line = line_no
        self.jumped = False
        try:
            self.execute(toks)
        except BasicError as e:
            self.io.print_line("?ERROR %d in line %d: %s" % (int(e.code), line_no, e))
            self.state = "EDIT"
            return
        except Exception as e:
            # Safety net: an unexpected Python-level error (e.g. a non-numeric
            # value where a number is required) must report a BASIC error and
            # drop to edit mode, never crash PyxelBasic.
            self.io.print_line("?ERROR in line %d: %s" % (line_no, e))
            self.state = "EDIT"
            return
        if self.state == "RUN" and not self.jumped:
            self.pc += 1

    def execute(self, toks):
        if not toks:
            return
        kind, val = toks[0]

        if kind == "VAR":
            self._do_assign(toks, 0)
            return
        if kind != "KW":
            raise BasicError(Err.SYNTAX_ERROR)

        handler = self._stmt_dispatch.get(val)
        if handler is None:
            raise BasicError(Err.UNSUPPORTED_STATEMENT, val)
        handler(toks)

        # Frame-break target (main-driven mode only): cut off the frame here.
        if val in self.frame_break:
            self.yield_frame = True

    # --- Implementation of each statement ---
    def _eval_from(self, toks, start):
        ev = Evaluator(toks, self, start)
        return ev.parse()

    def _do_assign(self, toks, start):
        # VAR [ ( idx ) ] = expr
        if toks[start][0] != "VAR":
            raise BasicError(Err.ASSIGN_TARGET_NOT_VAR)
        name = toks[start][1]
        pos = start + 1
        indices = None
        if pos < len(toks) and toks[pos][0] == "LP":
            ev = Evaluator(toks, self, pos)
            indices = ev.parse_arglist()
            pos = ev.pos
        if pos >= len(toks) or toks[pos] != ("OP", "="):
            # A bare line that began with a variable but has no '=' is simply not
            # a valid statement (e.g. arbitrary typed text). Only an explicit LET
            # (start > 0) should complain specifically about the missing '='.
            raise BasicError(Err.EXPECTED_EQUALS if start else Err.SYNTAX_ERROR)
        ev = Evaluator(toks, self, pos + 1)
        value = ev.parse()
        if indices is None:
            self.set_var(name, value)
        else:
            self.set_array(name, indices, value)

    def _do_let(self, toks):
        self._do_assign(toks, 1)

    def _do_noop(self, toks):
        # REM is a comment; DATA is pre-collected at prepare_run time.
        pass

    def _do_restore(self, toks):
        if len(toks) > 1:
            # RESTORE <line>: seek the data pointer to that line's DATA. The
            # target must be a line that actually holds a DATA statement.
            line_no = int(self._eval_from(toks, 1))
            if line_no not in self.data_lines:
                raise BasicError(Err.RESTORE_NO_DATA, line_no)
            self.data_ptr = self.data_lines[line_no]
        else:
            self.data_ptr = 0

    def _do_cls(self, toks):
        # CLS [mask]: 1 = text only, 2 = graphics only, 3 = both (bit OR).
        # No argument clears both (mask 3), as before. The mask is used as bit
        # flags downstream, so anything outside 1..3 would silently clear an
        # unexpected subset (or nothing); reject it instead of acting oddly. 0 is
        # rejected too (it would be a no-op that reads like a bare CLS).
        mask = 3
        if len(toks) > 1:
            mask = int(self._eval_from(toks, 1))
        if not 1 <= mask <= 3:
            raise BasicError(Err.INVALID_CLS_MASK, mask)
        self.io.cls(mask)

    def _do_color(self, toks):
        v = self._eval_from(toks, 1)
        self.io.set_color(int(v))

    def _do_end(self, toks):
        self.state = "END"

    def _do_print(self, toks):
        pos = 1
        newline = True
        out = []
        while pos < len(toks):
            t = toks[pos]
            if t[0] == "SEMI":
                newline = False
                pos += 1
                continue
            if t[0] == "COMMA":
                out.append("\t")
                newline = False
                pos += 1
                continue
            ev = Evaluator(toks, self, pos)
            value = ev.parse()
            out.append(basic_str(value))
            pos = ev.pos
            newline = True  # default newline after an expression (cancelled by a separator)
        text = "".join(out)
        if newline:
            self.io.print_line(text)
        else:
            self.io.print_text(text)

    def _do_input(self, toks):
        pos = 1
        prompt = "? "
        if toks[pos][0] == "STR":
            prompt = toks[pos][1]
            pos += 1
            if pos < len(toks) and toks[pos][0] in ("SEMI", "COMMA"):
                pos += 1
        targets = []
        while pos < len(toks):
            if toks[pos][0] == "VAR":
                targets.append(toks[pos][1])
                pos += 1
            elif toks[pos][0] == "COMMA":
                pos += 1
            else:
                break
        self.input_targets = targets
        self.io.print_text(prompt)
        # Switch to input-wait. Advance pc so we resume on the next line.
        self.pc += 1
        self.jumped = True
        self.state = "INPUT"

    def provide_input(self, text):
        """Called while waiting for input; assigns the input string to the variables and resumes."""
        parts = [p.strip() for p in text.split(",")]
        for i, name in enumerate(self.input_targets):
            raw = parts[i] if i < len(parts) else ""
            if name.endswith("$"):
                self.set_var(name, raw)
            else:
                try:
                    self.set_var(name, float(raw) if "." in raw else int(raw))
                except ValueError:
                    self.set_var(name, 0)
        self.input_targets = []
        self.state = "RUN"

    def _do_goto(self, toks):
        target = int(self._eval_from(toks, 1))
        self._jump_to(target)

    def _jump_to(self, line_no):
        if line_no not in self.line_index:
            raise BasicError(Err.LINE_NOT_FOUND, line_no)
        self.pc = self.line_index[line_no]
        self.jumped = True

    def _do_gosub(self, toks):
        target = int(self._eval_from(toks, 1))
        self.gosub_stack.append(self.pc + 1)
        self._jump_to(target)

    def _do_return(self, toks):
        if not self.gosub_stack:
            raise BasicError(Err.RETURN_WITHOUT_GOSUB)
        self.pc = self.gosub_stack.pop()
        self.jumped = True

    def _do_if(self, toks):
        # IF <expr> THEN <then part> [ELSE <else part>]
        then_pos = None
        for i, t in enumerate(toks):
            if t == ("KW", "THEN"):
                then_pos = i
                break
        if then_pos is None:
            raise BasicError(Err.EXPECTED_THEN)
        # The first ELSE after THEN ends the then-clause. (A nested IF...THEN...
        # ELSE on one line binds the ELSE to the outer IF; best-effort only.)
        else_pos = None
        for i in range(then_pos + 1, len(toks)):
            if toks[i] == ("KW", "ELSE"):
                else_pos = i
                break
        ev = Evaluator(toks, self, 1)
        cond = ev.parse()
        truthy = bool(cond) and cond != 0
        if truthy:
            end = else_pos if else_pos is not None else len(toks)
            clause = toks[then_pos + 1:end]
        elif else_pos is not None:
            clause = toks[else_pos + 1:]
        else:
            return
        if not clause:
            raise BasicError(Err.NOTHING_AFTER_THEN)
        # A leading number means an implicit GOTO.
        if clause[0][0] == "NUM":
            self._jump_to(int(clause[0][1]))
        else:
            self._run_stmt_seq(clause)

    def _run_stmt_seq(self, toks):
        """Run a token list that may hold several ':'-separated statements.

        Used for the THEN / ELSE clauses of IF and for direct-mode input. Stops
        early if a statement transfers control (GOTO/GOSUB/RETURN/NEXT/implicit
        GOTO) or ends the program, so the rest of the line is not executed.
        """
        for stmt in split_statements(toks):
            self.execute(stmt)
            if self.jumped or self.state != "RUN":
                break

    def _do_for(self, toks):
        # FOR VAR = start TO end [STEP n]
        if toks[1][0] != "VAR":
            raise BasicError(Err.MISSING_FOR_VAR)
        var = toks[1][1]
        if toks[2] != ("OP", "="):
            raise BasicError(Err.EXPECTED_EQUALS_IN_FOR)
        ev = Evaluator(toks, self, 3)
        start = ev.parse()
        if ev.peek() != ("KW", "TO"):
            raise BasicError(Err.EXPECTED_TO_IN_FOR)
        ev.advance()
        end = ev.parse()
        step = 1
        if ev.peek() == ("KW", "STEP"):
            ev.advance()
            step = ev.parse()
        self.set_var(var, start)
        self.for_stack.append({
            "var": var, "end": end, "step": step,
            "loop_pc": self.pc + 1,
        })

    def _do_next(self, toks):
        if not self.for_stack:
            raise BasicError(Err.NEXT_WITHOUT_FOR)
        # NEXT [var]: if a variable is given, unwind until it matches
        if len(toks) > 1 and toks[1][0] == "VAR":
            target = toks[1][1]
            while self.for_stack and self.for_stack[-1]["var"] != target:
                self.for_stack.pop()
            if not self.for_stack:
                raise BasicError(Err.NEXT_VAR_WITHOUT_FOR, target)
        frame = self.for_stack[-1]
        new_val = self.get_var(frame["var"]) + frame["step"]
        self.set_var(frame["var"], new_val)
        cont = new_val <= frame["end"] if frame["step"] >= 0 else new_val >= frame["end"]
        if cont:
            self.pc = frame["loop_pc"]
            self.jumped = True
        else:
            self.for_stack.pop()

    def _do_dim(self, toks):
        pos = 1
        while pos < len(toks):
            if toks[pos][0] != "VAR":
                raise BasicError(Err.INVALID_DIM_SYNTAX)
            name = toks[pos][1]
            ev = Evaluator(toks, self, pos + 1)
            dims = ev.parse_arglist()
            self.dim_array(name, dims)
            pos = ev.pos
            if pos < len(toks) and toks[pos][0] == "COMMA":
                pos += 1

    def _do_read(self, toks):
        pos = 1
        while pos < len(toks):
            if toks[pos][0] == "VAR":
                name = toks[pos][1]
                pos += 1
                # An array element target: VAR ( index [, index ...] ).
                indices = None
                if pos < len(toks) and toks[pos][0] == "LP":
                    ev = Evaluator(toks, self, pos)
                    indices = ev.parse_arglist()
                    pos = ev.pos
                if self.data_ptr >= len(self.data):
                    raise BasicError(Err.OUT_OF_DATA)
                value = self.data[self.data_ptr]
                self.data_ptr += 1
                if indices is None:
                    self.set_var(name, value)
                else:
                    self.set_array(name, indices, value)
            elif toks[pos][0] == "COMMA":
                pos += 1
            else:
                break

    def _do_locate(self, toks):
        ev = Evaluator(toks, self, 1)
        x = ev.parse()
        if ev.peek()[0] != "COMMA":
            raise BasicError(Err.INVALID_LOCATE_SYNTAX)
        ev.advance()
        y = ev.parse()
        self.io.locate(int(x), int(y))

    def _do_pset(self, toks):
        # PSET(x,y)[,col]  or  PSET(x,y,col)
        ev = Evaluator(toks, self, 1)
        args = ev.parse_arglist()
        col = None
        if ev.peek()[0] == "COMMA":
            ev.advance()
            col = int(ev.parse())
        elif len(args) >= 3:
            col = int(args[2])
        self.io.pset(int(args[0]), int(args[1]), col)

    def _parse_line_coords(self, toks):
        # Parse "(x1,y1)-(x2,y2)[,col]" and return (x1, y1, x2, y2, col).
        # col is None when omitted (the IO layer resolves the current color).
        ev = Evaluator(toks, self, 1)
        p1 = ev.parse_arglist()
        if ev.peek() != ("OP", "-"):
            raise BasicError(Err.INVALID_LINE_SYNTAX)
        ev.advance()
        p2 = ev.parse_arglist()
        col = None
        if ev.peek()[0] == "COMMA":
            ev.advance()
            col = int(ev.parse())
        return int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]), col

    def _do_line(self, toks):
        # LINE(x1,y1)-(x2,y2)[,col]
        x1, y1, x2, y2, col = self._parse_line_coords(toks)
        self.io.line(x1, y1, x2, y2, col)

    def _do_lineb(self, toks):
        # LINEB(x1,y1)-(x2,y2)[,col] : rectangle outline
        x1, y1, x2, y2, col = self._parse_line_coords(toks)
        self.io.rectb(x1, y1, x2, y2, col)

    def _do_linebf(self, toks):
        # LINEBF(x1,y1)-(x2,y2)[,col] : filled rectangle
        x1, y1, x2, y2, col = self._parse_line_coords(toks)
        self.io.rect(x1, y1, x2, y2, col)

    def _parse_circle_args(self, toks):
        # CIRCLE(x,y),r,col[,start][,end][,ratio]
        # Returns (x, y, r, col, start, end, ratio); omitted optionals are None.
        # Middle optionals may be left empty (consecutive commas) so that ratio
        # can be given without the angles, e.g. CIRCLE(x,y),r,c,,,2.
        ev = Evaluator(toks, self, 1)
        center = ev.parse_arglist()
        if len(center) != 2:
            raise BasicError(Err.INVALID_CIRCLE_SYNTAX)
        x, y = int(center[0]), int(center[1])
        slots = []
        while ev.peek()[0] == "COMMA":
            ev.advance()
            if ev.peek()[0] in ("COMMA", None):
                slots.append(None)        # empty slot
            else:
                slots.append(ev.parse())
        if len(slots) < 2 or slots[0] is None or slots[1] is None or len(slots) > 5:
            raise BasicError(Err.INVALID_CIRCLE_SYNTAX)
        r = slots[0]
        col = int(slots[1])
        start = slots[2] if len(slots) >= 3 else None
        end = slots[3] if len(slots) >= 4 else None
        ratio = slots[4] if len(slots) >= 5 else None
        return x, y, r, col, start, end, ratio

    @staticmethod
    def _circle_radii(r, ratio):
        # MSX-BASIC aspect: ratio = ry / rx (vertical / horizontal); r is always
        # the longer (major) semi-axis. ratio==1 -> circle; ratio>1 -> tall
        # (ry=r, rx=r/ratio); ratio<1 -> wide (rx=r, ry=r*ratio).
        r = float(r)
        ratio = 1.0 if ratio is None else float(ratio)
        if ratio <= 0:
            ratio = 1.0
        if ratio > 1.0:
            rx, ry = r / ratio, r
        elif ratio < 1.0:
            rx, ry = r, r * ratio
        else:
            rx = ry = r
        return int(round(rx)), int(round(ry))

    def _do_circle(self, toks):
        self._draw_circle(toks, fill=False)

    def _do_circlebf(self, toks):
        self._draw_circle(toks, fill=True)

    def _draw_circle(self, toks, fill):
        x, y, r, col, start, end, ratio = self._parse_circle_args(toks)
        rx, ry = self._circle_radii(r, ratio)
        if start is None and end is None:
            # Full ellipse/circle via the Pyxel primitive.
            if fill:
                self.io.elli(x, y, rx, ry, col)
            else:
                self.io.ellib(x, y, rx, ry, col)
            return
        # Arc: rasterize on this (Pyxel-independent) side and emit primitives.
        s = 0.0 if start is None else float(start)
        e = 2 * math.pi if end is None else float(end)
        self._draw_arc(fill, x, y, rx, ry, s, e, col)

    def _draw_arc(self, fill, x, y, rx, ry, start, end, col):
        # Angle is measured from 3 o'clock (right), counterclockwise (MSX style).
        # Screen y grows downward, so the y term is subtracted.
        span = end - start
        if span <= 0:
            span += 2 * math.pi
        n = min(720, max(8, int(max(rx, ry, 1) * span)))
        pts = []
        for i in range(n + 1):
            th = start + span * i / n
            px = int(round(x + rx * math.cos(th)))
            py = int(round(y - ry * math.sin(th)))
            pts.append((px, py))
        if fill:
            for i in range(n):
                self.io.tri(x, y, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col)
        else:
            for i in range(n):
                self.io.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], col)

    def _do_randomize(self, toks):
        if len(toks) > 1:
            seed = self._eval_from(toks, 1)
            random.seed(seed)
        else:
            random.seed()

    def _do_vsync(self, toks):
        # VSYNC behaviour depends on the execution mode:
        #   threaded mode (vsync_enabled False) -> no-op; frame pacing is handled
        #     by the VM throttle. Only "VSYNC LIST" prints "FRAME BREAK: (none)"
        #     for compatibility; every other form is accepted and ignored.
        #   main-driven mode (vsync_enabled True) -> classic frame-break control:
        #     VSYNC                -> break this frame (explicit sync point)
        #     VSYNC LIST           -> show the current break targets
        #     VSYNC RESET          -> restore the break config to its initial state
        #     VSYNC CLEAR          -> remove every automatic break target (only an
        #                             explicit VSYNC breaks a frame afterwards)
        #     VSYNC <word> ON|OFF  -> change the frame-break setting for that word
        if not self.vsync_enabled:
            if len(toks) >= 2 and toks[1][1] == "LIST":
                self._vsync_list()
            return
        if len(toks) == 1:
            self.yield_frame = True
            return
        sub = toks[1][1]   # second word (a reserved word if KW, an identifier if VAR)
        if sub == "LIST":
            self._vsync_list()
            return
        if sub == "RESET":
            self.frame_break = set(FRAME_BREAK)
            return
        if sub == "CLEAR":
            self.frame_break = set()
            return
        # Remaining form is "<word> ON|OFF"; the word must be a valid reserved word.
        if toks[1][0] != "KW":
            raise BasicError(Err.VSYNC_KEYWORD_REQUIRED)
        if len(toks) < 3 or toks[2][0] != "VAR" or toks[2][1] not in ("ON", "OFF"):
            raise BasicError(Err.VSYNC_ON_OFF_REQUIRED)
        if toks[2][1] == "ON":
            self.frame_break.add(sub)
        else:
            self.frame_break.discard(sub)

    def _vsync_list(self):
        if self.frame_break:
            words = " ".join(sorted(self.frame_break))
        else:
            words = "(none)"
        self.io.print_line("FRAME BREAK: " + words)

    # --- Sprites ---
    _HEX_DIGITS = "0123456789abcdefABCDEF"

    def _do_set(self, toks):
        # SET SPRITE no, "<hexstring>"
        # Define 8x8 patterns from a hex string (one char = one pixel colour).
        # 64 chars per 8x8 pattern; a short string is padded with '0', a long one
        # spills into the following 8x8 pattern numbers in 64-char chunks.
        if len(toks) < 2 or toks[1] != ("KW", "SPRITE"):
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        ev = Evaluator(toks, self, 2)
        no = int(ev.parse())
        if ev.peek()[0] != "COMMA":
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        ev.advance()
        data = ev.parse()
        if ev.peek()[0] is not None or not isinstance(data, str):
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        if not (0 <= no <= 1023):
            raise BasicError(Err.SPRITE_OUT_OF_RANGE, "no")
        for ch in data:
            if ch not in self._HEX_DIGITS:
                raise BasicError(Err.INVALID_SPRITE_DATA, ch)
        # Pad up to a whole number of 8x8 patterns (an empty string is one
        # all-zero pattern, matching "missing pixels are filled with 0").
        if len(data) == 0:
            data = "0" * 64
        elif len(data) % 64 != 0:
            data += "0" * (64 - len(data) % 64)
        count = len(data) // 64
        if no + count - 1 > 1023:
            raise BasicError(Err.SPRITE_PATTERN_OVERFLOW)
        colors = [int(ch, 16) for ch in data]
        self.io.set_sprite(no, colors)

    def _do_put(self, toks):
        # PUT SPRITE id, (x,y), no, size [,colkey]   -> enable + set the entry
        # PUT SPRITE id, OFF                          -> disable the entry
        if len(toks) < 2 or toks[1] != ("KW", "SPRITE"):
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        ev = Evaluator(toks, self, 2)
        sid = int(ev.parse())
        if ev.peek()[0] != "COMMA":
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        ev.advance()
        # OFF form: nothing may follow OFF.
        if ev.peek() == ("VAR", "OFF"):
            ev.advance()
            if ev.peek()[0] is not None:
                raise BasicError(Err.INVALID_SPRITE_SYNTAX)
            if not (0 <= sid <= 1023):
                raise BasicError(Err.SPRITE_OUT_OF_RANGE, "id")
            self.io.put_sprite_off(sid)
            return
        # Full form.
        coords = ev.parse_arglist()
        if len(coords) != 2:
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        x, y = int(coords[0]), int(coords[1])
        no = int(self._put_after_comma(ev))
        size = int(self._put_after_comma(ev))
        colkey = -1
        if ev.peek()[0] == "COMMA":
            ev.advance()
            colkey = int(ev.parse())
        if ev.peek()[0] is not None:
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        if not (0 <= sid <= 1023):
            raise BasicError(Err.SPRITE_OUT_OF_RANGE, "id")
        if size not in (0, 1):
            raise BasicError(Err.SPRITE_OUT_OF_RANGE, "size")
        no_max = 1023 if size == 0 else 255
        if not (0 <= no <= no_max):
            raise BasicError(Err.SPRITE_OUT_OF_RANGE, "no")
        if not (-1 <= colkey <= 15):
            raise BasicError(Err.SPRITE_OUT_OF_RANGE, "colkey")
        self.io.put_sprite(sid, x, y, no, size, colkey)

    @staticmethod
    def _put_after_comma(ev):
        if ev.peek()[0] != "COMMA":
            raise BasicError(Err.INVALID_SPRITE_SYNTAX)
        ev.advance()
        return ev.parse()

    # --- Sound (PLAY) ---
    def _do_play(self, toks):
        # PLAY "m0"[,"m1","m2","m3"] / PLAY LOOP ... / PLAY CH ch,"mml" /
        # PLAY LOOP CH ch,"mml" / PLAY STOP [ch,...]
        # LOOP and CH are contextual keywords: they tokenize as VAR and are
        # matched only here, by position, so they stay usable as variable names.
        if len(toks) >= 2 and toks[1] == ("KW", "STOP"):
            self._play_stop(toks)
            return
        start = 1
        loop = False
        if len(toks) > start and toks[start] == ("VAR", "LOOP"):
            loop = True
            start += 1
        if len(toks) > start and toks[start] == ("VAR", "CH"):
            self._play_one_channel(toks, start + 1, loop)
            return
        mmls = self._parse_play_slots(toks, start)
        bad = self.io.play_channels(mmls, loop)
        if bad is not None:
            raise BasicError(Err.INVALID_MML, bad)

    def _play_stop(self, toks):
        # PLAY STOP [ch [, ch ...]]  (no channels -> stop all)
        channels = []
        ev = Evaluator(toks, self, 2)
        while ev.peek()[0] is not None:
            ch = int(ev.parse())
            self._check_play_channel(ch)
            channels.append(ch)
            if ev.peek()[0] == "COMMA":
                ev.advance()
            else:
                break
        if ev.peek()[0] is not None:
            raise BasicError(Err.INVALID_PLAY_SYNTAX)
        self.io.play_stop(channels)

    def _play_one_channel(self, toks, start, loop):
        # PLAY [LOOP] CH ch, "mml"
        ev = Evaluator(toks, self, start)
        ch = int(ev.parse())
        if ev.peek()[0] != "COMMA":
            raise BasicError(Err.INVALID_PLAY_SYNTAX)
        ev.advance()
        mml = ev.parse()
        if not isinstance(mml, str) or ev.peek()[0] is not None:
            raise BasicError(Err.INVALID_PLAY_SYNTAX)
        self._check_play_channel(ch)
        bad = self.io.play_ch(ch, mml, loop)
        if bad is not None:
            raise BasicError(Err.INVALID_MML, bad)

    def _parse_play_slots(self, toks, start):
        # Up to 4 comma-separated MML slots; an empty slot (consecutive commas,
        # leading comma, or end) is None and means "this channel does nothing".
        ev = Evaluator(toks, self, start)
        slots = []
        while True:
            if ev.peek()[0] in ("COMMA", None):
                slots.append(None)
            else:
                v = ev.parse()
                if not isinstance(v, str):
                    raise BasicError(Err.INVALID_PLAY_SYNTAX)
                slots.append(v)
            if ev.peek()[0] == "COMMA":
                ev.advance()
                continue
            break
        if ev.peek()[0] is not None or len(slots) > 4:
            raise BasicError(Err.INVALID_PLAY_SYNTAX)
        return slots

    @staticmethod
    def _check_play_channel(ch):
        if not 0 <= ch <= 3:
            raise BasicError(Err.PLAY_CHANNEL_OUT_OF_RANGE, ch)


# ---------------------------------------------------------------------------
# Multidimensional array helpers
# ---------------------------------------------------------------------------

def _make_nd(size, fill):
    if len(size) == 1:
        return [fill for _ in range(size[0])]
    return [_make_nd(size[1:], fill) for _ in range(size[0])]


def _nd_get(data, size, indices, name):
    cur = data
    for k, idx in enumerate(indices):
        if idx < 0 or idx >= size[k]:
            raise BasicError(Err.SUBSCRIPT_OUT_OF_RANGE, name)
        cur = cur[idx]
    return cur


def _nd_set(data, size, indices, value, name):
    cur = data
    for k, idx in enumerate(indices[:-1]):
        if idx < 0 or idx >= size[k]:
            raise BasicError(Err.SUBSCRIPT_OUT_OF_RANGE, name)
        cur = cur[idx]
    last = indices[-1]
    if last < 0 or last >= size[-1]:
        raise BasicError(Err.SUBSCRIPT_OUT_OF_RANGE, name)
    cur[last] = value


# ---------------------------------------------------------------------------
# Detokenize (used by RENUM)
# ---------------------------------------------------------------------------

def detokenize(toks):
    parts = []
    for kind, val in toks:
        if kind == "STR":
            parts.append('"%s"' % val)
        elif kind == "NUM":
            if isinstance(val, HexInt):
                parts.append("&H" + val.digits)
            else:
                parts.append(basic_str(val))
        else:
            parts.append(str(val))
    # Join simply with spaces
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Wiring sanity check (fail fast at import, like a compile-time interface check)
# ---------------------------------------------------------------------------

# Every keyword declared in keywords.py must map to a handler method that really
# exists. This catches a typo or a forgotten implementation the moment the module
# is imported, rather than at runtime when the keyword is first used.
for _kw, _method in STATEMENT_HANDLERS.items():
    assert hasattr(Interpreter, _method), \
        "statement %r is wired to missing Interpreter.%s" % (_kw, _method)
for _kw, (_method, _raw, _lo, _hi) in FUNCTION_HANDLERS.items():
    assert hasattr(Evaluator, _method), \
        "function %r is wired to missing Evaluator.%s" % (_kw, _method)
