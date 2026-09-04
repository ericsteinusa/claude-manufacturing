#!/usr/bin/env python3
"""Guard the Windows PowerShell scripts against a silent encoding trap.

The .ps1 files in scripts/windows/ are UTF-8 without a BOM. Windows
PowerShell 5.1 — which is what actually runs them on the deployment box —
decodes BOM-less files using the ANSI code page, not UTF-8. A UTF-8
em-dash (E2 80 94) therefore arrives as three characters ending in 0x94,
which cp1252 maps to U+201D RIGHT DOUBLE QUOTATION MARK. PowerShell
accepts smart quotes as string delimiters, so a non-ASCII character
inside a double-quoted string silently changes where that string ends.

Both observed failure modes trace to this, and they look nothing alike:

  * An ODD number of stray quotes leaves a string unterminated. The file
    fails to parse and the script simply errors out — noisy, easy to spot.
    (manufacture-run.ps1 did this: "Missing closing '}'" at the opening
    line of every enclosing block.)

  * An EVEN number lets the stray quotes pair up. Everything between them
    becomes one string literal and the file still parses CLEAN — but the
    code in that span never executes. manufacture-autopull.ps1 lost 30
    lines this way, including `git pull origin main --ff-only`, and spent
    weeks reporting success while never pulling anything.

The second mode is why this check does not simply run the parser: the
broken file parses without error. The reliable invariant is the cause
rather than either symptom — keep executable lines ASCII-only. Comments
are exempt: a mangled quote inside a comment is harmless, since comments
run to end of line regardless, and the existing files have prose
em-dashes in their docstrings worth keeping.

Run directly (`python scripts/check_powershell_encoding.py`) or via CI.
Exits non-zero and prints file:line on any violation.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent / "windows"


def _is_comment(line: str) -> bool:
    """True for lines PowerShell will not parse as executable code.

    Covers `#` comments and the `.SYNOPSIS`-style directive lines inside
    a <# ... #> help block. Block-comment *bodies* are matched by the
    latter or are prose lines that happen not to start with `#`, so this
    is deliberately conservative: a prose line misclassified as code only
    ever produces a false positive, which is the safe direction.
    """
    stripped = line.lstrip()
    return (
        stripped.startswith("#")
        or stripped.startswith(".")
        or stripped.startswith("<#")
        or stripped.startswith("#>")
    )


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    in_block_comment = False

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()

        if stripped.startswith("<#"):
            in_block_comment = True
        if in_block_comment:
            if "#>" in line:
                in_block_comment = False
            continue
        if _is_comment(line):
            continue

        for col, ch in enumerate(line, 1):
            if ord(ch) > 0x7F:
                problems.append(
                    f"{path.as_posix()}:{lineno}:{col}: non-ASCII {ch!r} "
                    f"(U+{ord(ch):04X}) in executable code — Windows PowerShell 5.1 "
                    f"will mis-decode this and may silently truncate the enclosing string"
                )
    return problems


def main() -> int:
    if not SCRIPT_DIR.is_dir():
        print(f"no such directory: {SCRIPT_DIR}", file=sys.stderr)
        return 1

    scripts = sorted(SCRIPT_DIR.glob("*.ps1"))
    if not scripts:
        print(f"no .ps1 files found under {SCRIPT_DIR}", file=sys.stderr)
        return 1

    all_problems: list[str] = []
    for path in scripts:
        all_problems.extend(check_file(path))

    if all_problems:
        print("PowerShell encoding check FAILED:\n", file=sys.stderr)
        for p in all_problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "\nFix: replace the character with an ASCII equivalent (em-dash -> '-'),"
            "\nor move the text into a comment, where mis-decoding is harmless.",
            file=sys.stderr,
        )
        return 1

    print(f"PowerShell encoding check passed ({len(scripts)} file(s), executable lines are ASCII)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
