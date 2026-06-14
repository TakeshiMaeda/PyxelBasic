# -*- coding: utf-8 -*-
"""PyxelBasic application body.

Switches between edit mode, run mode and input-wait mode while driving the
interpreter from Pyxel's main loop (update/draw).
"""

import os
import time

import pyxel

from .version import __version__
from .console import Console, CHAR_W, CHAR_H
from .errors import BasicError, Err
from .interpreter import Interpreter, tokenize, basic_str

# Number of statements to run per frame (higher is faster but less responsive)
STEPS_PER_FRAME = 800

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


class App:
    def __init__(self, width=256, height=256, autoload=None,
                 workdir=None, autorun=False, show_fps=False):
        # Directory used by SAVE / LOAD. Fixed at startup; there is no command to
        # change it from inside the interpreter. Defaults to the bundled samples.
        self.workdir = os.path.abspath(workdir) if workdir else SAMPLE_DIR

        # Disable Pyxel's built-in ESC-to-quit; we confirm with a dialog instead.
        pyxel.init(width, height, title="PyxelBasic", fps=60, quit_key=pyxel.KEY_NONE)
        cols = width // CHAR_W
        rows = height // CHAR_H
        self.console = Console(cols, rows)
        self.interp = Interpreter(self.console)

        self.mode = "EDIT"          # EDIT / RUN / INPUT
        self.input_origin = 0       # cursor offset where INPUT typing starts
        self.confirm_quit = False   # ESC shows a quit confirmation dialog
        # FPS in the title bar (enabled with --showfps): measure the real frame rate.
        self.show_fps = show_fps
        self._fps_n = 0
        self._fps_t = time.perf_counter()

        self._banner()
        loaded = self._load_file(autoload) if autoload else False
        if autorun and loaded:
            self.interp.prepare_run()
            self.mode = "RUN"

        pyxel.run(self.update, self.draw)

    # --- Display helpers ---
    def _banner(self):
        self.console.print_line("PyxelBasic prototype v%s" % __version__)
        self.console.print_line("(c) 2025-2026 Takeshi Maeda (SPSoft)")
        self.console.print_line("")

    # --- Main loop ---
    def update(self):
        if self.show_fps:
            self._update_fps()
        # Keep the most recent typed character for INKEY$
        self.console.key_char = pyxel.input_text if hasattr(pyxel, "input_text") else ""

        # ESC opens a quit-confirmation dialog; while it is up, only Y/N/ESC act.
        if self.confirm_quit:
            if pyxel.btnp(pyxel.KEY_Y):
                pyxel.quit()
            elif pyxel.btnp(pyxel.KEY_N) or pyxel.btnp(pyxel.KEY_ESCAPE):
                self.confirm_quit = False
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.confirm_quit = True
            return

        if self.mode == "RUN":
            self._update_run()
        else:
            self._update_edit()

    def _update_fps(self):
        # Count frames and refresh the title bar with the real frame rate ~2x/sec.
        self._fps_n += 1
        now = time.perf_counter()
        dt = now - self._fps_t
        if dt >= 0.5:
            pyxel.title("PyxelBasic  %.1f FPS" % (self._fps_n / dt))
            self._fps_n = 0
            self._fps_t = now

    def _break_pressed(self):
        # Ctrl+C interrupts a running program (classic BASIC break).
        return pyxel.btn(pyxel.KEY_CTRL) and pyxel.btnp(pyxel.KEY_C)

    def _break_run(self):
        self.console.print_line("")
        self.console.print_line("BREAK in line %d" % self.interp.cur_line)
        self.interp.state = "EDIT"
        self.mode = "EDIT"

    def _update_run(self):
        if self._break_pressed():
            self._break_run()
            return
        for _ in range(STEPS_PER_FRAME):
            self.interp.step()
            st = self.interp.state
            if st == "INPUT":
                self.mode = "INPUT"
                # Remember where typed input begins so the prompt is excluded.
                self.input_origin = self.console.caret_index()
                return
            if st in ("END", "EDIT"):
                if st == "END":
                    self.console.print_line("")
                    self.console.print_line("OK")
                self.mode = "EDIT"
                return
            # VSYNC: stop running this frame and continue on the next one
            if self.interp.yield_frame:
                self.interp.yield_frame = False
                return

    # --- Full-screen editor (EDIT / INPUT) ---
    def _update_edit(self):
        # Ctrl+C while waiting for INPUT also breaks back to edit mode.
        if self.mode == "INPUT" and self._break_pressed():
            self._break_run()
            return
        c = self.console
        for ch in (pyxel.input_text if hasattr(pyxel, "input_text") else ""):
            if 32 <= ord(ch) < 127:
                c.type_char(ch)
        if pyxel.btnp(pyxel.KEY_LEFT, 20, 2):
            c.move_left()
        if pyxel.btnp(pyxel.KEY_RIGHT, 20, 2):
            c.move_right()
        if pyxel.btnp(pyxel.KEY_UP, 20, 2):
            c.move_up()
        if pyxel.btnp(pyxel.KEY_DOWN, 20, 2):
            c.move_down()
        if pyxel.btnp(pyxel.KEY_HOME):
            c.home()
        if pyxel.btnp(pyxel.KEY_END):
            c.end()
        if pyxel.btnp(pyxel.KEY_INSERT):
            c.toggle_insert()
        if pyxel.btnp(pyxel.KEY_DELETE, 20, 2):
            c.delete_at()
        if pyxel.btnp(pyxel.KEY_BACKSPACE, 20, 2):
            c.backspace()
        if pyxel.btnp(pyxel.KEY_RETURN):
            self._enter()

    def _enter(self):
        c = self.console
        text = c.get_logical_text()[0]
        if self.mode == "INPUT":
            value = text[self.input_origin:] if self.input_origin <= len(text) else ""
            c.cursor_to_next_logical()
            self.interp.provide_input(value)
            self.mode = "RUN"
        else:
            c.cursor_to_next_logical()
            self._submit_line(text)

    # --- Line submission (edit mode) ---
    def _submit_line(self, text):
        s = text.strip()
        if s == "":
            return
        # A leading digit means a numbered program line
        if s[0].isdigit():
            num, rest = self._split_lineno(s)
            self.interp.store_line(num, rest)
            return
        # Otherwise treat it as a direct command (output flows from the cursor)
        try:
            self._direct_command(s)
        except BasicError as e:
            self.console.print_line("?ERROR %d: %s" % (int(e.code), e))

    def _split_lineno(self, s):
        i = 0
        while i < len(s) and s[i].isdigit():
            i += 1
        num = int(s[:i])
        rest = s[i:].lstrip()
        return num, rest

    def _direct_command(self, s):
        toks = tokenize(s)
        if not toks:
            return
        kind, val = toks[0]
        if (kind, val) == ("KW", "RUN"):
            self.interp.prepare_run()
            self.mode = "RUN"
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
            # Execute PRINT, assignments, etc. on the spot (direct execution)
            self.interp.state = "RUN"
            self.interp.jumped = False
            self.interp.execute(toks)
            self.interp.state = "EDIT"

    def _cmd_list(self, toks):
        start = end = None
        nums = [v for (k, v) in toks[1:] if k == "NUM"]
        if len(nums) == 1:
            start = end = int(nums[0])
        elif len(nums) >= 2:
            start, end = int(nums[0]), int(nums[1])
        for ln, src in self.interp.list_lines(start, end):
            self.console.print_line("%d %s" % (ln, src))

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
        self.console.print_line('SAVED "%s"' % name)

    def _cmd_load(self, toks):
        name = next((v for (k, v) in toks if k == "STR"), None)
        if not name:
            raise BasicError(Err.LOAD_REQUIRES_NAME)
        self._load_file(name)

    def _load_file(self, name):
        path = self._resolve_path(name)
        if not os.path.exists(path):
            self.console.print_line('?FILE NOT FOUND "%s"' % name)
            return False
        self.interp.new_program()
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                s = line.strip()
                if s and s[0].isdigit():
                    num, rest = self._split_lineno(s)
                    self.interp.store_line(num, rest)
        self.console.print_line('LOADED "%s"' % name)
        return True

    def _resolve_path(self, name):
        if not name.lower().endswith(".bas"):
            name += ".bas"
        os.makedirs(self.workdir, exist_ok=True)
        return os.path.join(self.workdir, name)

    # --- Drawing ---
    def draw(self):
        self.console.draw()
        # The edited text lives in the console buffer itself; just blink a cursor
        # (shape reflects insert vs overtype mode).
        if (self.mode in ("EDIT", "INPUT") and not self.confirm_quit
                and pyxel.frame_count % 30 < 15):
            self.console.draw_cursor(True)
        if self.confirm_quit:
            self._draw_quit_dialog()

    def _draw_quit_dialog(self):
        w, h = 120, 27
        x = (pyxel.width - w) // 2
        y = (pyxel.height - h) // 2
        pyxel.rect(x, y, w, h, 1)
        pyxel.rectb(x, y, w, h, 7)
        msg1 = "Quit PyxelBasic?"
        msg2 = "Y = yes   N = no"
        pyxel.text(x + (w - len(msg1) * CHAR_W) // 2, y + 8, msg1, 7)
        pyxel.text(x + (w - len(msg2) * CHAR_W) // 2, y + 17, msg2, 7)
