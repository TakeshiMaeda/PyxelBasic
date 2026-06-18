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

    def drain(self, console):
        """Main thread: apply every queued command to the console.

        Done under the lock so that when a waiter observes the queue empty, all
        commands have actually been applied (so a future screen-read after
        wait_empty() sees an up-to-date Console)."""
        with self._cond:
            while self._dq:
                name, args = self._dq.popleft()
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
