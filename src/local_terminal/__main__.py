"""Launch the Local Terminal (API + built UI) with one command.

Usage:
    .venv/Scripts/python.exe -m src.local_terminal
"""

from __future__ import annotations

from src.local_terminal.server import main

if __name__ == "__main__":
    main()
