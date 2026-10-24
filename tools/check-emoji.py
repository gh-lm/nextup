#!/usr/bin/env python3
"""Fail if any tracked text file contains an emoji."""
import subprocess
import sys

RANGES = (
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B50, 0x2B55),
    (0xFE0F, 0xFE0F),
)

def is_emoji(ch):
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in RANGES)

def main():
    listing = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    files = [name.decode("utf-8") for name in listing.split(b"\0") if name]
    found = 0
    for path in files:
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
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
