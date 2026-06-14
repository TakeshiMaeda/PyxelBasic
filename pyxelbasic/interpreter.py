# -*- coding: utf-8 -*-
"""PyxelBasic interpreter core.

Bundles the lexer, expression evaluator and execution engine.
Screen I/O goes through the IOTarget interface, so this module does not
depend on Pyxel (easy to test or to swap the console out).
"""

import math
import random


class BasicError(Exception):
    """Runtime / syntax error."""
    pass


# ---------------------------------------------------------------------------
# Reserved word definitions
# ---------------------------------------------------------------------------

# Statements that can start a line
STATEMENTS = {
    "PRINT", "INPUT", "LET", "GOTO", "GOSUB", "RETURN", "IF",
    "FOR", "NEXT", "DIM", "REM", "CLS", "LOCATE", "COLOR",
    "PSET", "LINE", "END", "STOP", "DATA", "READ", "RESTORE",
    "RANDOMIZE", "VSYNC",
}

# Immediate (direct) mode commands
DIRECT = {"RUN", "LIST", "NEW", "RENUM", "SAVE", "LOAD"}

# Functions usable inside expressions
FUNCTIONS = {
    "LEN", "LEFT$", "RIGHT$", "MID$", "CHR$", "ASC", "STR$", "VAL",
    "ABS", "SGN", "INT", "FIX", "ROUND",
    "SIN", "COS", "TAN", "ATN", "RAD", "DEG",
    "EXP", "LOG", "LOG10", "SQR",
    "RND", "INKEY$", "STICK", "BUTTON",
}

# Syntactic keywords (neither operators nor statements)
SYNTAX = {"THEN", "ELSE", "TO", "STEP"}

# Word-form operators
WORD_OPS = {"MOD", "AND", "OR", "NOT", "XOR"}

KEYWORDS = STATEMENTS | DIRECT | FUNCTIONS | SYNTAX

