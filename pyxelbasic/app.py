# -*- coding: utf-8 -*-
"""PyxelBasic application body.

Switches between edit mode, run mode and input-wait mode while driving the
interpreter from Pyxel's main loop (update/draw).
"""

import os

import pyxel

from .console import Console, CHAR_W, CHAR_H
from .interpreter import Interpreter, tokenize, basic_str, BasicError

# Number of statements to run per frame (higher is faster but less responsive)
STEPS_PER_FRAME = 800

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


class App:
    def __init__(self, width=256, height=256, autoload=None):
        pyxel.init(width, height, title="PyxelBasic", fps=60)
        cols = width // CHAR_W
        rows = height // CHAR_H
        self.console = Console(cols, rows)
        self.interp = Interpreter(self.console)

        self.mode = "EDIT"          # EDIT / RUN / INPUT
        self.input_buffer = ""

        self._banner()
        if autoload:
            self._load_file(autoload)
        self._prompt()

        pyxel.run(self.update, self.draw)

    # --- Display helpers ---
    def _banner(self):
        self.console.print_line("PyxelBasic prototype v0.1")
        self.console.print_line("(c) 2025-2026 Takeshi Maeda (SPSoft)")
        self.console.print_line("")

    def _prompt(self):
        self.console.print_text("]")
        self.input_buffer = ""

    # --- Main loop ---
    def update(self):
        # Keep the most recent typed character for INKEY$
        self.console.key_char = pyxel.input_text if hasattr(pyxel, "input_text") else ""

        if self.mode == "RUN":
            self._update_run()
        else:
            self._update_lineedit()

    def _update_run(self):
        for _ in range(STEPS_PER_FRAME):
            self.interp.step()
            st = self.interp.state
            if st == "INPUT":
                self.mode = "INPUT"
                self.input_buffer = ""
                return
            if st in ("END", "EDIT"):
                if st == "END":
                    self.console.print_line("")
                    self.console.print_line("OK")
                self.mode = "EDIT"
                self._prompt()
                return
            # VSYNC: stop running this frame and continue on the next one
            if self.interp.yield_frame:
                self.interp.yield_frame = False
                return

    def _update_lineedit(self):
        # Character input
        typed = pyxel.input_text if hasattr(pyxel, "input_text") else ""
        if typed:
            self.input_buffer += typed
        # Backspace
        if pyxel.btnp(pyxel.KEY_BACKSPACE, 20, 2) and self.input_buffer:
            self.input_buffer = self.input_buffer[:-1]
        # Confirm
        if pyxel.btnp(pyxel.KEY_RETURN):
            line = self.input_buffer
            if self.mode == "INPUT":
                self.console.print_line(line)
                self.interp.provide_input(line)
                self.mode = "RUN"
            else:
                self.console.print_line(line)
                self._submit_line(line)

    # --- Line submission (edit mode) ---
    def _submit_line(self, text):
        s = text.strip()
        if s == "":
            self._prompt()
            return
        # A leading digit means a numbered program line
        if s[0].isdigit():
            num, rest = self._split_lineno(s)
            self.interp.store_line(num, rest)
            self._prompt()
            return
        # Otherwise treat it as a direct command
        try:
            self._direct_command(s)
        except BasicError as e:
            self.console.print_line("?ERROR: %s" % e)
        # Show the prompt unless we switched into RUN
        if self.mode == "EDIT":
            self._prompt()

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
            raise BasicError("SAVE requires a file name")
        path = self._resolve_path(name)
        with open(path, "w", encoding="utf-8") as f:
            for ln, src in self.interp.list_lines():
                f.write("%d %s\n" % (ln, src))
        self.console.print_line('SAVED "%s"' % name)

    def _cmd_load(self, toks):
        name = next((v for (k, v) in toks if k == "STR"), None)
        if not name:
            raise BasicError("LOAD requires a file name")
        self._load_file(name)

    def _load_file(self, name):
        path = self._resolve_path(name)
        if not os.path.exists(path):
            self.console.print_line('?FILE NOT FOUND "%s"' % name)
            return
        self.interp.new_program()
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                s = line.strip()
                if s and s[0].isdigit():
                    num, rest = self._split_lineno(s)
                    self.interp.store_line(num, rest)
        self.console.print_line('LOADED "%s"' % name)

    def _resolve_path(self, name):
        if not name.lower().endswith(".bas"):
            name += ".bas"
        os.makedirs(SAMPLE_DIR, exist_ok=True)
        return os.path.join(SAMPLE_DIR, name)

    # --- Drawing ---
    def draw(self):
        self.console.draw()
        if self.mode in ("EDIT", "INPUT"):
            # Overlay the line being edited at the cursor position
            px = self.console.cx * CHAR_W
            py = self.console.cy * CHAR_H
            pyxel.text(px, py, self.input_buffer, 7)
            # Blinking cursor
            if pyxel.frame_count % 30 < 15:
                cpx = px + len(self.input_buffer) * CHAR_W
                pyxel.rect(cpx, py + CHAR_H - 1, CHAR_W - 1, 1, 7)
