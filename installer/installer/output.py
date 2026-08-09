"""Colored terminal output helpers — no external dependencies."""

from __future__ import annotations

import sys


def _supports_color() -> bool:
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def _is_interactive() -> bool:
    """Check if stdin is a real TTY (not piped/redirected)."""
    return hasattr(sys.stdin, "isatty") and sys.stdin.isatty()


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
        "  ______ ______      __                         _ ",
        " |  ____/ __ \\ \\    / /                        | |",
        " | |__ | |  | \\ \\  / /   _ __   __ _ _ __   ___| |",
        " |  __|| |  | |\\ \\/ /   | '_ \\ / _` | '_ \\ / _ \\ |",
        " | |___| |__| | \\  /    | |_) | (_| | | | |  __/ |",
        " |______\\____/   \\/     | .__/ \\__,_|_| |_|\\___|_|",
        "                        | |                       ",
        "                        |_|                       ",
    ]
    for line in lines:
        print(f"  {cyan(line)}")


def heading(text: str) -> None:
    print(f"\n{bold(text)}")
    print(f"{'─' * len(text)}")


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question. Returns default if piped. Exits on Ctrl+C."""
    if not _is_interactive():
        return default
    suffix = " [Y/n]" if default else " [y/N]"
    try:
        answer = input(f"  {prompt}{suffix}: ").strip().lower()
    except KeyboardInterrupt:
        print()
        raise SystemExit(130)
    except (EOFError, UnicodeDecodeError):
        print()
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_str(label: str, default: str = "") -> str:
    """Ask for a string. Returns default if piped. Exits on Ctrl+C."""
    if not _is_interactive():
        return default
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"  {label}{suffix}: ").strip()
    except KeyboardInterrupt:
        print()
        raise SystemExit(130)
    except (EOFError, UnicodeDecodeError):
        print()
        return default
    return answer or default


def prompt_secret(label: str) -> str:
    """Ask for a password (hidden input). Returns empty on piped. Exits on Ctrl+C."""
    if not _is_interactive():
        return ""
    import getpass
    try:
        return getpass.getpass(f"  {label}: ")
    except KeyboardInterrupt:
        print()
        raise SystemExit(130)
    except (EOFError, UnicodeDecodeError):
        print()
        return ""


def prompt_str_required(label: str, default: str = "", min_length: int = 1) -> str:
    """Ask for a string that must not be empty. Loops until valid input."""
    while True:
        value = prompt_str(label, default)
        if value and len(value) >= min_length:
            return value
        fail(f"{label} cannot be empty. Please enter a valid value.")


def prompt_secret_required(label: str, min_length: int = 1) -> str:
    """Ask for a password that must not be empty. Loops until valid input."""
    if not _is_interactive():
        return ""
    while True:
        value = prompt_secret(label)
        if value and len(value) >= min_length:
            return value
        if min_length > 1:
            fail(f"{label} must be at least {min_length} characters.")
        else:
            fail(f"{label} cannot be empty. Please enter a password.")
