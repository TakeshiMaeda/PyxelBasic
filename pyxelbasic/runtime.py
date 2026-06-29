# -*- coding: utf-8 -*-
"""Runtime plumbing between the BASIC VM and the Pyxel front end.

The interpreter never touches Pyxel directly; this module provides the
Pyxel-independent glue used by the two execution modes (see app.py / session.py).
Some pieces are mode-independent, others are specific to one mode:

- InputRing    : a bounded SPSC event ring (the front end produces key/char
                 events, the VM consumes them) plus KeyState, which derives
                 STICK/BUTTON/INKEY$ from the event stream. Used in BOTH modes.
- CommandQueue : a bounded, thread-safe queue of graphics commands. The VM
                 enqueues; the main thread drains and applies them to the graphics
                 surface. THREAD MODE only (it crosses the VM/main-thread boundary).
- DirectGraphics: a same-thread graphics target that applies each command to the
                 surface immediately. MAIN-DRIVEN MODE only (the VM runs on the
                 main thread, so no queue or boundary is needed).
- InputState   : a thread-safe level snapshot of the input devices. Kept as a
                 reserved fallback; not on the active path of either mode.

None of this imports Pyxel, so the interpreter side stays headless-testable.
"""

import collections
import threading

from .keywords import STICK_BITS, BUTTON_KEYS

# Bounded queue capacity. Deliberately small to evoke a retro BASIC drawing
# pace: a loop that emits more than this many screen commands per iteration is
# spread across several display frames. Tune freely.
QUEUE_CAPACITY = 4

# Default graphics command queue capacity. Large enough to act as a plain
# thread-safe channel; execution pace is set by the VM throttle, not this.
GFX_QUEUE_CAPACITY = 1024

# Optional VM execution throttle (independent of the queue). The VM thread
# sleeps THROTTLE_DELAY seconds every THROTTLE_EVERY executed statements, giving
# a knob for retro-feel pacing and CPU relief on tight non-drawing loops.
# Disabled by default (THROTTLE_EVERY = 0).
THROTTLE_EVERY = 0
THROTTLE_DELAY = 0.0

# --- Input event ring (main thread -> VM thread) ---
# The main thread edge-detects keys/typed chars and pushes events here; the VM
# drains them. Bounded; when full the newest event is dropped (typeahead-full).
INPUT_RING_CAPACITY = 256

# Sentinel for CommandQueue.call(): distinguishes "not serviced yet" from a real
# None result (a call such as a successful play legitimately returns None).
_PENDING = object()

# Event kinds. value = the character (CHAR) or an abstract key id (the rest).
EV_CHAR = "char"     # a typed printable character
EV_DOWN = "down"     # a key was pressed this frame (edge)
EV_UP = "up"         # a key was released this frame (edge)
EV_REPEAT = "repeat"  # auto-repeat tick for a held key (editor use only)


