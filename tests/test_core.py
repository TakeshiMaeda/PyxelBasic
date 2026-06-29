# -*- coding: utf-8 -*-
"""Headless tests for the interpreter core.

Verifies language features using a Pyxel-independent MockIO.
Run:  python tests/test_core.py
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyxelbasic.interpreter import (  # noqa: E402
    Interpreter, tokenize, basic_str, BasicError,
)
from pyxelbasic.errors import Err  # noqa: E402
from pyxelbasic.keywords import STATEMENTS, FUNCTIONS  # noqa: E402
from pyxelbasic.runtime import (  # noqa: E402
    InputState, CommandQueue, DirectGraphics,
    InputRing, KeyState, SpriteTable, sprite8_pixel, sprite16_pixel,
    EV_CHAR, EV_DOWN, EV_UP, EV_REPEAT,
)
from pyxelbasic.keywords import (  # noqa: E402
    KEY_UP, KEY_LEFT, KEY_BTN0, KEY_BTN1,
)
from pyxelbasic.textscreen import TextScreen  # noqa: E402
from pyxelbasic.editor import Editor  # noqa: E402
from pyxelbasic.session import Session, STEPS_PER_FRAME, parse_list_range  # noqa: E402


class MockIO:
    """Test IO that accumulates screen output as strings."""

    def __init__(self, inputs=None):
        self.out = []
        self._cur = ""        # current line buffer (named to avoid clashing with the line method)
        self.gfx = []
        self.pixels = {}      # (x, y) -> color, fed by pset; read back by point
        self.inputs = list(inputs or [])
        self.sprite_sets = []   # (no, colors) recorded by set_sprite
        self.sprite_puts = []   # (id, x, y, no, size, colkey) recorded by put_sprite
        self.sprite_offs = []   # id recorded by put_sprite_off
        self.play_calls = []    # audio calls recorded by play_channels/play_ch/play_stop
        self._playing = set()   # channels currently "playing" (for the PLAY() function)
        self.invalid_mmls = set()  # MMLs to treat as invalid (return them as the error)

    def print_text(self, text):
        self._cur += text

    def print_line(self, text):
        self._cur += text
        self.out.append(self._cur)
        self._cur = ""

    def cls(self, mask=3):
        self.out.append("<CLS %d>" % mask)
        if mask & 2:
            self.pixels.clear()

    def set_color(self, col):
        pass

    def locate(self, x, y):
        pass

    def pset(self, x, y, col=None):
        self.gfx.append(("pset", x, y, col))
        self.pixels[(x, y)] = col

    def line(self, x1, y1, x2, y2, col=None):
        self.gfx.append(("line", x1, y1, x2, y2, col))

    def rect(self, x1, y1, x2, y2, col=None):
        self.gfx.append(("rect", x1, y1, x2, y2, col))

    def rectb(self, x1, y1, x2, y2, col=None):
        self.gfx.append(("rectb", x1, y1, x2, y2, col))

    def elli(self, x, y, rx, ry, col=None):
        self.gfx.append(("elli", x, y, rx, ry, col))

    def ellib(self, x, y, rx, ry, col=None):
        self.gfx.append(("ellib", x, y, rx, ry, col))

    def tri(self, x1, y1, x2, y2, x3, y3, col=None):
        self.gfx.append(("tri", x1, y1, x2, y2, x3, y3, col))

    def point(self, x, y):
        return self.pixels.get((x, y), 0)

    def set_sprite(self, no, colors):
        self.sprite_sets.append((no, colors))

    def put_sprite(self, sid, x, y, no, size, colkey):
        self.sprite_puts.append((sid, x, y, no, size, colkey))

    def put_sprite_off(self, sid):
        self.sprite_offs.append(sid)

    def play_channels(self, mmls, loop):
        self.play_calls.append(("channels", list(mmls), loop))
        for ch in range(4):
            if ch < len(mmls) and mmls[ch]:
                if mmls[ch] in self.invalid_mmls:
                    return mmls[ch]
                self._playing.add(ch)
        return None

    def play_ch(self, ch, mml, loop):
        self.play_calls.append(("ch", ch, mml, loop))
        if mml:
            if mml in self.invalid_mmls:
                return mml
            self._playing.add(ch)
        return None

    def play_stop(self, channels):
        self.play_calls.append(("stop", list(channels)))
        if channels:
            for ch in channels:
                self._playing.discard(ch)
        else:
            self._playing.clear()

    def playing(self, ch):
        return 1 if ch in self._playing else 0

    def inkey(self):
        return ""

    def stick(self, n):
        return 0

    def button(self, n):
        return 0


def run_program(lines, inputs=None, max_steps=100000, io=None):
    if io is None:
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


def test_hex():
    # &H literals (input), HEX$ (output), and VAL parsing of &H strings.
    io, _ = run_program([
        (10, 'A = &HFF'),
        (20, 'PRINT A'),
        (30, 'PRINT &H10; " "; &HaB'),     # case-insensitive digits
        (40, 'PRINT HEX$(255); " "; HEX$(16)'),
        (50, 'PRINT HEX$(-255)'),           # negative keeps a sign
        (60, 'PRINT VAL("&HFF"); " "; VAL("&hff")'),
        (70, 'PRINT VAL("&H"); " "; VAL("45")'),  # bad hex -> 0, decimal intact
    ])
    check("&H literal", io.out[0], "255")
    check("&H literal case", io.out[1], "16 171")
    check("HEX$", io.out[2], "FF 10")
    check("HEX$ negative", io.out[3], "-FF")
    check("VAL &H", io.out[4], "255 255")
    check("VAL bad hex / decimal", io.out[5], "0 45")


def test_hex_literal_error():
    # &H with no hex digits is a tokenizer error.
    code = None
    try:
        tokenize('A = &H')
    except BasicError as e:
        code = int(e.code)
    check("&H without digits raises 122", code, int(Err.INVALID_HEX_LITERAL))


def test_hex_renum_roundtrip():
    # A hex literal on a GOTO/GOSUB/THEN line is rewritten via detokenize during
    # RENUM; it must round-trip back to &H form (not collapse to decimal), while
    # the referenced line number is still renumbered.
    interp = Interpreter(MockIO())
    interp.store_line(10, 'IF A = &HFF THEN 100')
    interp.store_line(100, 'PRINT &H10')
    interp.renum(200, 5)
    lines = dict(interp.list_lines())
    check("RENUM keeps &H on THEN line", lines[200], "IF A = &HFF THEN 205")
    check("RENUM keeps &H on plain line", lines[205], "PRINT &H10")


def test_arg_count_error():
    # Calling a function with the wrong number of arguments is a BasicError
    # (code 123), not a Python crash. This covers too few (including none),
    # too many, and the single-argument math path (MATH1). The check happens in
    # parse_function before the handler runs, so handlers never see a short list.
    def err_code(expr):
        # A runtime error is caught in step() and printed as "?ERROR <code> ...";
        # pull the code back out of that line.
        io, _ = run_program([(10, 'PRINT ' + expr)])
        for line in io.out:
            if line.startswith("?ERROR "):
                return int(line.split()[1])
        return None

    want = int(Err.WRONG_ARG_COUNT)
    check("HEX$() no arg", err_code('HEX$()'), want)
    check("VAL() no arg", err_code('VAL()'), want)
    check("LEN() no arg", err_code('LEN()'), want)
    check("MID$ too few", err_code('MID$("AB")'), want)
    check("MID$ too many", err_code('MID$("A",1,2,3)'), want)
    check("POINT too few", err_code('POINT(1)'), want)
    check("SIN() math no arg", err_code('SIN()'), want)
    check("HEX$ too many", err_code('HEX$(255,1)'), want)
    # Valid call counts still evaluate (no false positives).
    io, _ = run_program([(10, 'PRINT HEX$(255); MID$("ABCDE",2,2)')])
    check("valid arg counts still work", io.out[0], "FFBC")


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


def test_cls_args():
    io, _ = run_program([
        (10, 'CLS 1'),
        (20, 'CLS 2'),
        (30, 'CLS 3'),
        (40, 'CLS'),
    ])
    masks = [s for s in io.out if s.startswith("<CLS")]
    check("cls masks", masks, ["<CLS 1>", "<CLS 2>", "<CLS 3>", "<CLS 3>"])


def test_cls_mask_range():
    # The mask is used as bit flags; a value outside 1..3 used to silently clear
    # an unexpected subset (or nothing) with no error. Now it is rejected. 0 is
    # rejected too, since it would read like a bare CLS but do nothing.
    check("cls 1 ok", _err_code([(10, 'CLS 1')]), None)
    check("cls 3 ok", _err_code([(10, 'CLS 3')]), None)
    check("cls 0 errors", _err_code([(10, 'CLS 0')]), int(Err.INVALID_CLS_MASK))
    check("cls 4 errors", _err_code([(10, 'CLS 4')]), int(Err.INVALID_CLS_MASK))
    check("cls -1 errors", _err_code([(10, 'CLS -1')]), int(Err.INVALID_CLS_MASK))


def test_list_range():
    check("list all", parse_list_range(tokenize("LIST")), (None, None))
    check("list single", parse_list_range(tokenize("LIST 100")), (100, 100))
    check("list both", parse_list_range(tokenize("LIST 100-200")), (100, 200))
    check("list from-top", parse_list_range(tokenize("LIST -100")), (None, 100))
    check("list to-end", parse_list_range(tokenize("LIST 200-")), (200, None))


def test_lineb():
    io, _ = run_program([
        (10, 'LINEB (10,10)-(60,40), 8'),
        (20, 'LINEBF (0,0)-(20,20), 9'),
    ])
    check("lineb cmd", io.gfx[0], ("rectb", 10, 10, 60, 40, 8))
    check("linebf cmd", io.gfx[1], ("rect", 0, 0, 20, 20, 9))


def test_circle_full():
    io, _ = run_program([
        (10, 'CIRCLE (80,80), 10, 11'),
        (20, 'CIRCLEBF (40,40), 8, 12'),
    ])
    check("circle outline = ellib", io.gfx[0], ("ellib", 80, 80, 10, 10, 11))
    check("circlebf fill = elli", io.gfx[1], ("elli", 40, 40, 8, 8, 12))


def test_circle_ratio():
    # ratio > 1 -> tall (ry=r, rx=r/ratio); ratio < 1 -> wide (rx=r, ry=r*ratio).
    io, _ = run_program([
        (10, 'CIRCLE (50,50), 20, 7, , , 2'),
        (20, 'CIRCLE (50,50), 20, 7, , , 0.5'),
    ])
    check("ratio>1 tall", io.gfx[0], ("ellib", 50, 50, 10, 20, 7))
    check("ratio<1 wide", io.gfx[1], ("ellib", 50, 50, 20, 10, 7))


def test_circle_arc():
    # An angle range rasterizes to line segments (no ellib/elli emitted).
    io, _ = run_program([
        (10, 'CIRCLE (80,80), 20, 11, 0, 1.5'),
    ])
    kinds = {g[0] for g in io.gfx}
    check("arc uses line segments", "line" in kinds, True)
    check("arc emits no full ellipse", "ellib" in kinds or "elli" in kinds, False)


def test_point():
    io, _ = run_program([
        (10, 'PSET (5,7), 9'),
        (20, 'C = POINT(5,7)'),
        (30, 'PRINT C'),
        (40, 'PRINT POINT(1,1)'),
    ])
    check("point reads set pixel", io.out[0], "9")
    check("point reads empty pixel", io.out[1], "0")


def test_command_queue_pget():
    # In threaded mode POINT cannot touch the (main-thread-only) Pyxel image, so
    # the read round-trips through the queue: the VM thread enqueues a request
    # and blocks until the main thread services it during drain().
    class DummySurface:
        def pget(self, x, y):
            return 42 if (x, y) == (5, 7) else 0

    q = CommandQueue()
    surf = DummySurface()
    result = {}

    def reader():
        result["v"] = q.pget(5, 7)

    t = threading.Thread(target=reader)
    t.start()
    # Act as the main thread: drain until the blocked reader gets its value.
    for _ in range(1000):
        q.drain(surf)
        if not t.is_alive():
            break
        time.sleep(0.001)
    t.join(timeout=1.0)
    check("queue pget round-trip", result.get("v"), 42)

    # Once stopped, a pget returns 0 immediately without needing a drain.
    q.stop()
    check("queue pget after stop", q.pget(9, 9), 0)


def test_vsync_noop():
    # VSYNC is a no-op now (frame pacing is the VM throttle). Only VSYNC LIST
    # still prints the historical frame-break list; every other form runs
    # without error and does nothing.
    io, _ = run_program([
        (10, 'VSYNC'),
        (20, 'VSYNC LINE OFF'),
        (30, 'VSYNC FOO ON'),
        (40, 'VSYNC RESET'),
        (50, 'PRINT "DONE"'),
    ])
    check("vsync no-op runs clean", io.out[-1], "DONE")
    check("vsync no-op raises nothing", any("ERROR" in s for s in io.out), False)
    io2, _ = run_program([(10, 'VSYNC LIST')])
    check("vsync list still prints", any("FRAME BREAK" in s for s in io2.out), True)


def test_vsync_threaded_no_framebreak():
    # Threaded mode (vsync_enabled defaults False): frame_break stays empty and
    # the interpreter never yields, even on PRINT / STICK.
    io = MockIO()
    interp = Interpreter(io)
    check("threaded frame_break empty", interp.frame_break, set())
    for ln, src in [(10, 'PRINT STICK(0)'), (20, 'PRINT "X"'), (30, 'END')]:
        interp.store_line(ln, src)
    interp.prepare_run()
    while interp.state == "RUN":
        interp.step()
    check("threaded never yields", interp.yield_frame, False)


def test_vsync_main_mode_control():
    # Main-driven mode (vsync_enabled True): the classic frame-break controls.
    io = MockIO()
    interp = Interpreter(io, vsync_enabled=True)
    check("main frame_break has PRINT", "PRINT" in interp.frame_break, True)
    interp.state = "RUN"
    interp.jumped = False
    interp._run_stmt_seq(tokenize("VSYNC LIST"))
    check("vsync list shows words", io.out[-1].startswith("FRAME BREAK: "), True)
    check("vsync list not none", "(none)" in io.out[-1], False)
    interp._run_stmt_seq(tokenize("VSYNC CLEAR"))
    check("vsync clear empties", interp.frame_break, set())
    interp._run_stmt_seq(tokenize("VSYNC PRINT ON"))
    check("vsync word on", "PRINT" in interp.frame_break, True)
    interp._run_stmt_seq(tokenize("VSYNC PRINT OFF"))
    check("vsync word off", "PRINT" not in interp.frame_break, True)
    interp._run_stmt_seq(tokenize("VSYNC RESET"))
    check("vsync reset restores", "STICK" in interp.frame_break, True)


def test_vsync_main_mode_yield_on_eval():
    # A frame-break statement/function sets yield_frame after the step.
    io = MockIO()
    interp = Interpreter(io, vsync_enabled=True)
    for ln, src in [(10, 'PRINT STICK(0)'), (20, 'END')]:
        interp.store_line(ln, src)
    interp.prepare_run()
    interp.step()
    check("main mode yields on frame-break", interp.yield_frame, True)


def test_session_run_frame_yields():
    # Session.run_frame honours yield_frame: one frame-break statement per frame.
    gfx = _Recorder()
    s = Session(64, 42, DirectGraphics(gfx), InputRing(), vsync_enabled=True)
    for ln, src in [(10, 'PRINT "A"'), (20, 'PRINT "B"'), (30, 'END')]:
        s.interp.store_line(ln, src)
    s._start_run()
    s.run_frame(STEPS_PER_FRAME)
    check("run_frame yields after frame-break", s.interp.cur_line, 10)
    check("session still running", s.mode, "RUN")
    s.run_frame(STEPS_PER_FRAME)
    check("next frame advances", s.interp.cur_line, 20)
    s.run_frame(STEPS_PER_FRAME)   # runs line 30 (END) -> back to edit mode
    check("session ends", s.mode, "EDIT")


def test_break_stops_sound():
    # Ctrl+C (request_break) must abort the run AND stop all sound channels.
    rec = _Recorder()
    s = Session(64, 42, DirectGraphics(_Recorder()), InputRing(),
                audio=DirectGraphics(rec))
    for ln, src in [(10, 'PRINT "A"'), (20, 'GOTO 10')]:
        s.interp.store_line(ln, src)
    s._start_run()
    s.run_frame(STEPS_PER_FRAME)     # run the loop for a frame
    check("running before break", s.mode, "RUN")
    s.request_break()
    s.run_frame(STEPS_PER_FRAME)     # next frame processes the break
    check("break returns to edit", s.mode, "EDIT")
    check("break issued play_stop", ("play_stop", []) in rec.calls, True)


def test_direct_graphics_immediate():
    # DirectGraphics applies each put() to the surface immediately (no queue).
    rec = _Recorder()
    d = DirectGraphics(rec)
    d.put(("pset", (1, 2, 7)))
    d.put(("cls", ()))
    check("direct gfx immediate", rec.calls, [("pset", 1, 2, 7), ("cls",)])
    # The queue-compatible methods are no-ops and must not raise.
    d.drain(rec)
    d.wait_empty()
    d.stop()
    d.reset()
    check("direct gfx noop methods", len(rec.calls), 2)


def test_mod_fraction():
    # MOD integerizes both sides; a divisor with 0 < |b| < 1 integerizes to 0,
    # which must raise a BASIC error (not crash with a Python ZeroDivisionError).
    io, _ = run_program([(10, 'PRINT 0.0003 MOD 0.1')])
    check("mod by fraction -> error", any("ERROR" in s for s in io.out), True)
    io, _ = run_program([(10, 'PRINT 7.9 MOD 3.9')])
    check("mod integerizes operands", io.out[0], "1")


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


class _Recorder:
    """Records any method call as (name, *args) for queue/IO tests."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def f(*args):
            self.calls.append((name,) + args)
        return f


