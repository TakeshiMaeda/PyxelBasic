# -*- coding: utf-8 -*-
"""PyxelBasic launcher script.

Usage:
    python main.py            normal start (edit mode)
    python main.py hello      load samples/hello.bas on startup
"""

import sys

from pyxelbasic.app import App


def main():
    autoload = sys.argv[1] if len(sys.argv) > 1 else None
    App(autoload=autoload)


if __name__ == "__main__":
    main()
