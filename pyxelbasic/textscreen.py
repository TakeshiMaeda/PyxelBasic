# -*- coding: utf-8 -*-
"""Platform-independent text screen model (virtual text VRAM).

No Pyxel here. Owns the character grid (a virtual screen), the cursor, the
logical-line model (a per-row continuation flag groups rows into wrapped logical
lines), text output commands (PRINT/LOCATE/COLOR and the text half of CLS),
scrolling and logical-line reflow. The interactive editor (editor.py) sits on
top via the logical-line primitives exposed here; a renderer (console.py)
displays an immutable snapshot published from here.

Threading model: a single owner thread (the BASIC VM) mutates this model and
calls publish(); other threads only read the published immutable snapshot, so
the live grid is never accessed concurrently. Scrolling is written to keep the
grid length-invariant regardless, so a stray concurrent read can never see a
short grid.
"""

DEFAULT_COLOR = 7   # white
DEFAULT_BG = 0


class TextSnapshot:
    """Immutable, self-consistent copy of the text screen for rendering."""

    __slots__ = ("cols", "rows", "chars", "colors", "cx", "cy",
                 "insert_mode", "bg", "version")

    def __init__(self, cols, rows, chars, colors, cx, cy, insert_mode, bg,
                 version):
        self.cols = cols
        self.rows = rows
        self.chars = chars      # tuple[rows] of tuple[cols] of 1-char str
        self.colors = colors    # tuple[rows] of tuple[cols] of int
        self.cx = cx
        self.cy = cy
        self.insert_mode = insert_mode
        self.bg = bg
        self.version = version


class TextScreen:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.color = DEFAULT_COLOR
        self.bg = DEFAULT_BG
        self.insert_mode = True     # editor: insert (True) vs overtype (False)
        self._version = 0
        self._clear_buffer()
        self._published = None
        self.publish()

    def _clear_buffer(self):
        self.chars = [[" "] * self.cols for _ in range(self.rows)]
        self.cols_color = [[self.color] * self.cols for _ in range(self.rows)]
        # cont[y] is True when row y continues the logical line started above it.
        self.cont = [False] * self.rows
        self.cx = 0
        self.cy = 0

    def _touch(self):
        self._version += 1

    # --- Text output (IOTarget text half) ---
    def cls(self):
        """Clear the text grid only (the graphics surface is cleared elsewhere)."""
        self._clear_buffer()
        self._touch()

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
        self._touch()
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
        # Shift every row up by one in place; the grid length stays `rows`
        # throughout (no pop/append window), so a concurrent reader can never
        # see a short grid. Row objects are simply re-indexed, not reallocated.
        for y in range(self.rows - 1):
            self.chars[y] = self.chars[y + 1]
            self.cols_color[y] = self.cols_color[y + 1]
            self.cont[y] = self.cont[y + 1]
        self.chars[self.rows - 1] = [" "] * self.cols
        self.cols_color[self.rows - 1] = [self.color] * self.cols
        self.cont[self.rows - 1] = False
        self.cont[0] = False          # the top row can never be a continuation
        self._touch()

    # --- Logical line model (primitives shared by editor and line submission) ---
    def logical_start(self, y):
        while y > 0 and self.cont[y]:
            y -= 1
        return y

    def logical_end(self, y):
        while y + 1 < self.rows and self.cont[y + 1]:
            y += 1
        return y

    def get_logical_text(self, y=None):
        """Return (text, start_row, end_row) of the logical line containing y."""
        if y is None:
            y = self.cy
        r = self.logical_start(y)
        s = self.logical_end(y)
        buf = []
        for yy in range(r, s + 1):
            buf.extend(self.chars[yy])
        return "".join(buf).rstrip(" "), r, s

    def caret_index(self):
        """Cursor offset within its logical line (used to skip an INPUT prompt)."""
        r = self.logical_start(self.cy)
        return (self.cy - r) * self.cols + self.cx

    def get_logical_cells(self):
        """Return (cells, caret, r, s) for the current logical line.

        cells is a list of [char, color]; caret is the index within cells. The
        editor mutates `cells` and hands it back to replace_logical_line().
        """
        r = self.logical_start(self.cy)
        s = self.logical_end(self.cy)
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

    def replace_logical_line(self, r, s, cells, new_caret):
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
        self._touch()

    def cursor_to_next_logical(self):
        """Move the cursor to the start of the line below the current logical one."""
        s = self.logical_end(self.cy)
        ny = s + 1
        if ny >= self.rows:
            self._scroll()
            ny = self.rows - 1
        self.cy = ny
        self.cx = 0
        self._touch()

    # --- Snapshot (tear-free hand-off to the renderer) ---
    def snapshot(self):
        chars = tuple(tuple(row) for row in self.chars)
        colors = tuple(tuple(row) for row in self.cols_color)
        return TextSnapshot(self.cols, self.rows, chars, colors,
                            self.cx, self.cy, self.insert_mode, self.bg,
                            self._version)

    def publish(self):
        """Atomically publish the current state for readers (single ref store)."""
        self._published = self.snapshot()

    def get_published(self):
        return self._published