def test_runtime_input_state():
    inp = InputState()
    check("input default", (inp.get_key_char(), inp.get_stick(), inp.get_button(0)),
          ("", 0, 0))
    inp.update("A", 5, [1, 0, 1, 0])
    check("input updated", (inp.get_key_char(), inp.get_stick()), ("A", 5))
    check("input button on/off", (inp.get_button(0), inp.get_button(1)), (1, 0))
    check("input button oob", inp.get_button(9), 0)


def test_runtime_command_queue_order():
    q = CommandQueue(capacity=4)
    q.put(("cls", ()))
    q.put(("print_text", ("HI",)))
    q.put(("pset", (1, 2, 7)))
    rec = _Recorder()
    q.drain(rec)
    check("queue applies in order", rec.calls,
          [("cls",), ("print_text", "HI"), ("pset", 1, 2, 7)])
    q.wait_empty()   # already empty -> returns immediately
    check("queue empty after drain", len(q._dq), 0)


def test_runtime_command_queue_backpressure():
    # A small queue must throttle a fast producer without losing/reordering.
    import threading
    import time
    q = CommandQueue(capacity=2)
    rec = _Recorder()

    def producer():
        for i in range(6):
            q.put(("print_text", (str(i),)))

    t = threading.Thread(target=producer)
    t.start()
    deadline = time.time() + 3
    while (t.is_alive() or len(rec.calls) < 6) and time.time() < deadline:
        q.drain(rec)
        time.sleep(0.001)
    t.join(timeout=1)
    q.drain(rec)
    check("backpressure delivers all in order",
          [c[1] for c in rec.calls], ["0", "1", "2", "3", "4", "5"])


