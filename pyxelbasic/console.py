# -*- coding: utf-8 -*-
"""Text console and graphics surface on top of Pyxel.

Referenced by the interpreter as an IOTarget. Characters live in a grid buffer
(a virtual screen) and are drawn every frame; that same buffer is what the
full-screen editor edits. A per-row continuation flag groups screen rows into
logical lines, so one logical line can wrap across several rows. There is a
single cursor used both for output (PRINT flows from it; LOCATE moves it) and
for editing. Graphics commands (PSET/LINE) are baked into a dedicated image and
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
        # frame (replaying stored draw commands every frame would get slower as
        # the number of points grows).
        self.gimg = pyxel.Image(cols * CHAR_W, rows * CHAR_H)
        self.gimg.cls(self.bg)
        self.insert_mode = True     # editor: insert (True) vs overtype (False)
        self._clear_buffer()
        # Key input (for INKEY$): the character typed in the most recent frame.
        self.key_char = ""

    def _clear_buffer(self):
        self.chars = [[" "] * self.cols for _ in range(self.rows)]
        self.cols_color = [[self.color] * self.cols for _ in range(self.rows)]
        # cont[y] is True when row y continues the logical line started above it.
        self.cont = [False] * self.rows
        self.cx = 0
        self.cy = 0

    # --- IOTarget interface ---
    def cls(self):
        self._clear_buffer()
        self.gimg.cls(self.bg)

    def set_color(self, col):
        self.color = col

    def locate(self, x, y):
        # LOCATE moves the (unified output/edit) cursor.
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
                self.cols_color[self.cy][self.cx] = self.color
                self.cx += 1
            if self.cx >= self.cols:
                self._advance_row(True)
            return
        if ch == "\r":
            self.cx = 0
            return
        self.chars[self.cy][self.cx] = ch
        self.cols_color[self.cy][self.cx] = self.color
        self.cx += 1
        if self.cx >= self.cols:
            self._advance_row(True)   # wrapped: the next row continues this line

    def _newline(self):
        self._advance_row(False)      # explicit newline starts a new logical line

    def _advance_row(self, cont_flag):
        self.cx = 0
        self.cy += 1
        if self.cy >= self.rows:
            self._scroll()
            self.cy = self.rows - 1
        self.cont[self.cy] = cont_flag

    def _scroll(self):
        self.chars.pop(0)
        self.cols_color.pop(0)
        self.cont.pop(0)
        self.chars.append([" "] * self.cols)
        self.cols_color.append([self.color] * self.cols)
        self.cont.append(False)
        self.cont[0] = False          # the top row can never be a continuation

    # --- Logical line model (for the editor) ---
    def _logical_start(self, y):
        while y > 0 and self.cont[y]:
            y -= 1
        return y

    def _logical_end(self, y):
        while y + 1 < self.rows and self.cont[y + 1]:
            y += 1
        return y

    def get_logical_text(self, y=None):
        """Return (text, start_row, end_row) of the logical line containing y."""
        if y is None:
            y = self.cy
        r = self._logical_start(y)
        s = self._logical_end(y)
        buf = []
        for yy in range(r, s + 1):
            buf.extend(self.chars[yy])
        return "".join(buf).rstrip(" "), r, s

    def caret_index(self):
        """Cursor offset within its logical line (used to skip an INPUT prompt)."""
        r = self._logical_start(self.cy)
        return (self.cy - r) * self.cols + self.cx

    # --- Cursor movement ---
    def move_left(self):
        if self.cx > 0:
            self.cx -= 1
        elif self.cy > 0:
            self.cy -= 1
            self.cx = self.cols - 1

    def move_right(self):
        if self.cx < self.cols - 1:
            self.cx += 1
        elif self.cy < self.rows - 1:
            self.cy += 1
            self.cx = 0

    def move_up(self):
        if self.cy > 0:
            self.cy -= 1

    def move_down(self):
        if self.cy < self.rows - 1:
            self.cy += 1

    def home(self):
        self.cy = self._logical_start(self.cy)
        self.cx = 0

    def end(self):
        text, r, s = self.get_logical_text(self.cy)
        pos = len(text)
        cy = r + pos // self.cols
        cx = pos % self.cols
        if cy > s:
            cy, cx = s, self.cols - 1
        self.cy = min(cy, self.rows - 1)
        self.cx = min(cx, self.cols - 1)

    def toggle_insert(self):
        self.insert_mode = not self.insert_mode

    def cursor_to_next_logical(self):
        """Move the cursor to the start of the line below the current logical one."""
        s = self._logical_end(self.cy)
        ny = s + 1
        if ny >= self.rows:
            self._scroll()
            ny = self.rows - 1
        self.cy = ny
        self.cx = 0

    # --- Editing (insert / overtype / delete with reflow) ---
    def _logical_cells_and_caret(self):
        r = self._logical_start(self.cy)
        s = self._logical_end(self.cy)
        cells = []
        for yy in range(r, s + 1):
            for x in range(self.cols):
                cells.append([self.chars[yy][x], self.cols_color[yy][x]])
        caret = (self.cy - r) * self.cols + self.cx
        # Trim trailing spaces, but never past the caret (so typing in a blank
        # region keeps the spaces sitting before the caret).
        last = len(cells)
        while last > 0 and cells[last - 1][0] == " ":
            last -= 1
        cells = cells[:max(last, caret)]
        return cells, caret, r, s

    def type_char(self, ch):
        cells, caret, r, s = self._logical_cells_and_caret()
        if self.insert_mode or caret >= len(cells):
            cells.insert(caret, [ch, self.color])
        else:
            cells[caret] = [ch, self.color]
        self._apply_logical(r, s, cells, caret + 1)

    def delete_at(self):
        cells, caret, r, s = self._logical_cells_and_caret()
        if caret < len(cells):
            del cells[caret]
            self._apply_logical(r, s, cells, caret)

    def backspace(self):
        cells, caret, r, s = self._logical_cells_and_caret()
        if caret > 0:
            del cells[caret - 1]
            self._apply_logical(r, s, cells, caret - 1)
        elif self.cy > 0:
            self.move_left()

    def _apply_logical(self, r, s, cells, new_caret):
        """Re-render the logical line (rows r..s) from `cells`, reflowing rows."""
        n = len(cells)
        # Enough rows for the content, and for the caret to rest on (when the
        # caret sits just past a row that is exactly full, it needs a fresh
        # continuation row to land on).
        nnew = max(1, (n + self.cols - 1) // self.cols, new_caret // self.cols + 1)
        block_c, block_k, block_cont = [], [], []
        for i in range(nnew):
            rowc = [" "] * self.cols
            rowk = [self.color] * self.cols
            for j in range(self.cols):
                idx = i * self.cols + j
                if idx < n:
                    rowc[j], rowk[j] = cells[idx][0], cells[idx][1]
            block_c.append(rowc)
            block_k.append(rowk)
            block_cont.append(i != 0)
        new_chars = self.chars[:r] + block_c + self.chars[s + 1:]
        new_cols = self.cols_color[:r] + block_k + self.cols_color[s + 1:]
        new_cont = self.cont[:r] + block_cont + self.cont[s + 1:]
        removed_top = 0
        if len(new_chars) > self.rows:
            # The line grew: drop rows from the top (scroll), without eating the
            # block itself; if it is pinned to the top, trim the tail instead.
            rem = min(len(new_chars) - self.rows, r)
            if rem:
                new_chars = new_chars[rem:]
                new_cols = new_cols[rem:]
                new_cont = new_cont[rem:]
                removed_top = rem
            while len(new_chars) > self.rows:
                new_chars.pop()
                new_cols.pop()
                new_cont.pop()
        else:
            while len(new_chars) < self.rows:
                new_chars.append([" "] * self.cols)
                new_cols.append([self.color] * self.cols)
                new_cont.append(False)
        self.chars = new_chars
        self.cols_color = new_cols
        self.cont = new_cont
        self.cont[0] = False
        base_r = r - removed_top
        self.cy = max(0, min(base_r + new_caret // self.cols, self.rows - 1))
        self.cx = max(0, min(new_caret % self.cols, self.cols - 1))

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
        if not visible:
            return
        px = self.cx * CHAR_W
        py = self.cy * CHAR_H
        if self.insert_mode:
            pyxel.rect(px, py + CHAR_H - 1, CHAR_W - 1, 1, 7)   # underline caret
        else:
            pyxel.rectb(px, py, CHAR_W, CHAR_H, 7)              # block caret
