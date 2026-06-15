# -*- coding: utf-8 -*-
"""Headless tests for the interpreter core.

Verifies language features using a Pyxel-independent MockIO.
Run:  python tests/test_core.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyxelbasic.interpreter import (  # noqa: E402
    Interpreter, tokenize, basic_str, BasicError,
)
from pyxelbasic.errors import Err  # noqa: E402
from pyxelbasic.keywords import (  # noqa: E402
    FRAME_BREAK, STATEMENTS, FUNCTIONS,
)


class MockIO:
    """Test IO that accumulates screen output as strings."""

    def __init__(self, inputs=None):
        self.out = []
        self._cur = ""        # current line buffer (named to avoid clashing with the line method)
        self.gfx = []
        self.inputs = list(inputs or [])

    def print_text(self, text):
        self._cur += text

    def print_line(self, text):
        self._cur += text
        self.out.append(self._cur)
        self._cur = ""

    def cls(self):
        self.out.append("<CLS>")

    def set_color(self, col):
        pass

    def locate(self, x, y):
        pass

    def pset(self, x, y, col=None):
        self.gfx.append(("pset", x, y, col))

    def line(self, x1, y1, x2, y2, col=None):
        self.gfx.append(("line", x1, y1, x2, y2, col))

    def inkey(self):
        return ""

    def stick(self, n):
        return 0

    def button(self, n):
        return 0


def run_program(lines, inputs=None, max_steps=100000):
    io = MockIO(inputs)
    interp = Interpreter(io)
    for ln, src in lines:
        interp.store_line(ln, src)
    interp.prepare_run()
    steps = 0
    while interp.state == "RUN" and steps < max_steps:
        interp.step()
        steps += 1
        if interp.state == "INPUT":
            val = io.inputs.pop(0) if io.inputs else ""
            io.print_line(val)   # like the real device, bake the confirmed input into the current line and break
            interp.provide_input(val)
    if io._cur:
        io.out.append(io._cur)
    return io, interp


def run_direct(src):
    """Execute one typed line through the direct-mode path.

    Mirrors what app.py does for a non-numbered line: run the ':'-separated
    statements via _run_stmt_seq without a flattened program (no prepare_run).
    """
    io = MockIO()
    interp = Interpreter(io)
    interp.state = "RUN"
    interp.jumped = False
    interp._run_stmt_seq(tokenize(src))
    interp.state = "EDIT"
    if io._cur:
        io.out.append(io._cur)
    return io, interp


# ---------------------------------------------------------------------------
# Test body
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0


def check(name, got, expected):
    global PASS, FAIL
    if got == expected:
        PASS += 1
        print("  OK   %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s\n       got=%r\n       exp=%r" % (name, got, expected))


def test_tokenize():
    toks = tokenize('IF A = 10 THEN GOTO 100')
    check("tokenize IF", toks, [
        ("KW", "IF"), ("VAR", "A"), ("OP", "="), ("NUM", 10),
        ("KW", "THEN"), ("KW", "GOTO"), ("NUM", 100),
    ])
    toks = tokenize('PRINT LEFT$("ABC", 2)')
    check("tokenize LEFT$", toks, [
        ("KW", "PRINT"), ("KW", "LEFT$"), ("LP", "("),
        ("STR", "ABC"), ("COMMA", ","), ("NUM", 2), ("RP", ")"),
    ])


def test_print_expr():
    io, _ = run_program([
        (10, 'PRINT 1 + 2 * 3'),
        (20, 'PRINT 2 ^ 10'),
        (30, 'PRINT 7 MOD 3'),
    ])
    check("print arithmetic", io.out[:3], ["7", "1024", "1"])


def test_for_next():
    io, interp = run_program([
        (10, 'LET S = 0'),
        (20, 'FOR I = 1 TO 10'),
        (30, 'LET S = S + I'),
        (40, 'NEXT I'),
        (50, 'PRINT S'),
    ])
    check("for/next sum", io.out[0], "55")
    check("for var final", interp.get_var("I"), 11)


def test_for_step():
    io, _ = run_program([
        (10, 'FOR I = 10 TO 0 STEP -2'),
        (20, 'PRINT I;'),
        (30, 'PRINT " ";'),
        (40, 'NEXT I'),
    ])
    check("for step down", io.out[0], "10 8 6 4 2 0 ")


def test_if_goto():
    io, _ = run_program([
        (10, 'LET A = 5'),
        (20, 'IF A > 3 THEN GOTO 50'),
        (30, 'PRINT "SMALL"'),
        (40, 'GOTO 60'),
        (50, 'PRINT "BIG"'),
        (60, 'END'),
    ])
    check("if then goto", io.out[0], "BIG")


def test_if_implicit_goto():
    io, _ = run_program([
        (10, 'LET A = 1'),
        (20, 'IF A = 1 THEN 40'),
        (30, 'PRINT "NO"'),
        (40, 'PRINT "YES"'),
    ])
    check("if implicit goto", io.out[0], "YES")


def test_if_else():
    io, _ = run_program([
        (10, 'IF 1 = 1 THEN PRINT "T1" ELSE PRINT "F1"'),
        (20, 'IF 1 = 0 THEN PRINT "T2" ELSE PRINT "F2"'),
    ])
    check("if-else true branch", io.out[0], "T1")
    check("if-else false branch", io.out[1], "F2")


def test_if_else_implicit_goto():
    io, _ = run_program([
        (10, 'LET A = 0'),
        (20, 'IF A = 1 THEN 50 ELSE 40'),
        (30, 'PRINT "NO"'),
        (40, 'PRINT "ELSEGOTO"'),
        (45, 'GOTO 60'),
        (50, 'PRINT "THENGOTO"'),
        (60, 'END'),
    ])
    check("if-else implicit goto", io.out[0], "ELSEGOTO")


def test_multi_statement_seq():
    io, interp = run_program([
        (10, 'A = 1 : B = 2 : PRINT A + B'),
    ])
    check("colon sequence", io.out[0], "3")
    check("colon vars set", (interp.get_var("A"), interp.get_var("B")), (1, 2))


def test_multi_statement_for_next():
    io, _ = run_program([
        (10, 'FOR I = 1 TO 3 : PRINT I; : NEXT'),
    ])
    check("one-line for/next", io.out[0], "123")


def test_multi_statement_gosub_continue():
    io, _ = run_program([
        (10, 'GOSUB 100 : PRINT "BACK" : END'),
        (100, 'PRINT "SUB" : RETURN'),
    ])
    check("gosub mid-line continue", io.out[:2], ["SUB", "BACK"])


def test_if_then_multi_and_false_skips_rest():
    io, interp = run_program([
        (10, 'V = 0 : IF 1 = 1 THEN V = 1 : V = V + 1'),
        (20, 'W = 0 : IF 1 = 0 THEN W = 9 : W = W + 9'),
        (30, 'PRINT V; W'),
    ])
    # then-clause runs both statements; false IF skips the rest of its clause
    check("if-then multi true", interp.get_var("V"), 2)
    check("if-then false skips clause", interp.get_var("W"), 0)


def test_multi_statement_data_unaffected():
    io, _ = run_program([
        (10, 'DATA 11, 22, 33'),
        (20, 'READ P : READ Q : PRINT P + Q'),
    ])
    check("data with colon read", io.out[0], "33")


def test_direct_multi_statement():
    # Multi-statement ':' lines work in direct mode, not only during RUN.
    io, interp = run_direct('A = 1 : B = 2 : PRINT A + B')
    check("direct colon sequence", io.out[0], "3")
    check("direct colon vars set", (interp.get_var("A"), interp.get_var("B")), (1, 2))


def test_direct_if_then_multi():
    io, _ = run_direct('IF 1 = 1 THEN PRINT "YES" : PRINT "AGAIN"')
    check("direct if-then multi", io.out[:2], ["YES", "AGAIN"])


def test_direct_for_next_no_loop():
    # Known limitation: FOR/NEXT cannot loop in direct mode. The loop relies on
    # rewinding the program counter into self.code, which only exists during
    # RUN, so the body runs exactly once.
    io, _ = run_direct('FOR K = 1 TO 3 : PRINT K; : NEXT')
    check("direct for/next runs once", io.out, ["1"])


def test_string_funcs():
    io, _ = run_program([
        (10, 'LET A$ = "PYXELBASIC"'),
        (20, 'PRINT LEFT$(A$, 5)'),
        (30, 'PRINT RIGHT$(A$, 5)'),
        (40, 'PRINT MID$(A$, 6, 3)'),
        (50, 'PRINT LEN(A$)'),
        (60, 'PRINT CHR$(65); ASC("A")'),
    ])
    check("LEFT$", io.out[0], "PYXEL")
    check("RIGHT$", io.out[1], "BASIC")
    check("MID$", io.out[2], "BAS")
    check("LEN", io.out[3], "10")
    check("CHR$/ASC", io.out[4], "A65")


def test_array():
    io, _ = run_program([
        (10, 'DIM A(5)'),
        (20, 'FOR I = 0 TO 5'),
        (30, 'LET A(I) = I * I'),
        (40, 'NEXT I'),
        (50, 'PRINT A(0); " "; A(3); " "; A(5)'),
    ])
    check("array 1d", io.out[0], "0 9 25")


def test_array_2d():
    io, _ = run_program([
        (10, 'DIM M(2,2)'),
        (20, 'LET M(1,1) = 7'),
        (30, 'LET M(2,0) = 3'),
        (40, 'PRINT M(1,1); " "; M(2,0); " "; M(0,0)'),
    ])
    check("array 2d", io.out[0], "7 3 0")


def test_gosub():
    io, _ = run_program([
        (10, 'GOSUB 100'),
        (20, 'PRINT "BACK"'),
        (30, 'END'),
        (100, 'PRINT "SUB"'),
        (110, 'RETURN'),
    ])
    check("gosub/return", io.out[:2], ["SUB", "BACK"])


def test_data_read():
    io, _ = run_program([
        (10, 'DATA 10, 20, "HELLO"'),
        (20, 'READ A, B'),
        (30, 'READ C$'),
        (40, 'PRINT A + B; " "; C$'),
    ])
    check("data/read", io.out[0], "30 HELLO")


def test_data_signed_values():
    # DATA items may carry a leading +/- sign (regression: the sign used to be
    # dropped, so DATA -5 was read as 5).
    io, _ = run_program([
        (10, 'READ A, B, C'),
        (20, 'PRINT A; " "; B; " "; C'),
        (30, 'DATA -5, +7, -0.5'),
    ])
    check("data signed values", io.out[0], "-5 7 -0.5")


def test_data_unquoted_is_error():
    # Unquoted text in DATA is rejected (raised while pre-collecting at RUN),
    # instead of being silently skipped and later surfacing as "Out of DATA".
    interp = Interpreter(MockIO())
    interp.store_line(10, 'READ A$')
    interp.store_line(20, 'DATA HELLO')
    code = None
    try:
        interp.prepare_run()
    except BasicError as e:
        code = int(e.code)
    check("unquoted DATA raises 403", code, int(Err.INVALID_DATA))


def test_read_into_array():
    # READ must accept array-element targets (regression: A(i) used to assign a
    # scalar A and then stop at the '(').
    io, _ = run_program([
        (10, 'DIM A(3)'),
        (20, 'DIM M(2, 2)'),
        (30, 'READ A(0), A(1), A(2)'),
        (40, 'READ S, M(1, 1)'),
        (50, 'PRINT A(0); A(1); A(2); " "; S; M(1, 1)'),
        (60, 'DATA 11, 22, 33, 7, 99'),
    ])
    check("read into array", io.out[0], "112233 799")


def test_restore_line():
    # RESTORE <line> seeks the data pointer to that line's DATA.
    io, _ = run_program([
        (10, 'DATA 1, 2'),
        (20, 'DATA 30, 40'),
        (30, 'READ A'),
        (40, 'RESTORE 20'),
        (50, 'READ B, C'),
        (60, 'PRINT A; " "; B; " "; C'),
    ])
    check("restore to line", io.out[0], "1 30 40")


def test_restore_line_not_data():
    # RESTORE to a line that has no DATA is an error.
    io, _ = run_program([
        (10, 'PRINT "X"'),
        (20, 'DATA 5'),
        (30, 'RESTORE 10'),
    ])
    check("restore non-data line errors",
          any(("ERROR %d" % int(Err.RESTORE_NO_DATA)) in s for s in io.out), True)


def test_input():
    io, _ = run_program([
        (10, 'INPUT "NAME"; N$'),
        (20, 'INPUT "AGE"; A'),
        (30, 'PRINT N$; " IS "; A'),
    ], inputs=["TAKE", "30"])
    check("input", io.out[-1], "TAKE IS 30")


def test_logical():
    io, _ = run_program([
        (10, 'IF 1 = 1 AND 2 = 2 THEN PRINT "AND-OK"'),
        (20, 'IF 1 = 2 OR 3 = 3 THEN PRINT "OR-OK"'),
        (30, 'IF NOT (1 = 2) THEN PRINT "NOT-OK"'),
    ])
    check("logical and/or/not", io.out[:3], ["AND-OK", "OR-OK", "NOT-OK"])


def test_graphics():
    io, _ = run_program([
        (10, 'CLS'),
        (20, 'PSET (10, 20), 7'),
        (30, 'LINE (0,0)-(100,100), 11'),
    ])
    check("pset cmd", io.gfx[0], ("pset", 10, 20, 7))
    check("line cmd", io.gfx[1], ("line", 0, 0, 100, 100, 11))


def test_vsync():
    # Verify that VSYNC breaks frames (tested alone since PRINT also breaks)
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'FOR I = 1 TO 3')
    interp.store_line(20, 'VSYNC')
    interp.store_line(30, 'NEXT I')
    interp.prepare_run()
    frames = 0
    steps = 0
    while interp.state == "RUN" and steps < 10000:
        interp.step()
        steps += 1
        if interp.yield_frame:
            interp.yield_frame = False
            frames += 1
    check("vsync frame count", frames, 3)
    check("vsync loop done", interp.get_var("I"), 4)


def test_frame_break_flags():
    # Verify the per-statement frame-break flag decision
    def first_step_yield(src):
        io = MockIO()
        interp = Interpreter(io)
        interp.store_line(10, src)
        interp.store_line(20, 'END')
        interp.prepare_run()
        interp.step()   # run line 10
        return interp.yield_frame

    check("PRINT breaks", first_step_yield('PRINT "A"'), True)
    check("PSET breaks", first_step_yield('PSET (1,1), 7'), True)
    check("LINE breaks", first_step_yield('LINE (0,0)-(1,1), 7'), True)
    check("STICK breaks", first_step_yield('A = STICK(0)'), True)
    check("BUTTON breaks", first_step_yield('A = BUTTON(0)'), True)
    check("LET no break", first_step_yield('LET A = 1'), False)
    check("GOTO no break", first_step_yield('GOTO 20'), False)


def test_vsync_config_off_on():
    # VSYNC <word> OFF / ON can change the break targets at runtime
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'VSYNC PSET OFF')
    interp.store_line(20, 'PSET (1,1), 7')
    interp.store_line(30, 'VSYNC PSET ON')
    interp.store_line(40, 'PSET (2,2), 7')
    interp.prepare_run()
    interp.step()   # VSYNC PSET OFF
    check("config cmd no yield", interp.yield_frame, False)
    check("PSET removed", "PSET" in interp.frame_break, False)
    interp.step()   # PSET (no break since it is OFF)
    check("PSET no break after OFF", interp.yield_frame, False)
    interp.step()   # VSYNC PSET ON
    check("PSET re-added", "PSET" in interp.frame_break, True)
    interp.step()   # PSET (breaks since it is ON)
    check("PSET break after ON", interp.yield_frame, True)


def test_vsync_bad_word():
    # Specifying a nonexistent reserved word is an error (it becomes a VAR token)
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'VSYNC FOO ON')
    interp.prepare_run()
    interp.step()
    check("bad word -> error", any("ERROR" in s for s in io.out), True)


def test_vsync_list():
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'VSYNC LIST')
    interp.prepare_run()
    interp.step()
    check("vsync list output", any("FRAME BREAK" in s for s in io.out), True)


def test_vsync_reset():
    # VSYNC RESET restores the initial state (can run mid-program)
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'VSYNC PRINT OFF')
    interp.store_line(20, 'VSYNC LINE OFF')
    interp.store_line(30, 'VSYNC RESET')
    interp.prepare_run()
    interp.step()   # PRINT OFF
    interp.step()   # LINE OFF
    check("changed before reset", interp.frame_break == set(FRAME_BREAK), False)
    interp.step()   # RESET
    check("restored after reset", interp.frame_break == set(FRAME_BREAK), True)


def test_mod_fraction():
    # MOD integerizes both sides; a divisor with 0 < |b| < 1 integerizes to 0,
    # which must raise a BASIC error (not crash with a Python ZeroDivisionError).
    io, _ = run_program([(10, 'PRINT 0.0003 MOD 0.1')])
    check("mod by fraction -> error", any("ERROR" in s for s in io.out), True)
    io, _ = run_program([(10, 'PRINT 7.9 MOD 3.9')])
    check("mod integerizes operands", io.out[0], "1")


def test_vsync_clear():
    # VSYNC CLEAR removes every automatic break target; an explicit VSYNC still works.
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'VSYNC CLEAR')
    interp.prepare_run()
    interp.step()   # CLEAR
    check("cleared frame_break empty", interp.frame_break, set())
    # An explicit VSYNC still requests a frame break even after CLEAR.
    interp.yield_frame = False
    interp.store_line(20, 'VSYNC')
    interp.prepare_run()
    interp.step()   # CLEAR (re-run from line 10)
    interp.step()   # VSYNC (explicit)
    check("explicit vsync still breaks", interp.yield_frame, True)


def test_new_resets_framebreak():
    # NEW also restores the break config to its initial state
    io = MockIO()
    interp = Interpreter(io)
    interp.frame_break.discard("PRINT")
    interp.new_program()
    check("new restores framebreak", interp.frame_break == set(FRAME_BREAK), True)


def test_renum():
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(1, 'PRINT "A"')
    interp.store_line(5, 'GOTO 1')
    interp.renum(100, 10)
    lines = interp.list_lines()
    check("renum numbers", [ln for ln, _ in lines], [100, 110])
    check("renum goto ref", "100" in lines[1][1], True)


def test_renum_keeps_rem():
    # RENUM must not blank REM lines (regression: tokenize drops the comment, so
    # round-tripping a REM line through detokenize used to leave an empty line).
    io = MockIO()
    interp = Interpreter(io)
    interp.store_line(10, 'REM ===== HEADER =====')
    interp.store_line(20, 'PRINT "HI"')
    interp.store_line(30, 'GOTO 20')
    interp.renum(100, 10)
    prog = dict(interp.list_lines())
    check("renum keeps REM text", prog.get(100), 'REM ===== HEADER =====')
    check("renum keeps plain line", prog.get(110), 'PRINT "HI"')
    check("renum remaps goto", prog.get(120), 'GOTO 110')


def test_store_uppercases_code():
    # Lines are upper-cased when registered, but string literals and REM comment
    # text are preserved as typed.
    interp = Interpreter(MockIO())
    interp.store_line(10, 'print left$("AbC", 2)')
    interp.store_line(20, 'rem Keep This Case')
    interp.store_line(30, 'for i=1 to 5')
    prog = dict(interp.list_lines())
    check("upper code, keep string", prog.get(10), 'PRINT LEFT$("AbC", 2)')
    check("upper REM, keep comment", prog.get(20), 'REM Keep This Case')
    check("upper plain", prog.get(30), 'FOR I=1 TO 5')


def test_dispatch_registration():
    # STATEMENTS / FUNCTIONS are derived in keywords.py from the handler maps
    # (STATEMENT_HANDLERS / FUNCTION_HANDLERS / MATH1). Pin their contents so a
    # missing or stray keyword is caught. Expected values mirror the original
    # hand-written sets.
    expected_statements = {
        "PRINT", "INPUT", "LET", "GOTO", "GOSUB", "RETURN", "IF",
        "FOR", "NEXT", "DIM", "REM", "CLS", "LOCATE", "COLOR",
        "PSET", "LINE", "END", "STOP", "DATA", "READ", "RESTORE",
        "RANDOMIZE", "VSYNC",
    }
    expected_functions = {
        "LEN", "LEFT$", "RIGHT$", "MID$", "CHR$", "ASC", "STR$", "VAL",
        "ABS", "SGN", "INT", "FIX", "ROUND",
        "SIN", "COS", "TAN", "ATN", "RAD", "DEG",
        "EXP", "LOG", "LOG10", "SQR",
        "RND", "INKEY$", "STICK", "BUTTON",
    }
    check("dispatch statements set", STATEMENTS, expected_statements)
    check("dispatch functions set", FUNCTIONS, expected_functions)


def test_alltest_sample():
    # Run the bundled all-command sample headlessly and require every self-check
    # to pass (F == 0) with no error lines. Keeps the sample honest over time.
    path = os.path.join(os.path.dirname(__file__), "..", "samples", "alltest.bas")
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if s and s[0].isdigit():
                i = 0
                while i < len(s) and s[i].isdigit():
                    i += 1
                lines.append((int(s[:i]), s[i:].strip()))
    io, interp = run_program(lines, inputs=["TEST"])
    check("alltest reaches END", interp.state, "END")
    check("alltest no failures (F=0)", interp.get_var("F"), 0)
    bad = [s for s in io.out if s.startswith("NG") or "ERROR" in s]
    check("alltest no NG/ERROR lines", bad, [])


def main():
    for fn in [
        test_tokenize, test_print_expr, test_for_next, test_for_step,
        test_if_goto, test_if_implicit_goto,
        test_if_else, test_if_else_implicit_goto, test_multi_statement_seq,
        test_multi_statement_for_next, test_multi_statement_gosub_continue,
        test_if_then_multi_and_false_skips_rest,
        test_multi_statement_data_unaffected,
        test_direct_multi_statement, test_direct_if_then_multi,
        test_direct_for_next_no_loop,
        test_string_funcs,
        test_array, test_array_2d, test_gosub, test_data_read,
        test_data_signed_values, test_data_unquoted_is_error,
        test_read_into_array,
        test_restore_line, test_restore_line_not_data,
        test_input, test_logical, test_graphics, test_vsync,
        test_frame_break_flags, test_vsync_config_off_on,
        test_vsync_bad_word, test_vsync_list, test_vsync_reset,
        test_vsync_clear, test_mod_fraction,
        test_new_resets_framebreak, test_renum, test_renum_keeps_rem,
        test_store_uppercases_code,
        test_dispatch_registration, test_alltest_sample,
    ]:
        print(fn.__name__)
        fn()
    print("\nResult: %d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
