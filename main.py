#!/usr/bin/env python
"""
CLI entry point for the OneDrive AI Organizer project.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from onedrive_ai_organizer import run  # noqa: E402  (import after sys.path manipulation)


def main() -> None:
    """Execute the main export routine."""
    run()


if __name__ == "__main__":
    main()
