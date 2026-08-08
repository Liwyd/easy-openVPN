"""Colored terminal output helpers — no external dependencies."""

from __future__ import annotations

import sys


def _supports_color() -> bool:
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


_COLOR = _supports_color()

# ANSI codes
_RESET = "\033[0m" if _COLOR else ""
_BOLD = "\033[1m" if _COLOR else ""
_DIM = "\033[2m" if _COLOR else ""
_RED = "\033[31m" if _COLOR else ""
_GREEN = "\033[32m" if _COLOR else ""
_YELLOW = "\033[33m" if _COLOR else ""
_CYAN = "\033[36m" if _COLOR else ""


def bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


def dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"


def red(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


def green(text: str) -> str:
    return f"{_GREEN}{text}{_RESET}"


def yellow(text: str) -> str:
    return f"{_YELLOW}{text}{_RESET}"


def cyan(text: str) -> str:
    return f"{_CYAN}{text}{_RESET}"


def ok(msg: str) -> None:
    print(f"  {green('[+]')} {msg}")


def warn(msg: str) -> None:
    print(f"  {yellow('[!]')} {msg}")


def fail(msg: str) -> None:
    print(f"  {red('[✗]')} {msg}")


def info(msg: str) -> None:
    print(f"  {cyan('[*]')} {msg}")


def step(num: int, total: int, msg: str) -> None:
    print(f"\n{bold(f'[{num}/{total}]')} {bold(msg)}")


def banner() -> None:
    lines = [
        "  ______ ____  _____ _____ _______   __",
        " |  ____/ ___|| ____|_   _| ____\\ \\ / /",
        " |  _| \\___ \\|  _|   | | |  _|  \\ V / ",
        " | |___ ___) | |___  | | | |___  | |  ",
        " |_____|____/|_____| |_| |_____| |_|  ",
    ]
    for line in lines:
        print(f"  {cyan(line)}")


def heading(text: str) -> None:
    print(f"\n{bold(text)}")
    print(f"{'─' * len(text)}")


def confirm(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    try:
        answer = input(f"  {prompt}{suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_str(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"  {label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer or default


def prompt_secret(label: str) -> str:
    import getpass
    try:
        return getpass.getpass(f"  {label}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
