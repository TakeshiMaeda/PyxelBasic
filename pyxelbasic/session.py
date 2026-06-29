# -*- coding: utf-8 -*-
"""BASIC session driver (platform-independent, runs on the VM thread).

Owns the interpreter, the text screen (virtual VRAM), the editor and the
derived key state. Runs the whole interactive session - edit mode, program RUN
and INPUT - on its own thread. The Pyxel main thread is only a terminal: it
feeds input events into a ring and renders the published text snapshot plus the
graphics surface (see app.py).

No Pyxel here. Output goes to the text screen directly (text) or to the
graphics command queue (graphics); input is read from the key state, which the
loop keeps fresh by draining the input ring every cycle.
"""

import os
import sys
import time

from .version import __version__
from .errors import BasicError, Err
from .interpreter import Interpreter, tokenize
from .textscreen import TextScreen
from .editor import Editor
from .runtime import KeyState, SpriteTable, EV_CHAR, EV_DOWN, EV_REPEAT
from .keywords import (
    KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_HOME, KEY_END,
    KEY_INSERT, KEY_DELETE, KEY_BACKSPACE, KEY_RETURN,
)

# Compensated throttle defaults: run STEPS statements per cycle, then pad the
# cycle to PERIOD seconds (frame-limiter style) so each cycle takes ~PERIOD.
# PERIOD is chosen as a multiple of the coarse Windows time.sleep() floor
# (~15.6ms) so the wait is actually honoured even on Python 3.10 (a ~64ms target
# lands near a timer-tick multiple -> ~16 cycles/s, so STEPS=400 gives roughly
# 6000-6400 statements/s). Calibrate by feel via --vm-cycle-steps /
# --vm-cycle-ms (raise STEPS to go faster; PERIOD only matters in steps of the
# sleep floor -- see --debug-throttle for the in-app verdict).
CYCLE_STEPS = 400
CYCLE_PERIOD = 0.064   # seconds; <= 0 disables the throttle (run free)

# Main-driven mode: statements executed per Pyxel frame (the classic cooperative
# pacing). Higher is faster but less responsive. Used only when exec_mode="main".
STEPS_PER_FRAME = 800

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")

# Editor key id -> Editor method name ("enter" is line submission).
EDITOR_KEY_ACTIONS = {
    KEY_LEFT: "move_left",
    KEY_RIGHT: "move_right",
    KEY_UP: "move_up",
    KEY_DOWN: "move_down",
    KEY_HOME: "home",
    KEY_END: "end",
    KEY_INSERT: "toggle_insert",
    KEY_DELETE: "delete_at",
    KEY_BACKSPACE: "backspace",
    KEY_RETURN: "enter",
}


def parse_list_range(toks):
    """Parse a LIST command's tokens into a (start, end) line range.

    Forms (start/end are None when open-ended):
      LIST          -> (None, None)   all lines
      LIST 100      -> (100, 100)     a single line
      LIST 100-200  -> (100, 200)
      LIST -100     -> (None, 100)    from the top through 100
      LIST 200-     -> (200, None)    from 200 to the end
    """
    rest = toks[1:]
    if not rest:
        return None, None
    dash_idx = None
    for i, t in enumerate(rest):
        if t == ("OP", "-"):
            dash_idx = i
            break
    if dash_idx is None:
        nums = [v for (k, v) in rest if k == "NUM"]
        if nums:
            return int(nums[0]), int(nums[0])
        return None, None
    before = [v for (k, v) in rest[:dash_idx] if k == "NUM"]
    after = [v for (k, v) in rest[dash_idx + 1:] if k == "NUM"]
    start = int(before[0]) if before else None
    end = int(after[0]) if after else None
    return start, end


