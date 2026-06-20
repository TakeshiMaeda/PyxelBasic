# -*- coding: utf-8 -*-
"""Pyxel rendering front end: text renderer and graphics surface.

This is the only place (besides app.py) that touches Pyxel drawing. The text is
displayed from an immutable TextSnapshot published by the platform-independent
text screen (textscreen.py); the graphics surface is a Pyxel image the main
thread applies queued PSET/LINE/CLS commands to. The two layers are baked into
Pyxel images and blt'd, so per-frame cost is constant.
"""

import pyxel

CHAR_W = 4   # width of one character in Pyxel's built-in font
CHAR_H = 6   # height of one line


class PyxelGraphicsSurface:
    """GraphicsSurface: the target the graphics command queue is drained into.

    Methods match the queued command names (cls / pset / line); colours are
    already resolved on the VM side before they reach here.
    """

    def __init__(self, width, height, bg=0):
        self.bg = bg
        self.img = pyxel.Image(width, height)
        self.img.cls(bg)

    def cls(self):
        self.img.cls(self.bg)

    def pset(self, x, y, col):
        self.img.pset(x, y, col)

    def pget(self, x, y):
        return self.img.pget(x, y)

    def line(self, x1, y1, x2, y2, col):
        self.img.line(x1, y1, x2, y2, col)

    def rect(self, x1, y1, x2, y2, col):
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1) + 1, abs(y2 - y1) + 1
        self.img.rect(x, y, w, h, col)

    def rectb(self, x1, y1, x2, y2, col):
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1) + 1, abs(y2 - y1) + 1
        self.img.rectb(x, y, w, h, col)

    def elli(self, x, y, rx, ry, col):
        self.img.elli(x - rx, y - ry, 2 * rx + 1, 2 * ry + 1, col)

    def ellib(self, x, y, rx, ry, col):
        self.img.ellib(x - rx, y - ry, 2 * rx + 1, 2 * ry + 1, col)

    def tri(self, x1, y1, x2, y2, x3, y3, col):
        self.img.tri(x1, y1, x2, y2, x3, y3, col)


class PyxelRenderer:
    """TextRenderer: displays a TextSnapshot plus a GraphicsSurface each frame."""

    def __init__(self, cols, rows, gfx_surface, bg=0):
        self.cols = cols
        self.rows = rows
        self.gfx = gfx_surface
        self.bg = bg
        self.timg = pyxel.Image(cols * CHAR_W, rows * CHAR_H)
        self._last_version = None

    def render(self, snapshot, cursor_visible):
        if snapshot is not None and snapshot.version != self._last_version:
            self._render_text(snapshot)
            self._last_version = snapshot.version
        pyxel.cls(self.bg)
        pyxel.blt(0, 0, self.gfx.img, 0, 0, self.gfx.img.width,
                  self.gfx.img.height)
        pyxel.blt(0, 0, self.timg, 0, 0, self.timg.width, self.timg.height,
                  self.bg)
        if cursor_visible and snapshot is not None:
            self._draw_cursor(snapshot)

    def _render_text(self, snap):
        """Bake the snapshot's text grid into self.timg."""
        self.timg.cls(self.bg)
        for y in range(snap.rows):
            row = snap.chars[y]
            colrow = snap.colors[y]
            x = 0
            while x < snap.cols:
                if row[x] == " ":
                    x += 1
                    continue
                col = colrow[x]
                start = x
                buf = []
                while x < snap.cols and row[x] != " " and colrow[x] == col:
                    buf.append(row[x])
                    x += 1
                self.timg.text(start * CHAR_W, y * CHAR_H, "".join(buf), col)

    def _draw_cursor(self, snap):
        px = snap.cx * CHAR_W
        py = snap.cy * CHAR_H
        if snap.insert_mode:
            pyxel.rect(px, py + CHAR_H - 1, CHAR_W - 1, 1, 7)   # underline caret
        else:
            pyxel.rectb(px, py, CHAR_W, CHAR_H, 7)              # block caret