# --- Initial frame-break configuration ---
# When any reserved word listed here is executed (as a statement) or evaluated
# (as a function), the current frame's execution is cut off and resumed on the
# next frame. Statements and functions are treated alike. This is the initial
# value; at runtime it can be adjusted with the VSYNC <word> ON|OFF command
# (Interpreter.frame_break).
FRAME_BREAK = {
    "PRINT",            # screen output
    "PSET", "LINE",     # drawing statements
    "STICK", "BUTTON",  # input polling (functions)
}


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

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
                raise BasicError("Unterminated string")
            tokens.append(("STR", "".join(buf)))
            i = j + 1
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
        raise BasicError("Invalid character: '%s'" % c)
    return tokens


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
            raise BasicError("Expected ')'")
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
                    raise BasicError("Division by zero")
                left = a / b
            else:  # MOD
                if b == 0:
                    raise BasicError("Division by zero")
                left = int(a) % int(b)
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
        raise BasicError("Invalid expression")

    def parse_arglist(self):
        """Read ( arg, arg, ... ) and return a list of values."""
        if self.peek()[0] != "LP":
            raise BasicError("Expected '('")
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

        # If this function is a frame-break target, break the frame on evaluation
        if name in self.interp.frame_break:
            self.interp.yield_frame = True

        # Functions usable without arguments
        if name == "RND":
            if self.peek()[0] == "LP":
                args = self.parse_arglist()
                n = self._num(args[0]) if args else 1
                return random.random() * n
            return random.random()
        if name == "INKEY$":
            return self.interp.io.inkey()

        args = self.parse_arglist()

        def num(idx):
            return self._num(args[idx])

        def s(idx):
            return basic_str(args[idx])

        if name == "LEN":
            return len(s(0))
        if name == "LEFT$":
            return s(0)[:int(num(1))]
        if name == "RIGHT$":
            k = int(num(1))
            return s(0)[-k:] if k > 0 else ""
        if name == "MID$":
            start = int(num(1)) - 1  # 1-based
            if len(args) >= 3:
                length = int(num(2))
                return s(0)[start:start + length]
            return s(0)[start:]
        if name == "CHR$":
            return chr(int(num(0)))
        if name == "ASC":
            t = s(0)
            return ord(t[0]) if t else 0
        if name == "STR$":
            return basic_str(num(0))
        if name == "VAL":
            try:
                txt = s(0).strip()
                return float(txt) if "." in txt else int(txt)
            except ValueError:
                return 0
        if name == "ABS":
            return abs(num(0))
        if name == "SGN":
            v = num(0)
            return (v > 0) - (v < 0)
        if name == "INT":
            return math.floor(num(0))
        if name == "FIX":
            return math.trunc(num(0))
        if name == "ROUND":
            return round(num(0))
        if name == "SIN":
            return math.sin(num(0))
        if name == "COS":
            return math.cos(num(0))
        if name == "TAN":
            return math.tan(num(0))
        if name == "ATN":
            return math.atan(num(0))
        if name == "RAD":
            return math.radians(num(0))
        if name == "DEG":
            return math.degrees(num(0))
        if name == "EXP":
            return math.exp(num(0))
        if name == "LOG":
            return math.log(num(0))
        if name == "LOG10":
            return math.log10(num(0))
        if name == "SQR":
            return math.sqrt(num(0))
        if name == "STICK":
            return self.interp.io.stick(int(num(0)))
        if name == "BUTTON":
            return self.interp.io.button(int(num(0)))
        raise BasicError("Unsupported function: %s" % name)

    # --- Helpers ---
    def _num(self, v):
        if isinstance(v, str):
            raise BasicError("Number required")
        return v

    def _compare(self, a, op, b):
        # When types are mixed, only string-to-string comparison is allowed
        if isinstance(a, str) != isinstance(b, str):
            raise BasicError("Type mismatch in comparison")
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
        raise BasicError("Invalid comparison operator")


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

    def __init__(self, io):
        self.io = io                  # I/O target
        self.program = {}             # line number -> source string
        # Frame-break targets. Kept across runs because the VSYNC command can
        # adjust them at runtime; reset_runtime does not reinitialize this.
        self.frame_break = set(FRAME_BREAK)
        self.reset_runtime()
        self.state = "EDIT"

    # --- Program editing ---
    def store_line(self, line_no, text):
        """Store a line. An empty text deletes it."""
        if text.strip() == "":
            self.program.pop(line_no, None)
        else:
            self.program[line_no] = text

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
        self.frame_break = set(FRAME_BREAK)   # reset the break config too
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
        self.code = []          # [(line number, token list)]
        self.line_index = {}    # line number -> index into code
        self.pc = 0
        self.jumped = False
        self.input_targets = []
        self.yield_frame = False    # signal from VSYNC to cut off this frame

    def prepare_run(self):
        self.reset_runtime()
        self.code = []
        for ln in sorted(self.program):
            toks = tokenize(self.program[ln])
            self.code.append((ln, toks))
        self.line_index = {ln: i for i, (ln, _) in enumerate(self.code)}
        self._collect_data()
        self.pc = 0
        self.state = "RUN"

    def _collect_data(self):
        """Collect DATA statements ahead of time."""
        self.data = []
        for ln, toks in self.code:
            if toks and toks[0] == ("KW", "DATA"):
                i = 1
                while i < len(toks):
                    kind, val = toks[i]
                    if kind in ("NUM", "STR"):
                        self.data.append(val)
                    i += 1
                    # Skip the comma
                    if i < len(toks) and toks[i][0] == "COMMA":
                        i += 1

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
            raise BasicError("Cannot assign string to numeric variable: %s" % name)
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
            self.io.print_line("?ERROR in %d: %s" % (line_no, e))
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
            raise BasicError("Invalid statement")

        if val == "LET":
            self._do_assign(toks, 1)
        elif val == "PRINT":
            self._do_print(toks)
        elif val == "INPUT":
            self._do_input(toks)
        elif val == "GOTO":
            self._do_goto(toks)
        elif val == "GOSUB":
            self._do_gosub(toks)
        elif val == "RETURN":
            self._do_return()
        elif val == "IF":
            self._do_if(toks)
        elif val == "FOR":
            self._do_for(toks)
        elif val == "NEXT":
            self._do_next(toks)
        elif val == "DIM":
            self._do_dim(toks)
        elif val == "REM":
            pass
        elif val == "DATA":
            pass  # already collected
        elif val == "READ":
            self._do_read(toks)
        elif val == "RESTORE":
            self.data_ptr = 0
        elif val == "CLS":
            self.io.cls()
        elif val == "LOCATE":
            self._do_locate(toks)
        elif val == "COLOR":
            v = self._eval_from(toks, 1)
            self.io.set_color(int(v))
        elif val == "PSET":
            self._do_pset(toks)
        elif val == "LINE":
            self._do_line(toks)
        elif val == "RANDOMIZE":
            self._do_randomize(toks)
        elif val == "VSYNC":
            self._do_vsync(toks)
        elif val in ("END", "STOP"):
            self.state = "END"
        else:
            raise BasicError("Unsupported statement: %s" % val)

        # If this statement is a frame-break target, cut off the frame here
        if val in self.frame_break:
            self.yield_frame = True

    # --- Implementation of each statement ---
    def _eval_from(self, toks, start):
        ev = Evaluator(toks, self, start)
        return ev.parse()

    def _do_assign(self, toks, start):
        # VAR [ ( idx ) ] = expr
        if toks[start][0] != "VAR":
            raise BasicError("Assignment target is not a variable")
        name = toks[start][1]
        pos = start + 1
        indices = None
        if pos < len(toks) and toks[pos][0] == "LP":
            ev = Evaluator(toks, self, pos)
            indices = ev.parse_arglist()
            pos = ev.pos
        if pos >= len(toks) or toks[pos] != ("OP", "="):
            raise BasicError("Expected '='")
        ev = Evaluator(toks, self, pos + 1)
        value = ev.parse()
        if indices is None:
            self.set_var(name, value)
        else:
            self.set_array(name, indices, value)

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
            raise BasicError("Line %d not found" % line_no)
        self.pc = self.line_index[line_no]
        self.jumped = True

    def _do_gosub(self, toks):
        target = int(self._eval_from(toks, 1))
        self.gosub_stack.append(self.pc + 1)
        self._jump_to(target)

    def _do_return(self):
        if not self.gosub_stack:
            raise BasicError("RETURN without GOSUB")
        self.pc = self.gosub_stack.pop()
        self.jumped = True

    def _do_if(self, toks):
        # IF <expr> THEN <then part>
        then_pos = None
        for i, t in enumerate(toks):
            if t == ("KW", "THEN"):
                then_pos = i
                break
        if then_pos is None:
            raise BasicError("Expected THEN")
        ev = Evaluator(toks, self, 1)
        cond = ev.parse()
        truthy = bool(cond) and cond != 0
        if not truthy:
            return
        then_toks = toks[then_pos + 1:]
        if not then_toks:
            raise BasicError("Nothing after THEN")
        # If only a number follows THEN, it is an implicit GOTO
        if then_toks[0][0] == "NUM":
            self._jump_to(int(then_toks[0][1]))
        else:
            self.execute(then_toks)

    def _do_for(self, toks):
        # FOR VAR = start TO end [STEP n]
        if toks[1][0] != "VAR":
            raise BasicError("Missing FOR variable")
        var = toks[1][1]
        if toks[2] != ("OP", "="):
            raise BasicError("Expected '=' in FOR")
        ev = Evaluator(toks, self, 3)
        start = ev.parse()
        if ev.peek() != ("KW", "TO"):
            raise BasicError("Expected TO in FOR")
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
            raise BasicError("NEXT without FOR")
        # NEXT [var]: if a variable is given, unwind until it matches
        if len(toks) > 1 and toks[1][0] == "VAR":
            target = toks[1][1]
            while self.for_stack and self.for_stack[-1]["var"] != target:
                self.for_stack.pop()
            if not self.for_stack:
                raise BasicError("NEXT %s without FOR" % target)
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
                raise BasicError("Invalid DIM syntax")
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
                if self.data_ptr >= len(self.data):
                    raise BasicError("Out of DATA")
                self.set_var(name, self.data[self.data_ptr])
                self.data_ptr += 1
                pos += 1
            elif toks[pos][0] == "COMMA":
                pos += 1
            else:
                break

    def _do_locate(self, toks):
        ev = Evaluator(toks, self, 1)
        x = ev.parse()
        if ev.peek()[0] != "COMMA":
            raise BasicError("Invalid LOCATE syntax")
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

    def _do_line(self, toks):
        # LINE(x1,y1)-(x2,y2)[,col]
        ev = Evaluator(toks, self, 1)
        p1 = ev.parse_arglist()
        if ev.peek() != ("OP", "-"):
            raise BasicError("Invalid LINE syntax ('-' required)")
        ev.advance()
        p2 = ev.parse_arglist()
        col = None
        if ev.peek()[0] == "COMMA":
            ev.advance()
            col = int(ev.parse())
        self.io.line(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]), col)

    def _do_randomize(self, toks):
        if len(toks) > 1:
            seed = self._eval_from(toks, 1)
            random.seed(seed)
        else:
            random.seed()

    def _do_vsync(self, toks):
        # VSYNC                  -> break this frame (explicit sync point)
        # VSYNC LIST             -> show the current break targets
        # VSYNC RESET            -> restore the break config to its initial state
        # VSYNC <word> ON|OFF    -> change the frame-break setting for that word
        if len(toks) == 1:
            self.yield_frame = True
            return
        sub = toks[1][1]   # second word (a reserved word name if KW, an identifier if VAR)
        if sub == "LIST":
            self._vsync_list()
            return
        if sub == "RESET":
            self.frame_break = set(FRAME_BREAK)
            return
        # Remaining form is "<word> ON|OFF". The second word must be a valid reserved word (KW token)
        if toks[1][0] != "KW":
            raise BasicError("VSYNC: keyword required")
        if len(toks) < 3 or toks[2][0] != "VAR" or toks[2][1] not in ("ON", "OFF"):
            raise BasicError("VSYNC: ON or OFF required")
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
            raise BasicError("Subscript out of range: %s" % name)
        cur = cur[idx]
    return cur


def _nd_set(data, size, indices, value, name):
    cur = data
    for k, idx in enumerate(indices[:-1]):
        if idx < 0 or idx >= size[k]:
            raise BasicError("Subscript out of range: %s" % name)
        cur = cur[idx]
    last = indices[-1]
    if last < 0 or last >= size[-1]:
        raise BasicError("Subscript out of range: %s" % name)
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
            parts.append(basic_str(val))
        else:
            parts.append(str(val))
    # Join simply with spaces
    return " ".join(parts)