def test_input_ring():
    ring = InputRing(capacity=3)
    check("ring push ok", ring.push((EV_CHAR, "A")), True)
    ring.push((EV_DOWN, KEY_UP))
    ring.push((EV_CHAR, "B"))
    check("ring full drops newest", ring.push((EV_CHAR, "C")), False)
    items = ring.drain()
    check("ring drains in order", items,
          [(EV_CHAR, "A"), (EV_DOWN, KEY_UP), (EV_CHAR, "B")])
    check("ring empty after drain", ring.drain(), [])


def test_key_state_stick_button():
    ks = KeyState()
    ks.apply_all([(EV_DOWN, KEY_UP), (EV_DOWN, KEY_LEFT), (EV_DOWN, KEY_BTN0)])
    check("stick up+left bits", ks.stick(0), 1 | 4)
    check("button0 down", ks.button(0), 1)
    check("button1 up", ks.button(1), 0)
    # releasing clears the held state
    ks.apply((EV_UP, KEY_LEFT))
    check("stick after release", ks.stick(0), 1)
    # a repeat event does not change the held set
    ks.apply((EV_REPEAT, KEY_UP))
    check("repeat no level change", ks.stick(0), 1)


def test_key_state_inkey_typeahead():
    ks = KeyState()
    ks.apply_all([(EV_CHAR, "H"), (EV_CHAR, "I")])
    check("inkey pop 1", ks.inkey(), "H")
    check("inkey pop 2", ks.inkey(), "I")
    check("inkey empty", ks.inkey(), "")