class InputState:
    """Thread-safe snapshot of the input devices.

    The main thread calls update() each frame; the VM thread calls the getters.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.key_char = ""          # most recent typed text (for INKEY$)
        self.stick = 0              # 8-direction bits (numpad style)
        self.buttons = [0, 0, 0, 0]

    def update(self, key_char, stick, buttons):
        with self._lock:
            self.key_char = key_char
            self.stick = stick
            self.buttons = list(buttons)

    def get_key_char(self):
        with self._lock:
            return self.key_char

    def get_stick(self):
        with self._lock:
            return self.stick

    def get_button(self, n):
        with self._lock:
            return self.buttons[n] if 0 <= n < len(self.buttons) else 0


class InputRing:
    """SPSC input event ring: main produces, the VM consumes.

    Lossless until full, then drops the newest event (typeahead-full behaviour).
    """

    def __init__(self, capacity=INPUT_RING_CAPACITY):
        self.capacity = capacity
        self._dq = collections.deque()
        self._lock = threading.Lock()

    def push(self, event):
        """Main thread: enqueue an event; returns False if dropped (full)."""
        with self._lock:
            if len(self._dq) >= self.capacity:
                return False
            self._dq.append(event)
            return True

    def drain(self):
        """VM thread: remove and return all pending events, in order."""
        with self._lock:
            items = list(self._dq)
            self._dq.clear()
            return items


class KeyState:
    """VM-side input state derived from the event stream.

    DOWN/UP maintain a set of currently-held keys (so STICK/BUTTON reflect the
    current level); CHAR events accumulate in a typeahead buffer for INKEY$.
    REPEAT events are for the editor only and do not affect the held set.
    This is the single accessor seam STICK/BUTTON/INKEY$ read through.
    """

    def __init__(self):
        self._down = set()
        self._chars = collections.deque()

    def apply(self, event):
        kind, value = event
        if kind == EV_DOWN:
            self._down.add(value)
        elif kind == EV_UP:
            self._down.discard(value)
        elif kind == EV_CHAR:
            self._chars.append(value)
        # EV_REPEAT: editor-only; no effect on the held set or typeahead.

    def apply_all(self, events):
        for e in events:
            self.apply(e)

    def is_down(self, key_id):
        return key_id in self._down

    def stick(self, n=0):
        v = 0
        for key_id, bit in STICK_BITS:
            if key_id in self._down:
                v |= bit
        return v

    def button(self, n):
        if 0 <= n < len(BUTTON_KEYS):
            return 1 if BUTTON_KEYS[n] in self._down else 0
        return 0

    def inkey(self):
        return self._chars.popleft() if self._chars else ""


class CommandQueue:
    """Bounded, thread-safe queue of (method_name, args) screen commands."""

    def __init__(self, capacity=QUEUE_CAPACITY):
        self.capacity = capacity
        self._dq = collections.deque()
        self._cond = threading.Condition()
        self._stop = False

    def put(self, cmd):
        """VM thread: enqueue a command, blocking while the queue is full."""
        with self._cond:
            while len(self._dq) >= self.capacity and not self._stop:
                self._cond.wait()
            if self._stop:
                return
            self._dq.append(cmd)
            self._cond.notify_all()

    def pget(self, x, y):
        """VM thread: read a pixel through the queue and block for the result.

        The Pyxel image is owned by (and only touchable on) the main thread, so
        the read is enqueued like a draw command and serviced during drain(). A
        holder slot carries the value back; None means not serviced yet (a real
        colour can be 0). Returns 0 if the queue is stopped before servicing."""
        holder = [None]
        with self._cond:
            if self._stop:
                return 0
            self._dq.append(("__pget__", (x, y, holder)))
            self._cond.notify_all()
            while holder[0] is None and not self._stop:
                self._cond.wait()
        return holder[0] if holder[0] is not None else 0

    def call(self, name, args=()):
        """VM thread: invoke a method on the drain target and block for its result.

        Like pget but generic: enqueues a request that drain() services on the
        main thread by calling target.<name>(*args), and returns the value. Used
        by the audio sink (e.g. play/playing) so Pyxel audio calls happen on the
        main thread. Returns None if the queue is stopped before servicing."""
        holder = [_PENDING]
        with self._cond:
            if self._stop:
                return None
            self._dq.append(("__call__", (name, args, holder)))
            self._cond.notify_all()
            while holder[0] is _PENDING and not self._stop:
                self._cond.wait()
        return None if holder[0] is _PENDING else holder[0]

    def drain(self, console):
        """Main thread: apply every queued command to the console.

        Done under the lock so that when a waiter observes the queue empty, all
        commands have actually been applied (so a future screen-read after
        wait_empty() sees an up-to-date Console)."""
        with self._cond:
            while self._dq:
                name, args = self._dq.popleft()
                if name == "__pget__":
                    x, y, holder = args
                    holder[0] = console.pget(x, y)
                elif name == "__call__":
                    fname, fargs, holder = args
                    holder[0] = getattr(console, fname)(*fargs)
                else:
                    getattr(console, name)(*args)
            self._cond.notify_all()

    def wait_empty(self):
        """VM thread: block until the queue has been fully drained/applied."""
        with self._cond:
            while self._dq and not self._stop:
                self._cond.wait()

    def wait_size_le(self, n):
        """VM thread: block until the queue holds at most n entries."""
        with self._cond:
            while len(self._dq) > n and not self._stop:
                self._cond.wait()

    def stop(self):
        """Unblock any waiting VM thread (used on BREAK / shutdown)."""
        with self._cond:
            self._stop = True
            self._cond.notify_all()

    def reset(self):
        """Drop pending commands and clear the stop flag for a fresh RUN."""
        with self._cond:
            self._dq.clear()
            self._stop = False
            self._cond.notify_all()


# --- Sprites (display table + pattern-sheet geometry) ---
# The pattern pixels live in a Pyxel texture on the front end (blt needs an
# Image as its source), so only the display table and the pure pattern-sheet
# geometry live here (Pyxel-independent, headless-testable). The VM updates the
# table; the front end reads a snapshot of it each frame to compose the sprite
# plane (the same "VM writes, front end reads a snapshot" shape as the screen).

SPRITE_SHEET = 256          # pattern sheet is SPRITE_SHEET x SPRITE_SHEET pixels
SPRITE_COUNT = 1024         # number of 8x8 patterns the sheet holds (32x32 cells)


def sprite8_pixel(n):
    """Top-left pixel (px, py) of 8x8 pattern number n on the 256x256 sheet.

    The sheet is grouped into 16x16 blocks (a 2x2 of 8x8 cells). Four 8x8
    patterns form one block: local 0=top-left, 1=top-right, 2=bottom-left,
    3=bottom-right. Blocks are numbered row-major across the 16x16 grid of
    blocks, giving the sheet order  0,1,4,5,...  /  2,3,6,7,...
    """
    block, local = divmod(n, 4)
    bx, by = block % 16, block // 16
    cx = bx * 2 + (1 if local in (1, 3) else 0)
    cy = by * 2 + (1 if local in (2, 3) else 0)
    return cx * 8, cy * 8


def sprite16_pixel(m):
    """Top-left pixel (px, py) of 16x16 sprite number m on the 256x256 sheet.

    A 16x16 sprite is the whole block of four 8x8 patterns m*4..m*4+3, so it
    sits at block (m%16, m//16) -> the same origin as sprite8_pixel(m*4)."""
    return (m % 16) * 16, (m // 16) * 16


class SpriteTable:
    """Display table for sprites: 1024 entries the VM writes and the front end
    reads (via snapshot) each frame.

    Each entry is [enabled, x, y, no, size, colkey]. All entries start disabled
    with zeroed fields. A lock guards the cross-thread access in threaded mode;
    in main-driven mode the same thread writes and reads, so it is uncontended.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._entries = [[False, 0, 0, 0, 0, -1] for _ in range(SPRITE_COUNT)]

    def put(self, sid, x, y, no, size, colkey):
        with self._lock:
            self._entries[sid] = [True, x, y, no, size, colkey]

    def off(self, sid):
        with self._lock:
            self._entries[sid][0] = False

    def clear(self):
        with self._lock:
            for e in self._entries:
                e[0] = False
                e[1] = e[2] = e[3] = e[4] = 0
                e[5] = -1

    def snapshot(self):
        """Return the enabled entries as (id, x, y, no, size, colkey) tuples."""
        with self._lock:
            return [(i, e[1], e[2], e[3], e[4], e[5])
                    for i, e in enumerate(self._entries) if e[0]]


class DirectGraphics:
    """Same-thread graphics target for the main-driven execution mode.

    SessionIO emits graphics as (method_name, args) tuples through put(). In the
    threaded mode those go to a CommandQueue that the Pyxel main thread drains;
    in the main-driven mode the VM already runs on the main thread, so each
    command is applied to the graphics surface immediately. This sidesteps the
    bounded-queue blocking that would deadlock a single thread (a full queue with
    no concurrent drainer). The wait/stop/reset/drain methods are no-ops so this
    is drop-in compatible wherever a CommandQueue is expected.
    """

    def __init__(self, surface):
        self.surface = surface

    def put(self, cmd):
        name, args = cmd
        getattr(self.surface, name)(*args)

    def pget(self, x, y):
        # VM runs on the main thread here, so reading the surface is immediate.
        return self.surface.pget(x, y)

    def call(self, name, args=()):
        # Same thread: dispatch immediately and return the result.
        return getattr(self.surface, name)(*args)

    def drain(self, console=None):
        pass

    def wait_empty(self):
        pass

    def wait_size_le(self, n):
        pass

    def stop(self):
        pass

    def reset(self):
        pass
