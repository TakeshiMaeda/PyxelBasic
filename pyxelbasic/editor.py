# -*- coding: utf-8 -*-
"""Interactive full-screen editor behaviour (keystroke layer).

No Pyxel. Maps editing intents (typing, delete, cursor movement) to the
platform-independent TextScreen primitives. The trickiest grid reflow/scroll
lives in TextScreen; the editor only calls it. The cursor and insert/overtype
flag are part of the TextScreen model (so the renderer can show them); the
editor reads and moves them.
"""


class Editor:
    def __init__(self, screen):
        self.screen = screen

    # --- Cursor movement ---
    def move_left(self):
        s = self.screen
        if s.cx > 0:
            s.cx -= 1
        elif s.cy > 0:
            s.cy -= 1
            s.cx = s.cols - 1

    def move_right(self):
        s = self.screen
        if s.cx < s.cols - 1:
            s.cx += 1
        elif s.cy < s.rows - 1:
            s.cy += 1
            s.cx = 0

    def move_up(self):
        s = self.screen
        if s.cy > 0:
            s.cy -= 1

    def move_down(self):
        s = self.screen
        if s.cy < s.rows - 1:
            s.cy += 1

    def home(self):
        s = self.screen
        s.cy = s.logical_start(s.cy)
        s.cx = 0

    def end(self):
        s = self.screen
        text, r, e = s.get_logical_text(s.cy)
        pos = len(text)
        cy = r + pos // s.cols
        cx = pos % s.cols
        if cy > e:
            cy, cx = e, s.cols - 1
        s.cy = min(cy, s.rows - 1)
        s.cx = min(cx, s.cols - 1)

    def cursor_to_next_logical(self):
        self.screen.cursor_to_next_logical()

    def toggle_insert(self):
        self.screen.insert_mode = not self.screen.insert_mode

    # --- Editing (insert / overtype / delete with reflow) ---
    def type_char(self, ch):
        s = self.screen
        cells, caret, r, e = s.get_logical_cells()
        if s.insert_mode or caret >= len(cells):
            cells.insert(caret, [ch, s.color])
        else:
            cells[caret] = [ch, s.color]
        s.replace_logical_line(r, e, cells, caret + 1)

    def delete_at(self):
        s = self.screen
        cells, caret, r, e = s.get_logical_cells()
        if caret < len(cells):
            del cells[caret]
            s.replace_logical_line(r, e, cells, caret)

    def backspace(self):
        s = self.screen
        cells, caret, r, e = s.get_logical_cells()
        if caret > 0:
            del cells[caret - 1]
            s.replace_logical_line(r, e, cells, caret - 1)
        elif s.cy > 0:
            self.move_left()
