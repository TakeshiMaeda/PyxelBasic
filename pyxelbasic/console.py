# -*- coding: utf-8 -*-
"""Text console and graphics surface on top of Pyxel.

Referenced by the interpreter as an IOTarget.
Characters are kept in a grid buffer and drawn every frame.
Graphics commands (PSET/LINE) are baked into a dedicated image and
overlaid beneath the text.
"""

import pyxel

CHAR_W = 4   # width of one character in Pyxel's built-in font
CHAR_H = 6   # height of one line


class Console:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.color = 7              # default text color (white)
        self.bg = 0                 # background color
        # Graphics are baked once into a dedicated Image and just blt'd every
        # frame. (Replaying stored draw commands every frame would get slower
        # as the number of points grows.)
        self.gimg = pyxel.Image(cols * CHAR_W, rows * CHAR_H)
        self.gimg.cls(self.bg)
        self._clear_buffer()
        # Key input (for INKEY$): the character typed in the most recent frame.
        self.key_char = ""

    def _clear_buffer(self):
        self.chars = [[" "] * self.cols for _ in range(self.rows)]
        self.cols_color = [[self.color] * self.cols for _ in range(self.rows)]
        self.cx = 0
        self.cy = 0

    # --- IOTarget interface ---
    def cls(self):
        self._clear_buffer()
        self.gimg.cls(self.bg)

    def set_color(self, col):
        self.color = col

    def locate(self, x, y):
        self.cx = max(0, min(x, self.cols - 1))
        self.cy = max(0, min(y, self.rows - 1))

    def print_text(self, text):
        """Output without appending a newline."""
        for ch in text:
            self._putchar(ch)

    def print_line(self, text):
        """Output, then append a newline."""
        self.print_text(text)
        self._newline()

    def _putchar(self, ch):
        if ch == "\n":
            self._newline()
            return
        if ch == "\t":
            # Advance to the next tab stop (tab width 8)
            nx = ((self.cx // 8) + 1) * 8
            while self.cx < nx and self.cx < self.cols:
                self.chars[self.cy][self.cx] = " "
                self.cx += 1
            if self.cx >= self.cols:
                self._newline()
            return
        if ch == "\r":
            self.cx = 0
            return
        self.chars[self.cy][self.cx] = ch
        self.cols_color[self.cy][self.cx] = self.color
        self.cx += 1
        if self.cx >= self.cols:
            self._newline()

    def _newline(self):
        self.cx = 0
        self.cy += 1
        if self.cy >= self.rows:
            self._scroll()
            self.cy = self.rows - 1

    def _scroll(self):
        self.chars.pop(0)
        self.cols_color.pop(0)
        self.chars.append([" "] * self.cols)
        self.cols_color.append([self.color] * self.cols)

    # --- Graphics (baked directly into the Image) ---
    def pset(self, x, y, col=None):
        self.gimg.pset(x, y, self.color if col is None else col)

    def line(self, x1, y1, x2, y2, col=None):
        self.gimg.line(x1, y1, x2, y2, self.color if col is None else col)

    # --- Input (INKEY$ / STICK / BUTTON) ---
    def inkey(self):
        return self.key_char

    def stick(self, n):
        # 8-direction value (numpad style). Simplified to an OR of direction bits.
        v = 0
        if pyxel.btn(pyxel.KEY_UP):
            v |= 1
        if pyxel.btn(pyxel.KEY_DOWN):
            v |= 2
        if pyxel.btn(pyxel.KEY_LEFT):
            v |= 4
        if pyxel.btn(pyxel.KEY_RIGHT):
            v |= 8
        return v

    def button(self, n):
        keys = [pyxel.KEY_Z, pyxel.KEY_X, pyxel.KEY_C, pyxel.KEY_SPACE]
        if 0 <= n < len(keys):
            return 1 if pyxel.btn(keys[n]) else 0
        return 0

    # --- Drawing ---
    def draw(self):
        pyxel.cls(self.bg)
        # Transfer the whole graphics layer at once (cost is constant regardless
        # of the number of points)
        pyxel.blt(0, 0, self.gimg, 0, 0, self.gimg.width, self.gimg.height)
        # Overlay the text
        for y in range(self.rows):
            row = self.chars[y]
            colrow = self.cols_color[y]
            for x in range(self.cols):
                ch = row[x]
                if ch != " ":
                    pyxel.text(x * CHAR_W, y * CHAR_H, ch, colrow[x])

    def draw_cursor(self, visible):
        if visible:
            px = self.cx * CHAR_W
            py = self.cy * CHAR_H
            pyxel.rect(px, py + CHAR_H - 1, CHAR_W - 1, 1, 7)