def _screen_rows(ts):
    return ["".join(ts.chars[y]).rstrip() for y in range(ts.rows)]


def test_textscreen_print_wrap():
    ts = TextScreen(cols=8, rows=4)
    ts.print_line("HELLO")
    check("ts print line", _screen_rows(ts)[0], "HELLO")
    ts2 = TextScreen(cols=8, rows=4)
    ts2.print_text("ABCDEFGHIJ")   # 10 chars wrap on an 8-wide screen
    check("ts wrap row0", "".join(ts2.chars[0]), "ABCDEFGH")
    check("ts wrap row1", "".join(ts2.chars[1]).rstrip(), "IJ")
    check("ts wrap continuation", ts2.cont[1], True)


def test_textscreen_scroll_length_invariant():
    ts = TextScreen(cols=8, rows=3)
    for i in range(5):
        ts.print_line("L%d" % i)
    check("ts scroll length invariant",
          (len(ts.chars), len(ts.cols_color), len(ts.cont)), (3, 3, 3))
    check("ts scroll keeps recent", "L4" in _screen_rows(ts), True)


def test_textscreen_logical_text():
    ts = TextScreen(cols=8, rows=4)
    ts.print_text("ABCDEFGHIJ")   # one wrapped logical line across rows 0-1
    text, r, s = ts.get_logical_text(1)
    check("ts logical text joins wrap", text, "ABCDEFGHIJ")
    check("ts logical span", (r, s), (0, 1))