class SessionIO:
    """IOTarget used by the interpreter while the session runs.

    Text output goes straight to the (VM-owned) text screen; graphics commands
    are enqueued for the main thread; input reads consult the key state.
    """

    def __init__(self, screen, gfx_queue, keys, sprite_table, audio=None):
        self.screen = screen
        self.gfx = gfx_queue
        self.keys = keys
        self.sprite_table = sprite_table
        self.audio = audio          # dedicated audio command sink (None in headless tests)

    # --- text (direct to the VM-owned screen) ---
    def cls(self, mask=3):
        # mask: bit 1 = text, bit 2 = graphics (3 = both, the default).
        if mask & 1:
            self.screen.cls()           # text grid (here)
        if mask & 2:
            self.gfx.put(("cls", ()))   # graphics surface (main thread)
            self.sprite_table.clear()   # sprite display table (CLS 2 clears it too)

    def set_color(self, col):
        self.screen.set_color(col)

    def locate(self, x, y):
        self.screen.locate(x, y)

    def print_text(self, text):
        self.screen.print_text(text)

    def print_line(self, text):
        self.screen.print_line(text)

    # --- graphics (enqueue; resolve the default colour on this side) ---
    def pset(self, x, y, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("pset", (x, y, c)))

    def line(self, x1, y1, x2, y2, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("line", (x1, y1, x2, y2, c)))

    def rect(self, x1, y1, x2, y2, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("rect", (x1, y1, x2, y2, c)))

    def rectb(self, x1, y1, x2, y2, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("rectb", (x1, y1, x2, y2, c)))

    def elli(self, x, y, rx, ry, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("elli", (x, y, rx, ry, c)))

    def ellib(self, x, y, rx, ry, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("ellib", (x, y, rx, ry, c)))

    def tri(self, x1, y1, x2, y2, x3, y3, col=None):
        c = self.screen.color if col is None else col
        self.gfx.put(("tri", (x1, y1, x2, y2, x3, y3, c)))

    def point(self, x, y):
        # Read back a pixel via the graphics target. The Pyxel image is only
        # touchable on the main thread, so in threaded mode this round-trips
        # through the command queue (serviced during drain); in main-driven mode
        # it reads the surface directly. Either way prior draws are applied first.
        return self.gfx.pget(x, y)

    # --- sprites ---
    def set_sprite(self, no, colors):
        # Pattern pixels live in a Pyxel texture, so write them through the same
        # graphics path as PSET (main thread applies them during drain).
        self.gfx.put(("set_sprite", (no, colors)))

    def put_sprite(self, sid, x, y, no, size, colkey):
        # Display table is plain data (no texture); update it directly. The
        # front end reads a snapshot of it each frame to compose the sprite plane.
        self.sprite_table.put(sid, x, y, no, size, colkey)

    def put_sprite_off(self, sid):
        self.sprite_table.off(sid)

    # --- sound (PLAY) ---
    # Play calls round-trip through the audio sink (validate + play on the main
    # thread) and return None, or the offending MML for the core to raise on.
    def play_channels(self, mmls, loop):
        if self.audio is None:
            return None
        return self.audio.call("play_channels", (mmls, loop))

    def play_ch(self, ch, mml, loop):
        if self.audio is None:
            return None
        return self.audio.call("play_ch", (ch, mml, loop))

    def play_stop(self, channels):
        if self.audio is not None:
            self.audio.put(("play_stop", (channels,)))

    def playing(self, ch):
        if self.audio is None:
            return 0
        return self.audio.call("playing", (ch,))

    # --- input (read the derived key state) ---
    def inkey(self):
        return self.keys.inkey()

    def stick(self, n):
        return self.keys.stick(n)

    def button(self, n):
        return self.keys.button(n)


