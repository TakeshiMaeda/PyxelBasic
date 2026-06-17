# -*- coding: utf-8 -*-
"""PyxelBasic launcher script.

Usage:
    python main.py                      normal start (edit mode)
    python main.py hello                load hello.bas on startup (shorthand)
    python main.py --load hello         same as above
    python main.py --load stick --run   load and run automatically
    python main.py --workdir ./mybas    set the SAVE/LOAD directory
    python main.py --vm-cycle-ms 8      slow the VM throttle (retro pacing)
    python main.py --showfps            show the frame rate in the title bar
    python main.py --version            print the version and exit
"""

import argparse

from pyxelbasic.version import __version__
from pyxelbasic.runtime import GFX_QUEUE_CAPACITY
from pyxelbasic.session import CYCLE_STEPS, CYCLE_PERIOD


def _positive_int(s):
    v = int(s)
    if v < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return v


def _nonneg_float(s):
    v = float(s)
    if v < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return v


def build_parser():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="PyxelBasic - a line-numbered classic-style BASIC on Pyxel.")
    parser.add_argument(
        "file", nargs="?", default=None,
        help="program to load on startup (shorthand for --load)")
    parser.add_argument(
        "--load", metavar="FILE", default=None,
        help="program file to load on startup")
    parser.add_argument(
        "--workdir", metavar="DIR", default=None,
        help="directory used by SAVE/LOAD "
             "(fixed at startup; cannot be changed from inside the interpreter)")
    parser.add_argument(
        "--gfx-queue-size", metavar="N", type=_positive_int,
        default=GFX_QUEUE_CAPACITY,
        help="graphics-command (PSET/LINE) queue capacity (default %(default)s)")
    parser.add_argument(
        "--vm-cycle-steps", metavar="N", type=_positive_int, default=CYCLE_STEPS,
        help="BASIC statements run per throttle cycle (default %(default)s)")
    parser.add_argument(
        "--vm-cycle-ms", metavar="MS", type=_nonneg_float,
        default=CYCLE_PERIOD * 1000.0,
        help="target throttle cycle period in ms; 0 runs free "
             "(default %(default)s)")
    parser.add_argument(
        "--run", action="store_true",
        help="run the program automatically after loading")
    parser.add_argument(
        "--showfps", action="store_true",
        help="show the frame rate in the title bar")
    parser.add_argument(
        "--debug-throttle", action="store_true",
        help="measure the in-app sleep floor and effective throttle rate "
             "at startup and print it to stderr")
    parser.add_argument(
        "--version", action="store_true",
        help="print the version and exit without starting")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        print("PyxelBasic prototype v%s" % __version__)
        return

    # --load takes precedence over the positional shorthand.
    load = args.load or args.file
    if args.run and not load:
        parser.error("--run requires a program to load (use --load FILE)")

    # Imported here so that --version needs neither Pyxel nor a display.
    from pyxelbasic.app import App
    App(autoload=load, workdir=args.workdir, autorun=args.run,
        show_fps=args.showfps, gfx_queue_size=args.gfx_queue_size,
        cycle_steps=args.vm_cycle_steps,
        cycle_period=args.vm_cycle_ms / 1000.0,
        debug_throttle=args.debug_throttle).run()


if __name__ == "__main__":
    main()