def test_textscreen_snapshot():
    ts = TextScreen(cols=8, rows=4)
    ts.print_text("AB")
    snap = ts.snapshot()
    v = snap.version
    check("snap content", snap.chars[0][0], "A")
    check("snap cursor", (snap.cx, snap.cy), (2, 0))
    ts.print_text("C")
    check("snap is immutable", snap.chars[0][2], " ")
    check("snap version bumps on change", ts.snapshot().version > v, True)


def test_editor_type_delete():
    ts = TextScreen(cols=16, rows=4)
    ed = Editor(ts)
    for ch in "HELLO":
        ed.type_char(ch)
    check("editor typed", ts.get_logical_text(0)[0], "HELLO")
    ed.move_left()
    ed.move_left()                 # caret before the 2nd 'L' (index 3)
    ed.type_char("X")
    check("editor insert mid", ts.get_logical_text(0)[0], "HELXLO")
    ed.backspace()
    check("editor backspace", ts.get_logical_text(0)[0], "HELLO")
    ed.delete_at()
    check("editor delete_at", ts.get_logical_text(0)[0], "HELO")


def test_editor_overtype():
    ts = TextScreen(cols=16, rows=4)
    ed = Editor(ts)
    for ch in "ABCD":
        ed.type_char(ch)
    ed.home()
    ed.toggle_insert()             # switch to overtype
    ed.type_char("Z")
    check("editor overtype", ts.get_logical_text(0)[0], "ZBCD")


