"""
Terminal presentation layer for the CLI (run_local.py).

Phase 1 has no graphical UI — the terminal output of the local runner IS the
product's user interface. This module treats it like one: consistent visual
hierarchy, aligned columns, status color, and graceful degradation.

UX principles applied here:
  * Color communicates STATUS at a glance (green=eligible, amber=not-yet,
    red=ineligible) — but is never the ONLY signal (labels + grouping carry the
    meaning too, for colorblind users and no-color terminals).
  * Alignment is computed on VISIBLE width (ANSI codes stripped), so columns line
    up whether or not color is on.
  * Degrades safely: no color when piped, when NO_COLOR is set, or on a dumb
    terminal. Force it with GRANTSCOUT_FORCE_COLOR=1 for demos/recordings.
  * UTF-8 output is forced so box-drawing characters never crash a redirected run.
"""
from __future__ import annotations

import os
import re
import sys

WIDTH = 74  # content width; keeps lines comfortable in an 80-col terminal

# --- Make Unicode output safe even when stdout is redirected to a pipe/file ---
try:  # pragma: no cover - environment dependent
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 - reconfigure is best-effort
    pass


def _supports_color() -> bool:
    if os.environ.get("GRANTSCOUT_FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    stream = sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def _enable_windows_vt() -> None:  # pragma: no cover - Windows-only
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:  # noqa: BLE001
        pass


COLOR = _supports_color()
if COLOR:
    _enable_windows_vt()

# --- Palette ---------------------------------------------------------------
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
AMBER = "\x1b[33m"
RED = "\x1b[31m"
CYAN = "\x1b[36m"
GREY = "\x1b[90m"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def paint(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes when color is enabled; otherwise return as-is."""
    if not COLOR or not codes:
        return text
    return "".join(codes) + text + RESET


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def vlen(text: str) -> int:
    """Visible length (ANSI-stripped) — use for alignment math."""
    return len(strip_ansi(text))


def pad(text: str, width: int, align: str = "left") -> str:
    """Pad to a visible width, ignoring ANSI codes."""
    gap = max(0, width - vlen(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def truncate(text: str, width: int) -> str:
    """Truncate to a visible width with an ellipsis (assumes no ANSI in input)."""
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)].rstrip() + "…"


# --- Structural elements ---------------------------------------------------
def rule(char: str = "─", width: int = WIDTH, color: str | None = GREY) -> str:
    line = char * width
    return paint(line, color) if color else line


def banner(title: str, subtitle: str = "") -> None:
    print()
    print(rule("━"))
    print(paint(f" {title}", BOLD, CYAN))
    if subtitle:
        print(paint(f" {subtitle}", DIM))
    print(rule("━"))


def section(title: str) -> None:
    print()
    print(paint(title, BOLD))
    print(rule("─"))


def step(text: str) -> None:
    """A pipeline progress line."""
    print(f"{paint('▶', CYAN)} {text}")


def note(text: str) -> None:
    print(paint(text, DIM))


# --- Domain-specific rendering --------------------------------------------
# Status -> (human label, color, bullet). Meaning is carried by BOTH the word and
# the color, so nothing is lost without color.
_STATUS = {
    "eligible": ("eligible", GREEN),
    "gaps": ("not yet eligible", AMBER),
    "ineligible": ("ineligible", RED),
}
_GROUP_HEADERS = {
    "eligible": "ELIGIBLE — you meet every hard requirement",
    "gaps": "NOT YET ELIGIBLE — fixable gaps, worth working toward",
    "ineligible": "INELIGIBLE — structural mismatch (wrong audience or region)",
}


def status_color(status: str) -> str:
    return _STATUS.get(status, ("", ""))[1]


def status_label(status: str) -> str:
    return _STATUS.get(status, (status, ""))[0]


def group_header(status: str) -> None:
    label = _GROUP_HEADERS.get(status, status.upper())
    print()
    print(paint(f"  {label}", BOLD, status_color(status)))


def highlight_markers(text: str, marker: str = "[ORG TO PROVIDE]") -> str:
    """Make the action markers impossible to miss inside a draft body."""
    if marker not in text:
        return text
    return text.replace(marker, paint(marker, BOLD, AMBER))
