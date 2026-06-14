# -*- coding: utf-8 -*-
"""PyxelBasic launcher script.

Usage:
    python main.py                      normal start (edit mode)
    python main.py hello                load hello.bas on startup (shorthand)
    python main.py --load hello         same as above
    python main.py --load stick --run   load and run automatically
    python main.py --workdir ./mybas    set the SAVE/LOAD directory
    python main.py --version            print the version and exit
"""

import argparse

from pyxelbasic.version import __version__


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
        "--run", action="store_true",
        help="run the program automatically after loading")
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
    App(autoload=load, workdir=args.workdir, autorun=args.run)


if __name__ == "__main__":
    main()