class Session:
    def __init__(self, cols, rows, gfx_queue, input_ring, workdir=None,
                 autoload=None, autorun=False,
                 cycle_steps=CYCLE_STEPS, cycle_period=CYCLE_PERIOD,
                 debug_throttle=False, vsync_enabled=False, sprite_table=None,
                 audio=None):
        self.workdir = os.path.abspath(workdir) if workdir else SAMPLE_DIR
        self.screen = TextScreen(cols, rows)
        self.editor = Editor(self.screen)
        self.keys = KeyState()
        self.gfx_queue = gfx_queue
        self.input_ring = input_ring
        # Sprite display table (shared with the front end, which reads a snapshot
        # of it each frame). Created here when not supplied, so headless tests
        # that build a Session without a front end still work.
        self.sprite_table = sprite_table if sprite_table is not None else SpriteTable()
        self.io = SessionIO(self.screen, gfx_queue, self.keys, self.sprite_table,
                            audio=audio)
        # vsync_enabled is True only in the main-driven execution mode, where the
        # interpreter honours frame-break/VSYNC; the threaded mode leaves it off.
        self.interp = Interpreter(self.io, vsync_enabled=vsync_enabled)

        self.mode = "EDIT"          # EDIT / RUN / INPUT
        self.input_origin = 0
        self.steps_per_cycle = cycle_steps
        self.period = cycle_period
        self.debug_throttle = debug_throttle
        self._stop = False
        self._break = False

        self._banner()
        loaded = self._load_file(autoload) if autoload else False
        if autorun and loaded:
            try:
                self._start_run()
            except BasicError as e:
                self.screen.print_line("?ERROR %d: %s" % (int(e.code), e))
        self.screen.publish()

    # --- main loop (runs on the VM thread) ---
    def run(self):
        if self.debug_throttle:
            self._debug_throttle_report()
        while not self._stop:
            t0 = time.perf_counter()
            self._poll_input()
            if self.mode == "RUN":
                self._run_cycle()
            self.screen.publish()
            if self.period > 0:
                dt = time.perf_counter() - t0
                if dt < self.period:
                    time.sleep(self.period - dt)

    def request_break(self):
        self._break = True

    def request_stop(self):
        self._stop = True

    def _debug_throttle_report(self):
        """Measure the real time.sleep() floor and the effective throttle rate
        inside the running app (the timer resolution can differ from a bare
        Python process while Pyxel holds the window open). Prints to stderr."""
        def probe(req, n=80):
            best = 1e9
            tot = 0.0
            for _ in range(n):
                t0 = time.perf_counter()
                time.sleep(req)
                dt = time.perf_counter() - t0
                tot += dt
                best = min(best, dt)
            return best, tot / n

        out = ["[debug-throttle] measured inside the running app:"]
        floor = None
        for r in (0.001, 0.004, 0.008):
            b, a = probe(r)
            out.append("  sleep(%4.0fms): min=%6.3fms avg=%6.3fms"
                       % (r * 1000, b * 1000, a * 1000))
            if floor is None:
                floor = a   # avg of a sub-floor request ~= the sleep floor F
        # Actual cycle of the configured throttle (trivial per-step work, so
        # this is dominated by the sleep floor - the real ceiling).
        end = time.perf_counter() + 0.3
        cycles = 0
        while time.perf_counter() < end:
            c0 = time.perf_counter()
            x = 0
            for _ in range(self.steps_per_cycle):
                x += 1
            dt = time.perf_counter() - c0
            if self.period > 0 and dt < self.period:
                time.sleep(self.period - dt)
            cycles += 1
        rate = cycles / 0.3
        actual_ms = (1000.0 / rate) if rate > 0 else 0.0
        req_ms = self.period * 1000.0
        floor_ms = floor * 1000.0
        out.append("  sleep floor F ~= %.2fms" % floor_ms)
        out.append("  config: --vm-cycle-steps %d --vm-cycle-ms %.1f"
                   % (self.steps_per_cycle, req_ms))
        # Verdict on whether the requested --vm-cycle-ms is actually honoured.
        if self.period <= 0:
            out.append("  verdict: --vm-cycle-ms 0 -> no sleep (runs free, CPU-bound)")
        elif actual_ms > req_ms * 1.5:
            out.append("  verdict: requested %.1fms is near/below the sleep floor "
                       "(F~%.1fms) -> NOT honoured;" % (req_ms, floor_ms))
            out.append("           actual cycle is ~%.1fms. Lowering --vm-cycle-ms "
                       "further won't speed up." % actual_ms)
            out.append("           Use --vm-cycle-steps for speed; raise "
                       "--vm-cycle-ms above ~%.0fms to actually slow down."
                       % floor_ms)
        else:
            out.append("  verdict: --vm-cycle-ms %.1f honoured (actual cycle ~%.1fms)."
                       % (req_ms, actual_ms))
        out.append("  effective: ~%.0f cycles/s, ~%.0f statements/s ceiling"
                   % (rate, rate * self.steps_per_cycle))
        sys.stderr.write("\n".join(out) + "\n")
        sys.stderr.flush()

    # --- main-driven mode (driven one frame at a time by the Pyxel main loop) ---
    def poll_input(self):
        """Public entry: pump input once (used by the main-driven driver)."""
        self._poll_input()

    def run_frame(self, max_steps):
        """Run up to max_steps statements for one Pyxel frame (main-driven mode).

        Like _run_cycle but honours the interpreter's yield_frame flag, so a
        VSYNC / frame-break statement or function ends the frame early and the
        Pyxel main loop continues it on the next frame.
        """
        for _ in range(max_steps):
            if self._break:
                self._break = False
                self._do_break()
                return
            if self.interp.state != "RUN":
                break
            self.interp.step()
            st = self.interp.state
            if st == "INPUT":
                self.mode = "INPUT"
                self.input_origin = self.screen.caret_index()
                return
            if st in ("END", "EDIT"):
                self._finish_run(st)
                return
            # Frame-break / VSYNC: stop running this frame, resume next frame.
            if self.interp.yield_frame:
                self.interp.yield_frame = False
                return

    # --- input dispatch ---
    def _poll_input(self):
        events = self.input_ring.drain()
        if not events:
            return
        self.keys.apply_all(events)         # always keep STICK/BUTTON/INKEY$ fresh
        if self.mode in ("EDIT", "INPUT"):
            for kind, value in events:
                self._dispatch_edit_event(kind, value)

    def _dispatch_edit_event(self, kind, value):
        if kind == EV_CHAR:
            if len(value) == 1 and 32 <= ord(value) < 127:
                self.editor.type_char(value)
        elif kind in (EV_DOWN, EV_REPEAT):
            action = EDITOR_KEY_ACTIONS.get(value)
            if action == "enter":
                self._enter()
            elif action is not None:
                getattr(self.editor, action)()

    # --- RUN cycle ---
    def _run_cycle(self):
        for _ in range(self.steps_per_cycle):
            if self._break:
                self._break = False
                self._do_break()
                return
            if self.interp.state != "RUN":
                break
            self.interp.step()
            st = self.interp.state
            if st == "INPUT":
                self.mode = "INPUT"
                self.input_origin = self.screen.caret_index()
                return
            if st in ("END", "EDIT"):
                self._finish_run(st)
                return

    def _start_run(self):
        self.interp.prepare_run()       # may raise BasicError
        self._break = False
        self.mode = "RUN"

    def _finish_run(self, st):
        if st == "END":
            self.screen.print_line("")
            self.screen.print_line("OK")
        self.mode = "EDIT"

    def _do_break(self):
        # Ctrl+C aborts the run and also silences every sound channel (an empty
        # channel list means all), so a looping BGM does not keep playing.
        self.io.play_stop([])
        self.screen.print_line("")
        self.screen.print_line("BREAK in line %d" % self.interp.cur_line)
        self.interp.state = "EDIT"
        self.mode = "EDIT"

    # --- line submission / direct commands ---
    def _enter(self):
        text = self.screen.get_logical_text()[0]
        if self.mode == "INPUT":
            value = text[self.input_origin:] if self.input_origin <= len(text) else ""
            self.screen.cursor_to_next_logical()
            self.interp.provide_input(value)
            self.mode = "RUN"
        else:
            self.screen.cursor_to_next_logical()
            self._submit_line(text)

    def _submit_line(self, text):
        s = text.strip()
        if s == "":
            return
        if s[0].isdigit():
            num, rest = self._split_lineno(s)
            self.interp.store_line(num, rest)
            return
        try:
            self._direct_command(s)
        except BasicError as e:
            self.screen.print_line("?ERROR %d: %s" % (int(e.code), e))
        except Exception as e:
            # Safety net for direct commands too: report instead of crashing.
            self.interp.state = "EDIT"
            self.screen.print_line("?ERROR: %s" % (e,))

    def _split_lineno(self, s):
        i = 0
        while i < len(s) and s[i].isdigit():
            i += 1
        return int(s[:i]), s[i:].lstrip()

    def _direct_command(self, s):
        toks = tokenize(s)
        if not toks:
            return
        kind, val = toks[0]
        if (kind, val) == ("KW", "RUN"):
            self._start_run()
        elif (kind, val) == ("KW", "LIST"):
            self._cmd_list(toks)
        elif (kind, val) == ("KW", "NEW"):
            self.interp.new_program()
        elif (kind, val) == ("KW", "RENUM"):
            self._cmd_renum(toks)
        elif (kind, val) == ("KW", "SAVE"):
            self._cmd_save(toks)
        elif (kind, val) == ("KW", "LOAD"):
            self._cmd_load(toks)
        else:
            # Direct execution (PRINT, assignments, ':'-separated statements).
            self.interp.state = "RUN"
            self.interp.jumped = False
            self.interp._run_stmt_seq(toks)
            self.interp.state = "EDIT"

    def _cmd_list(self, toks):
        start, end = parse_list_range(toks)
        for ln, src in self.interp.list_lines(start, end):
            self.screen.print_line("%d %s" % (ln, src))

    def _cmd_renum(self, toks):
        nums = [v for (k, v) in toks[1:] if k == "NUM"]
        start = int(nums[0]) if len(nums) >= 1 else 10
        step = int(nums[1]) if len(nums) >= 2 else 10
        self.interp.renum(start, step)

    def _cmd_save(self, toks):
        name = next((v for (k, v) in toks if k == "STR"), None)
        if not name:
            raise BasicError(Err.SAVE_REQUIRES_NAME)
        path = self._resolve_path(name)
        with open(path, "w", encoding="utf-8") as f:
            for ln, src in self.interp.list_lines():
                f.write("%d %s\n" % (ln, src))
        self.screen.print_line('SAVED "%s"' % name)

    def _cmd_load(self, toks):
        name = next((v for (k, v) in toks if k == "STR"), None)
        if not name:
            raise BasicError(Err.LOAD_REQUIRES_NAME)
        self._load_file(name)

    def _load_file(self, name):
        path = self._resolve_path(name)
        if not os.path.exists(path):
            self.screen.print_line('?FILE NOT FOUND "%s"' % name)
            return False
        self.interp.new_program()
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                s = raw.rstrip("\n").strip()
                if s and s[0].isdigit():
                    num, rest = self._split_lineno(s)
                    self.interp.store_line(num, rest)
        self.screen.print_line('LOADED "%s"' % name)
        return True

    def _resolve_path(self, name):
        if not name.lower().endswith(".bas"):
            name += ".bas"
        os.makedirs(self.workdir, exist_ok=True)
        return os.path.join(self.workdir, name)

    # --- display ---
    def _banner(self):
        self.screen.print_line("PyxelBasic v%s" % __version__)
        self.screen.print_line("(c) 2025-2026 Takeshi Maeda (SPSoft)")
        self.screen.print_line("")
