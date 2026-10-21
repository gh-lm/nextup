#!/usr/bin/env python3
"""Fail if any tracked text file contains an emoji.

Only the Unicode emoji blocks are checked, so ordinary punctuation, arrows
and accented letters pass.
"""
import subprocess
import sys

RANGES = (
    (0x1F000, 0x1FAFF),  # pictographs, emoticons, transport, symbols, flags
    (0x2600, 0x27BF),    # miscellaneous symbols and dingbats
    (0x2B50, 0x2B55),    # stars and circles used as emoji
    (0xFE0F, 0xFE0F),    # emoji presentation selector
)


def is_emoji(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in RANGES)


def main():
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    found = 0
    for path in files:
        try:
            text = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            hits = [ch for ch in line if is_emoji(ch)]
            if hits:
                found += 1
                print(f"{path}:{number}: emoji {' '.join(f'U+{ord(h):04X}' for h in hits)}")
    if found:
        print(f"{found} line(s) with emoji")
        return 1
    print("no emoji found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
