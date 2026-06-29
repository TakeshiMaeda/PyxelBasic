# -*- coding: utf-8 -*-
"""Pyxel audio front end for the PLAY statement.

The only place (besides app.py / console.py) that touches Pyxel. The BASIC core
stays Pyxel-independent and reaches this through the IOTarget seam, routed on a
dedicated audio command sink so audio runs on the main thread (like graphics)
and never competes with the graphics queue.

Per the language design, MML is never handed to pyxel.play() directly: a fresh
pyxel.Sound() is built and fed the MML, then played. Sound instances are created
on demand (pyxel.sounds[n] / pyxel.musics[n] are not used).

  PLAY        -> loop=False, resume=<channel active>  (one-shot; interrupt+return)
  PLAY LOOP   -> loop=True,  resume=False              (sustained / BGM)

resume gating: a one-shot PLAY should return to the previous sound only when the
channel still has one to return to. pyxel.stop() does NOT clear the channel's
resume target, so a plain resume=True after a stop would resurrect the stopped
sound. We therefore track a per-channel "logically active" flag: it is set on any
play and cleared by PLAY STOP, and a one-shot uses resume = that flag. Effects:

  - after PLAY STOP, the flag is clear, so a one-shot does not resurrect the
    stopped sound;
  - over a still-playing sound (BGM or even a one-shot), the flag is set, so the
    one-shot interrupts and the previous sound resumes afterwards;
  - after a sound ends on its own the flag stays set, but Pyxel then has nothing
    to resume, so passing resume=True is harmless.

MML validity is not re-implemented here: pyxel's Sound.mml() raises on invalid
input, and that exception is caught. play_channels / play_ch build (and thereby
validate) every sound first, so an invalid MML aborts before anything plays and
the offending MML string is returned for the core to raise as a BASIC error.
"""

import pyxel


class PyxelBasicAudio:
    """Plays MML on Pyxel's 4 channels via on-demand pyxel.Sound() instances."""

    def __init__(self):
        # Per-channel "logically active" flag (see module docstring: resume gating).
        self._active = [False, False, False, False]

    def _make_sound(self, mml):
        snd = pyxel.Sound()
        snd.mml(mml)            # raises on invalid MML (caught by callers)
        return snd

    def _play(self, ch, snd, loop):
        if loop:
            pyxel.play(ch, snd, loop=True, resume=False)
        else:
            # Resume only when the channel still holds a sound we did not stop, so
            # a one-shot after PLAY STOP does not bring the stopped sound back.
            pyxel.play(ch, snd, loop=False, resume=self._active[ch])
        self._active[ch] = True

    def play_channels(self, mmls, loop=False):
        """Play one MML per channel (index 0..3). None / "" channels are skipped.

        Returns None on success, or the first invalid MML string (nothing is
        played in that case, so a bad channel does not leave a partial mix)."""
        prepared = []
        for ch in range(4):
            if ch >= len(mmls):
                continue
            mml = mmls[ch]
            if not mml:                 # None or ""
                continue
            try:
                snd = self._make_sound(mml)
            except Exception:
                return mml              # invalid MML: play nothing
            prepared.append((ch, snd))
        for ch, snd in prepared:
            self._play(ch, snd, loop)
        return None

    def play_ch(self, ch, mml, loop=False):
        """Play a single channel. Returns None on success or the invalid MML."""
        if not mml:
            return None
        try:
            snd = self._make_sound(mml)
        except Exception:
            return mml
        self._play(ch, snd, loop)
        return None

    def play_stop(self, channels):
        """Stop the given channels (empty / falsy means all four)."""
        if not channels:
            channels = range(4)
        for ch in channels:
            pyxel.stop(ch)
            self._active[ch] = False    # cleared so a later one-shot will not resume it

    def playing(self, ch):
        """1 if channel ch is currently playing, else 0."""
        return 1 if pyxel.play_pos(ch) is not None else 0
