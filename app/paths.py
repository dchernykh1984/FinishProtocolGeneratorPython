"""Resolve where the app keeps its data.

The app stores its files (race info, logs) next to the program, so a
downloaded portable build keeps everything beside the executable the user ran
(not in a random working directory). In development this is the project root.
"""

from __future__ import annotations

import sys
from pathlib import Path


def base_dir() -> Path:
    """Directory the app reads and writes its data in.

    Frozen (PyInstaller): the folder that contains the runnable, so data sits
    next to the downloaded program. On macOS the runnable lives inside
    ``<name>.app/Contents/MacOS/``, so the bundle's parent folder is used. In
    development: the project root.
    """
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if (
            exe.parent.name == "MacOS"
            and exe.parents[1].name == "Contents"
            and exe.parents[2].suffix == ".app"
        ):
            return exe.parents[3]
        return exe.parent
    return Path(__file__).resolve().parents[1]


def app_path(*parts: str) -> Path:
    """Path to a data file/folder resolved against :func:`base_dir`."""
    return base_dir().joinpath(*parts)
