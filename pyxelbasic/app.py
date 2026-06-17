# -*- coding: utf-8 -*-
"""PyxelBasic terminal front end (Pyxel main thread).

A thin terminal: it captures Pyxel input into an event ring, drains the graphics
command queue onto the graphics surface, and renders the text snapshot the
session publishes. All BASIC work (edit, run, input, meta-commands) happens on
the Session thread (session.py); this file holds the only Pyxel input/render
calls and the Pyxel key -> abstract key id mapping.
"""

import os
import threading
import time

import pyxel

from .console import PyxelRenderer, PyxelGraphicsSurface, CHAR_W, CHAR_H
from .runtime import (
    InputRing, CommandQueue, GFX_QUEUE_CAPACITY,
    EV_CHAR, EV_DOWN, EV_UP, EV_REPEAT,
)
from .session import Session, CYCLE_STEPS, CYCLE_PERIOD
from .keywords import (
    KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_HOME, KEY_END,
    KEY_INSERT, KEY_DELETE, KEY_BACKSPACE, KEY_RETURN,
    KEY_BTN0, KEY_BTN1, KEY_BTN2, KEY_BTN3,
)

# Editor auto-repeat timing for held keys (frames before / between repeats).
REPEAT_HOLD = 20
REPEAT_PERIOD = 2


class App:
    def __init__(self, width=256, height=256, autoload=None, workdir=None,
                 autorun=False, show_fps=False, gfx_queue_size=None,
                 cycle_steps=None, cycle_period=None, debug_throttle=False):
        # Disable Pyxel's built-in ESC-to-quit; we confirm with a dialog instead.
        pyxel.init(width, height, title="PyxelBasic", fps=60,
                   quit_key=pyxel.KEY_NONE)
        cols = width // CHAR_W
        rows = height // CHAR_H

        # Cross-thread channels: input events (main -> session), graphics
        # commands (session -> main).
        self.input_ring = InputRing()
        gcap = gfx_queue_size if gfx_queue_size is not None else GFX_QUEUE_CAPACITY
        self.gfx_queue = CommandQueue(gcap)
        self.gfx_surface = PyxelGraphicsSurface(cols * CHAR_W, rows * CHAR_H)
        self.renderer = PyxelRenderer(cols, rows, self.gfx_surface)

        self.session = Session(
            cols, rows, self.gfx_queue, self.input_ring,
            workdir=workdir, autoload=autoload, autorun=autorun,
            cycle_steps=cycle_steps if cycle_steps is not None else CYCLE_STEPS,
            cycle_period=cycle_period if cycle_period is not None else CYCLE_PERIOD,
            debug_throttle=debug_throttle)

        self.confirm_quit = False
        self.show_fps = show_fps
        self._fps_n = 0
        self._fps_t = time.perf_counter()

        # Pyxel key -> (abstract key id, auto-repeat). Built here (Pyxel only).
        self.key_events = [
            (pyxel.KEY_LEFT, KEY_LEFT, True),
            (pyxel.KEY_RIGHT, KEY_RIGHT, True),
            (pyxel.KEY_UP, KEY_UP, True),
            (pyxel.KEY_DOWN, KEY_DOWN, True),
            (pyxel.KEY_HOME, KEY_HOME, False),
            (pyxel.KEY_END, KEY_END, False),
            (pyxel.KEY_INSERT, KEY_INSERT, False),
            (pyxel.KEY_DELETE, KEY_DELETE, True),
            (pyxel.KEY_BACKSPACE, KEY_BACKSPACE, True),
            (pyxel.KEY_RETURN, KEY_RETURN, False),
            (pyxel.KEY_Z, KEY_BTN0, False),
            (pyxel.KEY_X, KEY_BTN1, False),
            (pyxel.KEY_C, KEY_BTN2, False),
            (pyxel.KEY_SPACE, KEY_BTN3, False),
        ]

        self.session_thread = threading.Thread(target=self.session.run,
                                                daemon=True)
        self.session_thread.start()

    def run(self):
        """Enter the Pyxel main loop (blocks until the window closes)."""
        pyxel.run(self.update, self.draw)
        # Window closed: stop the session and release any blocked put().
        self.session.request_stop()
        self.gfx_queue.stop()

    # --- Main loop ---
    def update(self):
        if self.show_fps:
            self._update_fps()
        # Apply queued graphics every frame (also frees a back-pressured VM).
        self.gfx_queue.drain(self.gfx_surface)

        if self.confirm_quit:
            if pyxel.btnp(pyxel.KEY_Y):
                pyxel.quit()
            elif pyxel.btnp(pyxel.KEY_N) or pyxel.btnp(pyxel.KEY_ESCAPE):
                self.confirm_quit = False
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.confirm_quit = True
            return
        # Ctrl+C breaks a running program (handled out of band by the session).
        if pyxel.btn(pyxel.KEY_CTRL) and pyxel.btnp(pyxel.KEY_C):
            self.session.request_break()

        self._capture_input()

    def _capture_input(self):
        # Typed text -> char events.
        text = pyxel.input_text if hasattr(pyxel, "input_text") else ""
        for ch in text:
            self.input_ring.push((EV_CHAR, ch))
        # Key edges -> down/up; held auto-repeat keys also emit repeat ticks.
        for pkey, kid, repeat in self.key_events:
            if pyxel.btnp(pkey):
                self.input_ring.push((EV_DOWN, kid))
            elif repeat and pyxel.btnp(pkey, REPEAT_HOLD, REPEAT_PERIOD):
                self.input_ring.push((EV_REPEAT, kid))
            if pyxel.btnr(pkey):
                self.input_ring.push((EV_UP, kid))

    def _update_fps(self):
        self._fps_n += 1
        now = time.perf_counter()
        dt = now - self._fps_t
        if dt >= 0.5:
            pyxel.title("PyxelBasic  %.1f FPS" % (self._fps_n / dt))
            self._fps_n = 0
            self._fps_t = now

    # --- Drawing ---
    def draw(self):
        snap = self.session.screen.get_published()
        cursor_visible = (self.session.mode in ("EDIT", "INPUT")
                          and not self.confirm_quit
                          and pyxel.frame_count % 30 < 15)
        self.renderer.render(snap, cursor_visible)
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