def test_editor_reflow_wrap():
    ts = TextScreen(cols=4, rows=6)
    ed = Editor(ts)
    for ch in "ABCDEF":            # wraps to two rows as one logical line
        ed.type_char(ch)
    check("editor wrapped text", ts.get_logical_text(0)[0], "ABCDEF")
    check("editor wrapped continuation", ts.cont[1], True)
    ed.home()
    ed.type_char("X")
    check("editor reflow on insert", ts.get_logical_text(0)[0], "XABCDEF")


def _err_code(lines):
    """Run a program and return the code of the first ?ERROR line (or None)."""
    io, _ = run_program(lines)
    for line in io.out:
        if line.startswith("?ERROR "):
            return int(line.split()[1])
    return None


def test_set_sprite():
    # 64 hex chars define one 8x8 pattern; each char is one pixel colour.
    io, _ = run_program([(10, 'SET SPRITE 0, "' + "0123456789ABCDEF" * 4 + '"')])
    no, colors = io.sprite_sets[0]
    check("set_sprite no/len", (no, len(colors)), (0, 64))
    check("set_sprite decode", colors[:16],
          [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
    # A short string is padded with '0' up to a full 64-char pattern.
    io, _ = run_program([(10, 'SET SPRITE 5, "FF"')])
    no, colors = io.sprite_sets[0]
    check("set_sprite short padded", (no, len(colors), colors[:3]), (5, 64, [15, 15, 0]))
    # 128 chars store two consecutive 8x8 patterns in one call.
    io, _ = run_program([(10, 'SET SPRITE 0, "' + "A" * 128 + '"')])
    check("set_sprite two patterns", (io.sprite_sets[0][0], len(io.sprite_sets[0][1])), (0, 128))
    # Lowercase hex digits are allowed (string literals keep their case).
    io, _ = run_program([(10, 'SET SPRITE 0, "abcdef00"')])
    check("set_sprite lowercase", io.sprite_sets[0][1][:6], [10, 11, 12, 13, 14, 15])


def test_set_sprite_errors():
    check("set invalid char", _err_code([(10, 'SET SPRITE 0, "XYZ"')]),
          int(Err.INVALID_SPRITE_DATA))
    check("set no out of range", _err_code([(10, 'SET SPRITE 1024, "FF"')]),
          int(Err.SPRITE_OUT_OF_RANGE))
    # Two patterns starting at 1023 spill past the last pattern (1023).
    check("set overflow", _err_code([(10, 'SET SPRITE 1023, "' + "A" * 128 + '"')]),
          int(Err.SPRITE_PATTERN_OVERFLOW))


def test_put_sprite():
    io, _ = run_program([
        (10, 'PUT SPRITE 3, (40, 50), 7, 0'),
        (20, 'PUT SPRITE 4, (10, 20), 2, 1, 5'),
    ])
    check("put default colkey -1", io.sprite_puts[0], (3, 40, 50, 7, 0, -1))
    check("put with colkey", io.sprite_puts[1], (4, 10, 20, 2, 1, 5))
    # no = 255 is valid for a 16x16 sprite (max 255).
    io, _ = run_program([(10, 'PUT SPRITE 0, (0, 0), 255, 1')])
    check("put no 255 ok for 16x16", io.sprite_puts[0], (0, 0, 0, 255, 1, -1))


def test_put_sprite_off():
    io, _ = run_program([(10, 'PUT SPRITE 9, OFF')])
    check("put off records id", io.sprite_offs, [9])
    check("put off extra args error", _err_code([(10, 'PUT SPRITE 9, OFF, 1')]),
          int(Err.INVALID_SPRITE_SYNTAX))


def test_put_sprite_errors():
    check("put id oob", _err_code([(10, 'PUT SPRITE 1024, (0, 0), 0, 0')]),
          int(Err.SPRITE_OUT_OF_RANGE))
    check("put size oob", _err_code([(10, 'PUT SPRITE 0, (0, 0), 0, 2')]),
          int(Err.SPRITE_OUT_OF_RANGE))
    check("put no oob 8x8", _err_code([(10, 'PUT SPRITE 0, (0, 0), 1024, 0')]),
          int(Err.SPRITE_OUT_OF_RANGE))
    check("put no oob 16x16", _err_code([(10, 'PUT SPRITE 0, (0, 0), 256, 1')]),
          int(Err.SPRITE_OUT_OF_RANGE))
    check("put colkey oob", _err_code([(10, 'PUT SPRITE 0, (0, 0), 0, 0, 16')]),
          int(Err.SPRITE_OUT_OF_RANGE))


def test_sprite_framebreak():
    # main-driven mode: PUT SPRITE is a frame-break (updates the display table
    # each game-loop frame); SET SPRITE is not (it is pattern setup).
    io = MockIO()
    interp = Interpreter(io, vsync_enabled=True)
    for ln, src in [(10, 'PUT SPRITE 0, (0, 0), 0, 0'),
                    (20, 'SET SPRITE 0, "FF"'), (30, 'END')]:
        interp.store_line(ln, src)
    interp.prepare_run()
    interp.step()
    check("PUT SPRITE yields frame", interp.yield_frame, True)
    interp.yield_frame = False
    interp.step()
    check("SET SPRITE does not yield", interp.yield_frame, False)


def test_sprite_table():
    t = SpriteTable()
    check("table empty snapshot", t.snapshot(), [])
    t.put(2, 10, 20, 5, 1, 7)
    t.put(0, 1, 2, 3, 0, -1)
    snap = t.snapshot()
    # snapshot() is ascending by id; the renderer draws it reversed so the
    # lowest id (0) lands frontmost.
    check("table snapshot ascending by id", [e[0] for e in snap], [0, 2])
    check("table entry fields", snap[1], (2, 10, 20, 5, 1, 7))
    t.off(0)
    check("table off disables", [e[0] for e in t.snapshot()], [2])
    t.clear()
    check("table clear empties", t.snapshot(), [])


def test_sprite_geometry():
    # 8x8 sheet order: 0,1 / 2,3 within a block, blocks row-major (0,1,4,5..).
    check("8x8 #0..4", [sprite8_pixel(n) for n in range(5)],
          [(0, 0), (8, 0), (0, 8), (8, 8), (16, 0)])
    check("8x8 #1023", sprite8_pixel(1023), (248, 248))
    check("16x16 #0/1/16/255",
          [sprite16_pixel(m) for m in (0, 1, 16, 255)],
          [(0, 0), (16, 0), (0, 16), (240, 240)])
    # A 16x16 sprite m aligns with its top-left 8x8 pattern m*4.
    check("16x16 aligns 8x8*4", sprite16_pixel(5), sprite8_pixel(20))


def test_play_channels():
    io, _ = run_program([
        (10, 'PLAY "a", "b"'),
        (20, 'PLAY "", "b"'),
        (30, 'PLAY , "b"'),
        (40, 'PLAY LOOP "a"'),
    ])
    check("play positional", io.play_calls[0], ("channels", ["a", "b"], False))
    check("play empty-string slot", io.play_calls[1], ("channels", ["", "b"], False))
    check("play omitted slot", io.play_calls[2], ("channels", [None, "b"], False))
    check("play loop flag", io.play_calls[3], ("channels", ["a"], True))


def test_play_ch():
    io, _ = run_program([
        (10, 'PLAY CH 2, "x"'),
        (20, 'PLAY LOOP CH 1, "y"'),
    ])
    check("play ch", io.play_calls[0], ("ch", 2, "x", False))
    check("play loop ch", io.play_calls[1], ("ch", 1, "y", True))


def test_play_stop():
    io, _ = run_program([
        (10, 'PLAY STOP'),
        (20, 'PLAY STOP 1'),
        (30, 'PLAY STOP 0, 1'),
    ])
    check("play stop all", io.play_calls[0], ("stop", []))
    check("play stop one", io.play_calls[1], ("stop", [1]))
    check("play stop many", io.play_calls[2], ("stop", [0, 1]))


def test_play_function():
    io, _ = run_program([
        (10, 'PLAY CH 0, "a"'),
        (20, 'PRINT PLAY(0); PLAY(3)'),
        (30, 'PLAY STOP 0'),
        (40, 'PRINT PLAY(0)'),
    ])
    check("play() reports playing", io.out[0], "10")
    check("play() reports stopped", io.out[1], "0")


def test_play_invalid_mml():
    io = MockIO()
    io.invalid_mmls = {"zzz"}
    io2, _ = run_program([(10, 'PLAY "zzz"')], io=io)
    code = next((int(s.split()[1]) for s in io2.out if s.startswith("?ERROR ")), None)
    check("invalid mml raises 409", code, int(Err.INVALID_MML))


def test_play_errors():
    check("play ch oob", _err_code([(10, 'PLAY CH 4, "x"')]),
          int(Err.PLAY_CHANNEL_OUT_OF_RANGE))
    check("play stop ch oob", _err_code([(10, 'PLAY STOP 5')]),
          int(Err.PLAY_CHANNEL_OUT_OF_RANGE))
    check("play() ch oob", _err_code([(10, 'PRINT PLAY(9)')]),
          int(Err.PLAY_CHANNEL_OUT_OF_RANGE))
    check("play ch no mml", _err_code([(10, 'PLAY CH 0')]),
          int(Err.INVALID_PLAY_SYNTAX))
    check("play too many slots", _err_code([(10, 'PLAY "a","b","c","d","e"')]),
          int(Err.INVALID_PLAY_SYNTAX))


def test_exception_safety_net():
    # An unexpected Python-level error (e.g. a non-numeric where a number is
    # required) must be reported as a BASIC error, not crash the interpreter.
    # This covers the new sprite/sound statements and pre-existing ones alike.
    cases = [
        'SET SPRITE "ffffffff"',     # number omitted -> int("ffffffff")
        'PUT SPRITE "x", (0,0), 0, 0',
        'PLAY CH "x", "m"',
        'PLAY STOP "x"',
        'LOCATE "a", 1',
    ]
    for src in cases:
        io, interp = run_program([(10, src)])
        check("safety net reports: " + src,
              any(s.startswith("?ERROR") for s in io.out), True)
        check("safety net drops to edit: " + src, interp.state, "EDIT")


def test_audio_resume_gating():
    # PyxelBasicAudio decides the resume flag from a per-channel "active" flag so
    # a one-shot after PLAY STOP does not resurrect the stopped sound, while a
    # one-shot over a still-playing sound does resume it. Drive it with a fake
    # pyxel and assert the (ch, loop, resume) values reaching pyxel.play.
    import pyxelbasic.audio as audiomod

    class _FakeSound:
        def mml(self, s):
            pass

    class _FakePyxel:
        def __init__(self):
            self.calls = []

        def Sound(self):
            return _FakeSound()

        def play(self, ch, snd, loop, resume):
            self.calls.append((ch, loop, resume))

        def stop(self, ch):
            self.calls.append(("stop", ch))

        def play_pos(self, ch):
            return None

    fake = _FakePyxel()
    orig = audiomod.pyxel
    audiomod.pyxel = fake
    try:
        a = audiomod.PyxelBasicAudio()
        a.play_ch(0, "C")                       # fresh channel -> resume False
        a.play_ch(0, "D")                       # over active   -> resume True
        a.play_stop([0])                        # stop          -> active cleared
        a.play_ch(0, "E")                       # after stop    -> resume False
        a.play_channels(["", "B"], loop=True)   # ch1 loop      -> resume False
        a.play_ch(1, "C")                       # ch1 active    -> resume True
    finally:
        audiomod.pyxel = orig
    check("audio resume gating", fake.calls, [
        (0, False, False),
        (0, False, True),
        ("stop", 0),
        (0, False, False),
        (1, True, False),
        (1, False, True),
    ])


def test_dispatch_registration():
    # STATEMENTS / FUNCTIONS are derived in keywords.py from the handler maps
    # (STATEMENT_HANDLERS / FUNCTION_HANDLERS / MATH1). Pin their contents so a
    # missing or stray keyword is caught. Expected values mirror the original
    # hand-written sets.
    expected_statements = {
        "PRINT", "INPUT", "LET", "GOTO", "GOSUB", "RETURN", "IF",
        "FOR", "NEXT", "DIM", "REM", "CLS", "LOCATE", "COLOR",
        "PSET", "LINE", "LINEB", "LINEBF", "CIRCLE", "CIRCLEBF",
        "END", "STOP", "DATA", "READ", "RESTORE",
        "RANDOMIZE", "VSYNC", "SET", "PUT", "PLAY",
    }
    expected_functions = {
        "LEN", "LEFT$", "RIGHT$", "MID$", "CHR$", "ASC", "STR$", "HEX$", "VAL",
        "ABS", "SGN", "INT", "FIX", "ROUND",
        "SIN", "COS", "TAN", "ATN", "RAD", "DEG",
        "EXP", "LOG", "LOG10", "SQR",
        "RND", "INKEY$", "STICK", "BUTTON", "POINT", "PLAY",
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
        test_string_funcs, test_hex, test_hex_literal_error,
        test_hex_renum_roundtrip, test_arg_count_error,
        test_array, test_array_2d, test_gosub, test_data_read,
        test_data_signed_values, test_data_unquoted_is_error,
        test_read_into_array,
        test_restore_line, test_restore_line_not_data,
        test_input, test_logical, test_graphics,
        test_cls_args, test_cls_mask_range, test_list_range, test_lineb,
        test_circle_full, test_circle_ratio, test_circle_arc, test_point,
        test_set_sprite, test_set_sprite_errors,
        test_put_sprite, test_put_sprite_off, test_put_sprite_errors,
        test_sprite_framebreak, test_sprite_table, test_sprite_geometry,
        test_play_channels, test_play_ch, test_play_stop, test_play_function,
        test_play_invalid_mml, test_play_errors, test_audio_resume_gating,
        test_exception_safety_net,
        test_command_queue_pget,
        test_vsync_noop, test_vsync_threaded_no_framebreak,
        test_vsync_main_mode_control, test_vsync_main_mode_yield_on_eval,
        test_session_run_frame_yields, test_break_stops_sound,
        test_direct_graphics_immediate,
        test_mod_fraction,
        test_renum, test_renum_keeps_rem,
        test_store_uppercases_code,
        test_runtime_input_state, test_runtime_command_queue_order,
        test_runtime_command_queue_backpressure,
        test_input_ring, test_key_state_stick_button,
        test_key_state_inkey_typeahead,
        test_textscreen_print_wrap, test_textscreen_scroll_length_invariant,
        test_textscreen_logical_text, test_textscreen_snapshot,
        test_editor_type_delete, test_editor_overtype, test_editor_reflow_wrap,
        test_dispatch_registration, test_alltest_sample,
    ]:
        print(fn.__name__)
        fn()
    print("\nResult: %d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
