"""Shared pytest fixtures and setup."""

from __future__ import annotations

import os

# Set headless Qt platform before any PySide6 import, so Qt tests
# run without a display (CI, developer machines without a screen).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
